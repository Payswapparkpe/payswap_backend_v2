"""
Parking Service — core business logic for Parkpe Smart Parking Platform.

Responsibilities:
- Location geo-search
- Slot availability queries
- Booking creation with Redis distributed lock (no double-booking)
- QR ticket generation (HMAC-SHA256 signed)
- Entry / exit processing
- Final charge calculation with Parkpe Voucher debit
- Revenue rollup
- Price estimation
"""
import hashlib
import hmac
import json
import math
import secrets
import string
from datetime import timedelta
from decimal import Decimal, ROUND_UP

from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from portal.models import (
    ParkingLocation,
    ParkingZone,
    ParkingSlot,
    ParkingRate,
    ParkingBooking,
    ParkingSession,
    ParkingTicket,
    ParkingTransaction,
    ParkingRevenue,
)
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.parking")

# ─── Constants ───────────────────────────────────────────────────────────────
BOOKING_REF_PREFIX = "PKP"
BOOKING_GRACE_EXPIRY_MINUTES = 15   # Auto-cancel if customer doesn't show
QR_HMAC_SECRET_SETTING = "PARKING_QR_SECRET"
DEFAULT_QR_SECRET = "parkpe-qr-default-secret-change-in-prod"
DEFAULT_COMMISSION_PCT = Decimal("5.00")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _qr_secret() -> str:
    return getattr(settings, QR_HMAC_SECRET_SETTING, DEFAULT_QR_SECRET)


def _generate_booking_reference() -> str:
    """PKP-YYYYMMDD-XXXX  (date + 4 random uppercase chars)"""
    today = timezone.now().strftime("%Y%m%d")
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{BOOKING_REF_PREFIX}-{today}-{suffix}"


def _sign_qr(booking_reference: str) -> str:
    """Return HMAC-SHA256 hex of booking_reference — used as QR payload."""
    secret = _qr_secret().encode()
    return hmac.HMAC(secret, booking_reference.encode(), hashlib.sha256).hexdigest()


def verify_qr(booking_reference: str, signature: str) -> bool:
    """Constant-time comparison of QR payload signature."""
    expected = _sign_qr(booking_reference)
    return hmac.compare_digest(expected, signature or "")


def _ticket_number() -> str:
    """TKT-<8 random alphanumeric>"""
    chars = string.ascii_uppercase + string.digits
    return "TKT-" + "".join(secrets.choice(chars) for _ in range(8))


# ─── Geo search ──────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine formula — great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearby_locations(lat: float, lng: float, radius_km: float = 5.0, city: str = None):
    """
    Return active ParkingLocation queryset sorted by distance.
    Uses Python-side Haversine (PostGIS can replace this once enabled).
    """
    qs = ParkingLocation.objects.filter(is_active=True)
    if city:
        qs = qs.filter(city__iexact=city)

    results = []
    for loc in qs.select_related("owner"):
        dist = haversine_km(lat, lng, float(loc.latitude), float(loc.longitude))
        if dist <= radius_km:
            results.append((dist, loc))

    results.sort(key=lambda x: x[0])
    return results  # list of (distance_km, ParkingLocation)


# ─── Slot availability ────────────────────────────────────────────────────────

def get_slot_availability(location_id: int):
    """
    Return slots grouped by zone for a location.
    Each slot includes status, type, rate.
    """
    slots = (
        ParkingSlot.objects.filter(
            zone__location_id=location_id,
            zone__is_active=True,
            is_active=True,
        )
        .select_related("zone")
        .order_by("zone__floor_level", "zone__display_order", "slot_code")
    )
    return slots


# ─── Price estimation ─────────────────────────────────────────────────────────

def estimate_price(location_id: int, vehicle_type: str, duration_hours: float) -> dict:
    """Return price estimate dict for given location, vehicle type and duration."""
    try:
        rate = ParkingRate.objects.get(
            location_id=location_id,
            vehicle_type=vehicle_type,
            is_active=True,
        )
    except ParkingRate.DoesNotExist:
        return {"amount": 0, "currency": "INR", "breakdown": "No rate configured"}

    duration_minutes = int(duration_hours * 60)
    amount = rate.estimate(duration_minutes)
    return {
        "amount": float(amount),
        "currency": "INR",
        "base_rate": float(rate.base_rate),
        "per_hour_rate": float(rate.per_hour_rate),
        "grace_minutes": rate.grace_minutes,
        "daily_cap": float(rate.daily_cap) if rate.daily_cap else None,
        "duration_hours": duration_hours,
        "breakdown": f"₹{rate.base_rate} base + ₹{rate.per_hour_rate}/hr for {duration_hours:.1f}h",
    }


# ─── Booking creation ─────────────────────────────────────────────────────────

def create_booking(
    customer,
    slot_id: int,
    vehicle_number: str,
    vehicle_type: str,
    from_dt,
    to_dt,
    idempotency_key: str = None,
) -> ParkingBooking:
    """
    Create a parking booking.
    Uses SELECT FOR UPDATE on the slot to prevent race conditions.
    Deduplicates on idempotency_key if provided.

    Returns ParkingBooking on success.
    Raises ValueError on slot unavailable, insufficient voucher, or invalid input.
    """
    if idempotency_key:
        existing = ParkingBooking.objects.filter(
            customer=customer,
            slot_id=slot_id,
            status__in=[
                ParkingBooking.STATUS_PENDING,
                ParkingBooking.STATUS_CONFIRMED,
                ParkingBooking.STATUS_ACTIVE,
            ],
        ).filter(
            transactions__idempotency_key=idempotency_key,
        ).first()
        if existing:
            logger.info(
                "parking_booking_idempotent_replay",
                extra_data={"booking_ref": existing.booking_reference, "customer_id": customer.pk},
            )
            return existing

    with transaction.atomic():
        try:
            slot = ParkingSlot.objects.select_for_update(nowait=True).get(
                pk=slot_id, is_active=True
            )
        except ParkingSlot.DoesNotExist:
            raise ValueError("Slot not found or inactive.")
        except Exception:
            raise ValueError("Slot is currently being reserved. Please try again.")

        if slot.status not in (ParkingSlot.STATUS_AVAILABLE,):
            raise ValueError(f"Slot {slot.slot_code} is not available (status: {slot.status}).")

        # Estimate amount
        location = slot.zone.location
        try:
            rate = ParkingRate.objects.get(
                location=location, vehicle_type=vehicle_type, is_active=True
            )
            duration_minutes = int((to_dt - from_dt).total_seconds() / 60)
            estimated_amount = rate.estimate(duration_minutes)
        except ParkingRate.DoesNotExist:
            estimated_amount = Decimal("0")

        # Get customer profile snapshot
        profile = getattr(customer, "profile", None)
        customer_name = getattr(profile, "full_name", "") or customer.get_full_name() or customer.username
        customer_phone = getattr(profile, "phone", "") or ""
        customer_email = getattr(profile, "email", "") or customer.email or ""

        booking_reference = _generate_booking_reference()
        while ParkingBooking.objects.filter(booking_reference=booking_reference).exists():
            booking_reference = _generate_booking_reference()

        qr_signature = _sign_qr(booking_reference)
        qr_data = json.dumps({"ref": booking_reference, "sig": qr_signature})

        booking = ParkingBooking.objects.create(
            customer=customer,
            slot=slot,
            booking_reference=booking_reference,
            vehicle_number=vehicle_number.upper().strip(),
            vehicle_type=vehicle_type,
            from_dt=from_dt,
            to_dt=to_dt,
            estimated_amount=estimated_amount,
            status=ParkingBooking.STATUS_CONFIRMED,
            qr_data=qr_data,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
        )

        ParkingSession.objects.create(
            booking=booking,
            vehicle_number=booking.vehicle_number,
            state=ParkingSession.STATE_INITIATED,
            entry_method=ParkingSession.ENTRY_METHOD_QR,
        )

        # Reserve the slot
        slot.status = ParkingSlot.STATUS_RESERVED
        slot.save(update_fields=["status", "updated_at"])

        logger.info(
            "parking_booking_created",
            extra_data={
                "booking_ref": booking_reference,
                "customer_id": customer.pk,
                "slot_id": slot.pk,
                "amount": str(estimated_amount),
            },
        )
    return booking


# ─── Entry processing ─────────────────────────────────────────────────────────

def process_entry(
    booking_reference: str,
    qr_payload: str = None,
    otp: str = None,
    attendant=None,
    acting_user=None,
    entry_method_override: str | None = None,
) -> ParkingBooking:
    """
    Mark vehicle as entered. Validates QR when provided; otherwise only parking operators/staff
    may record manual entry at the location (acting_user).
    """
    try:
        booking = ParkingBooking.objects.select_related("slot", "slot__zone__location").get(
            booking_reference=booking_reference
        )
    except ParkingBooking.DoesNotExist:
        raise ValueError("Booking not found.")

    if booking.status not in (ParkingBooking.STATUS_CONFIRMED, ParkingBooking.STATUS_PENDING):
        raise ValueError(f"Cannot enter with booking status: {booking.status}")

    # Validate QR
    if entry_method_override:
        entry_method = entry_method_override
    elif qr_payload:
        try:
            payload = json.loads(qr_payload)
            ref = payload.get("ref", "")
            sig = payload.get("sig", "")
        except (json.JSONDecodeError, AttributeError):
            ref = qr_payload
            sig = qr_payload
        if ref != booking_reference or not verify_qr(booking_reference, sig):
            raise ValueError("Invalid or tampered QR code.")
        entry_method = ParkingSession.ENTRY_METHOD_QR
    else:
        # No QR: only operators at this location or Django staff may enter manually.
        if acting_user is None:
            raise ValueError("Authentication required.")
        loc_id = booking.slot.zone.location_id
        from portal.models.parking import ParkingOperator

        is_staff = getattr(acting_user, "is_staff", False)
        is_operator = ParkingOperator.objects.filter(
            user=acting_user, location_id=loc_id, is_active=True
        ).exists()
        if not (is_operator or is_staff):
            raise ValueError("Scan your booking QR to enter, or ask parking staff for assistance.")
        entry_method = ParkingSession.ENTRY_METHOD_MANUAL
        if otp:
            logger.info(
                "parking_entry_otp_ignored",
                extra_data={"booking_ref": booking_reference, "note": "OTP not yet wired for manual customer entry"},
            )

    with transaction.atomic():
        now = timezone.now()
        booking.status = ParkingBooking.STATUS_ACTIVE
        booking.actual_entry_time = now
        booking.save(update_fields=["status", "actual_entry_time", "updated_at"])

        slot = ParkingBooking.objects.select_for_update().get(pk=booking.pk).slot
        ParkingSlot.objects.filter(pk=slot.pk).update(
            status=ParkingSlot.STATUS_OCCUPIED, updated_at=now
        )

        session, created = ParkingSession.objects.select_for_update().get_or_create(
            booking=booking,
            defaults={
                "vehicle_number": booking.vehicle_number,
                "entry_time": now,
                "entry_method": entry_method,
                "attendant": attendant,
                "state": ParkingSession.STATE_ENTERED,
            },
        )
        if not created:
            session.vehicle_number = booking.vehicle_number
            session.entry_time = now
            session.entry_method = entry_method
            if attendant:
                session.attendant = attendant
            session.state = ParkingSession.STATE_ENTERED
            session.save(
                update_fields=[
                    "vehicle_number",
                    "entry_time",
                    "entry_method",
                    "attendant",
                    "state",
                    "updated_at",
                ]
            )

        # Ensure ticket exists
        _ensure_ticket(booking)

    logger.info(
        "parking_entry_processed",
        extra_data={"booking_ref": booking_reference, "method": entry_method},
    )
    return booking


# ─── Exit processing ──────────────────────────────────────────────────────────

def process_exit(booking_reference: str, attendant=None, exit_method: str | None = None) -> dict:
    """
    Record vehicle exit.  Non-blocking: if voucher balance is insufficient the
    booking is NOT completed yet — caller receives { payment_required: True }.
    The exit is finalised by parking_payment_service once payment succeeds.

    Returns:
      { status: "completed", ... }              — exit done, no payment needed
      { status: "payment_required", due: X, voucher_balance: Y,
        voucher_sufficient: bool, ... }          — payment pending; use
                                                   parking_payment_service
    """
    try:
        booking = ParkingBooking.objects.select_related(
            "slot__zone__location", "customer"
        ).get(booking_reference=booking_reference)
    except ParkingBooking.DoesNotExist:
        raise ValueError("Booking not found.")

    if booking.status != ParkingBooking.STATUS_ACTIVE:
        raise ValueError(f"Cannot exit booking with status: {booking.status}")

    from portal.services.parking_payment_service import compute_exit_due, get_voucher_total_balance

    due_info = compute_exit_due(booking)
    due = due_info["due"]
    final_amount = due_info["final_amount"]
    overstay_amount = due_info["overstay_amount"]
    duration_minutes = due_info["duration_minutes"]
    entry_time = booking.actual_entry_time or booking.from_dt

    base_response = {
        "booking_reference": booking_reference,
        "entry_time": entry_time.isoformat(),
        "duration_minutes": duration_minutes,
        "final_amount": float(final_amount),
        "overstay_amount": float(overstay_amount),
        "currency": "INR",
    }

    if due <= Decimal("0"):
        # Already fully paid (e.g. pre-paid on booking, no overstay) — complete immediately
        from portal.services.parking_payment_service import _complete_exit

        em = exit_method or ParkingSession.ENTRY_METHOD_QR
        with transaction.atomic():
            result = _complete_exit(
                booking, attendant, due_info, payment_method="none", exit_method_code=em
            )
        logger.info("parking_exit_no_charge", extra_data={"booking_ref": booking_reference})
        return {**base_response, **result}

    # Check voucher balance
    voucher_balance = get_voucher_total_balance(booking.customer)
    voucher_sufficient = voucher_balance >= due

    logger.info(
        "parking_exit_payment_required",
        extra_data={
            "booking_ref": booking_reference,
            "due": str(due),
            "voucher_balance": str(voucher_balance),
            "voucher_sufficient": voucher_sufficient,
        },
    )

    with transaction.atomic():
        sess = ParkingSession.objects.select_for_update().filter(booking=booking).first()
        if sess:
            sess.state = ParkingSession.STATE_PAYMENT_PENDING
            sess.save(update_fields=["state", "updated_at"])

    return {
        **base_response,
        "status": "payment_required",
        "due": float(due),
        "voucher_balance": float(voucher_balance),
        "voucher_sufficient": voucher_sufficient,
        "has_parking_tx_pin": _has_parking_tx_pin(booking.customer),
        "payment_options": _build_payment_options(voucher_sufficient),
    }


def _has_parking_tx_pin(user) -> bool:
    from portal.models import ParkingTransactionPin
    return ParkingTransactionPin.objects.filter(user=user, is_active=True).exists()


def _build_payment_options(voucher_sufficient: bool) -> list:
    options = []
    if voucher_sufficient:
        options.append({"method": "voucher", "label": "Pay from Voucher (auto-debit)", "primary": True})
    options.append({"method": "upi", "label": "Pay via UPI", "primary": not voucher_sufficient})
    return options


def _get_already_charged(booking: ParkingBooking) -> Decimal:
    from django.db.models import Sum
    result = ParkingTransaction.objects.filter(
        booking=booking, status=ParkingTransaction.STATUS_SUCCESS
    ).aggregate(total=Sum("amount"))
    return result["total"] or Decimal("0")


def _charge_voucher(customer, booking: ParkingBooking, amount: Decimal, transaction_type: str = "charge"):
    """Debit Parkpe Voucher and record ParkingTransaction."""
    from portal.services.parkpe_voucherx_bridge import debit_voucher_balance

    idempotency_key = f"parking-{booking.booking_reference}-{transaction_type}"

    if ParkingTransaction.objects.filter(idempotency_key=idempotency_key, status=ParkingTransaction.STATUS_SUCCESS).exists():
        return ParkingTransaction.objects.filter(idempotency_key=idempotency_key).first()

    txn = ParkingTransaction.objects.create(
        booking=booking,
        amount=amount,
        payment_method=ParkingTransaction.METHOD_VOUCHER,
        idempotency_key=idempotency_key,
        transaction_type=transaction_type,
        status=ParkingTransaction.STATUS_PENDING,
    )
    try:
        debit_voucher_balance(
            user=customer,
            amount=amount,
            reference_id=idempotency_key,
            service_code="PARKING",
            description=f"Parking {booking.booking_reference}",
        )
        txn.status = ParkingTransaction.STATUS_SUCCESS
        txn.settled_at = timezone.now()
        txn.save(update_fields=["status", "settled_at", "updated_at"])
    except ValueError as e:
        txn.status = ParkingTransaction.STATUS_FAILED
        txn.failure_reason = str(e)
        txn.save(update_fields=["status", "failure_reason", "updated_at"])
        raise

    return txn


# ─── Ticket helpers ───────────────────────────────────────────────────────────

def _ensure_ticket(booking: ParkingBooking) -> ParkingTicket:
    """Create ParkingTicket if not exists. Does not send notifications."""
    ticket, created = ParkingTicket.objects.get_or_create(
        booking=booking,
        defaults={
            "ticket_number": _ticket_number(),
            "whatsapp_phone": booking.customer_phone,
            "email_address": booking.customer_email,
        },
    )
    if created:
        while ParkingTicket.objects.filter(ticket_number=ticket.ticket_number).exclude(pk=ticket.pk).exists():
            ticket.ticket_number = _ticket_number()
            ticket.save(update_fields=["ticket_number"])
    return ticket


def get_or_create_ticket(booking_reference: str) -> ParkingTicket:
    try:
        booking = ParkingBooking.objects.select_related("slot__zone__location", "customer").get(
            booking_reference=booking_reference
        )
    except ParkingBooking.DoesNotExist:
        raise ValueError("Booking not found.")
    return _ensure_ticket(booking)


# ─── Cancellation ─────────────────────────────────────────────────────────────

def cancel_booking(booking_reference: str, reason: str = "", cancelled_by=None) -> ParkingBooking:
    try:
        booking = ParkingBooking.objects.select_related("slot__zone__location").get(
            booking_reference=booking_reference
        )
    except ParkingBooking.DoesNotExist:
        raise ValueError("Booking not found.")

    if cancelled_by is not None:
        if booking.customer_id != cancelled_by.id:
            if getattr(cancelled_by, "is_staff", False):
                pass
            else:
                from portal.models.parking import ParkingOperator

                if not ParkingOperator.objects.filter(
                    user=cancelled_by,
                    location=booking.slot.zone.location,
                    is_active=True,
                ).exists():
                    raise PermissionDenied(detail="Not authorized to cancel this booking.")

    if booking.status not in (ParkingBooking.STATUS_PENDING, ParkingBooking.STATUS_CONFIRMED):
        raise ValueError(f"Cannot cancel booking with status: {booking.status}")

    with transaction.atomic():
        booking.status = ParkingBooking.STATUS_CANCELLED
        booking.cancellation_reason = reason
        booking.save(update_fields=["status", "cancellation_reason", "updated_at"])

        ParkingSlot.objects.filter(pk=booking.slot_id).update(
            status=ParkingSlot.STATUS_AVAILABLE, updated_at=timezone.now()
        )

        ParkingSession.objects.filter(booking=booking).update(
            state=ParkingSession.STATE_ABORTED,
            updated_at=timezone.now(),
        )

    logger.info(
        "parking_booking_cancelled",
        extra_data={"booking_ref": booking_reference, "reason": reason},
    )
    return booking


# ─── Revenue rollup ───────────────────────────────────────────────────────────

def _update_revenue(location: ParkingLocation, date, amount: Decimal):
    """Upsert daily revenue record for a location."""
    commission_pct = DEFAULT_COMMISSION_PCT
    commission = (amount * commission_pct / Decimal("100")).quantize(Decimal("0.01"))
    net = amount - commission

    try:
        rev, created = ParkingRevenue.objects.get_or_create(
            location=location,
            date=date,
            defaults={
                "gross_revenue": amount,
                "commission_pct": commission_pct,
                "commission_amount": commission,
                "net_owner_amount": net,
                "total_bookings": 1,
            },
        )
        if not created:
            from django.db.models import F
            ParkingRevenue.objects.filter(pk=rev.pk).update(
                gross_revenue=F("gross_revenue") + amount,
                commission_amount=F("commission_amount") + commission,
                net_owner_amount=F("net_owner_amount") + net,
                total_bookings=F("total_bookings") + 1,
                updated_at=timezone.now(),
            )
    except Exception as e:
        logger.warning("parking_revenue_update_failed", extra_data={"error": str(e)})


# ─── Owner dashboard data ─────────────────────────────────────────────────────

def get_owner_revenue_summary(location_id: int, days: int = 30) -> dict:
    """Return revenue summary for last N days."""
    from django.db.models import Sum, Count
    from datetime import date
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)

    records = ParkingRevenue.objects.filter(
        location_id=location_id,
        date__range=[start_date, end_date],
    ).order_by("date")

    aggregated = records.aggregate(
        total_gross=Sum("gross_revenue"),
        total_net=Sum("net_owner_amount"),
        total_commission=Sum("commission_amount"),
        total_bookings=Sum("total_bookings"),
    )

    daily = list(records.values("date", "gross_revenue", "net_owner_amount", "total_bookings"))

    return {
        "location_id": location_id,
        "period_days": days,
        "from_date": start_date.isoformat(),
        "to_date": end_date.isoformat(),
        "total_gross_revenue": float(aggregated["total_gross"] or 0),
        "total_net_revenue": float(aggregated["total_net"] or 0),
        "total_commission": float(aggregated["total_commission"] or 0),
        "total_bookings": aggregated["total_bookings"] or 0,
        "daily": [
            {
                "date": str(d["date"]),
                "gross_revenue": float(d["gross_revenue"]),
                "net_revenue": float(d["net_owner_amount"]),
                "bookings": d["total_bookings"],
            }
            for d in daily
        ],
    }
