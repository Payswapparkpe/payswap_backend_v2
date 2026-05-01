"""
Parking Payment Service
Handles overstay/exit payment via:
  1. Multi-voucher auto-debit (using profile-level transaction PIN — no per-voucher PIN needed)
  2. Cashfree UPI payment order creation + real-time status polling
  3. Webhook processing from Cashfree on UPI payment completion

Flow:
  process_exit (non-blocking) → compute_exit_due → if due > 0:
      a. try_voucher_autodebit(booking, pin) → success? → complete_exit()
      b. else create_upi_exit_order(booking) → UPI QR/link → poll/webhook → complete_exit()
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from decimal import Decimal

import bcrypt
from django.db import transaction
from django.utils import timezone

from portal.models import (
    GiftVoucher,
    ParkingBooking,
    ParkingExitPayment,
    ParkingRate,
    ParkingSession,
    ParkingSlot,
    ParkingTransaction,
    ParkingTransactionPin,
    VehicleFasTagMapping,
)
from portal.services.fastag_service import InsufficientFasTagBalance, deduct_wallet
from portal.services.parkpe_voucherx_bridge import _get_parkpe_brand_id
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.parking_payment")

UPI_ORDER_TTL_MINUTES = 15


# ─── Transaction PIN management ───────────────────────────────────────────────

def set_parking_tx_pin(user, raw_pin: str) -> None:
    """Hash and store (or update) a user's parking transaction PIN."""
    raw_pin = raw_pin.strip()
    if not (4 <= len(raw_pin) <= 6) or not raw_pin.isdigit():
        raise ValueError("PIN must be 4–6 digits.")
    hashed = bcrypt.hashpw(raw_pin.encode(), bcrypt.gensalt()).decode()
    ParkingTransactionPin.objects.update_or_create(
        user=user,
        defaults={"pin_hash": hashed, "is_active": True, "failed_attempts": 0, "locked_until": None},
    )


def verify_parking_tx_pin(user, raw_pin: str) -> bool:
    """
    Verify PIN; enforce lock-out after 5 failed attempts (15 min lock).
    Returns True if PIN is correct and account is not locked.
    Raises ValueError on locked account or wrong PIN (with attempt count).
    """
    try:
        rec = ParkingTransactionPin.objects.get(user=user, is_active=True)
    except ParkingTransactionPin.DoesNotExist:
        raise ValueError("Parking transaction PIN not set. Please set it from your profile.")

    now = timezone.now()
    if rec.locked_until and rec.locked_until > now:
        remaining = int((rec.locked_until - now).total_seconds() / 60) + 1
        raise ValueError(f"PIN locked. Try again in {remaining} minute(s).")

    ok = bcrypt.checkpw(raw_pin.encode(), rec.pin_hash.encode())
    if ok:
        if rec.failed_attempts:
            rec.failed_attempts = 0
            rec.locked_until = None
            rec.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        return True

    rec.failed_attempts += 1
    if rec.failed_attempts >= 5:
        rec.locked_until = now + timedelta(minutes=15)
        rec.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        raise ValueError("Too many wrong PINs. Locked for 15 minutes.")
    rec.save(update_fields=["failed_attempts", "updated_at"])
    remaining_tries = 5 - rec.failed_attempts
    raise ValueError(f"Wrong PIN. {remaining_tries} attempt(s) left.")


# ─── Exit amount computation ───────────────────────────────────────────────────

def compute_exit_due(booking: ParkingBooking) -> dict:
    """
    Compute how much is still owed for a booking at current time.
    Returns dict with: final_amount, already_paid, due, overstay_amount, duration_minutes.
    Does NOT mutate the booking.
    """
    now = timezone.now()
    entry_time = booking.actual_entry_time or booking.from_dt
    duration_minutes = max(0, int((now - entry_time).total_seconds() / 60))

    location = booking.slot.zone.location
    try:
        rate = ParkingRate.objects.get(location=location, vehicle_type=booking.vehicle_type, is_active=True)
        final_amount = rate.compute_exact_charge(entry_time, now)
    except ParkingRate.DoesNotExist:
        final_amount = booking.estimated_amount

    from django.db.models import Sum
    already_paid = ParkingTransaction.objects.filter(
        booking=booking, status=ParkingTransaction.STATUS_SUCCESS
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    due = max(Decimal("0"), final_amount - already_paid)
    overstay = max(Decimal("0"), final_amount - booking.estimated_amount)

    return {
        "final_amount": final_amount,
        "already_paid": already_paid,
        "due": due,
        "overstay_amount": overstay,
        "duration_minutes": duration_minutes,
    }


# ─── Voucher availability ──────────────────────────────────────────────────────

def deduct_fastag_payment(
    booking_id,
    amount: Decimal,
    idempotency_key: str,
    mapping: VehicleFasTagMapping,
) -> str:
    """
    ACID-safe FASTag deduction with booking row lock and idempotent replay.
    Returns 'already_charged' | 'charged'. Raises InsufficientFasTagBalance on failure.
    """
    with transaction.atomic():
        booking = ParkingBooking.objects.select_for_update().get(pk=booking_id)

        if ParkingTransaction.objects.filter(
            booking=booking,
            idempotency_key=idempotency_key,
            status=ParkingTransaction.STATUS_SUCCESS,
        ).exists():
            return "already_charged"

        txn = ParkingTransaction.objects.create(
            booking=booking,
            amount=amount,
            payment_method=ParkingTransaction.METHOD_FASTAG,
            idempotency_key=idempotency_key,
            status=ParkingTransaction.STATUS_PENDING,
        )

        result = deduct_wallet(mapping.fastag_wallet_id, amount, str(txn.pk))

        if result.success:
            txn.status = ParkingTransaction.STATUS_SUCCESS
            txn.gateway_reference = result.reference
            txn.settled_at = timezone.now()
            txn.save(update_fields=["status", "gateway_reference", "settled_at", "updated_at"])
            return "charged"

        txn.status = ParkingTransaction.STATUS_FAILED
        txn.failure_reason = result.error or "FASTag deduction failed"
        txn.save(update_fields=["status", "failure_reason", "updated_at"])
        raise InsufficientFasTagBalance(result.error or "FASTag deduction failed")


def get_voucher_total_balance(user) -> Decimal:
    """Sum of all active Parkpe vouchers for this user."""
    brand_id = _get_parkpe_brand_id()
    if not brand_id:
        return Decimal("0")
    from django.db.models import Sum
    result = GiftVoucher.objects.filter(
        brand_id=brand_id,
        metadata__parkpe_user_id=user.pk,
        status__in=["ACTIVE", "PARTIALLY_REDEEMED"],
    ).aggregate(total=Sum("current_balance"))
    return result["total"] or Decimal("0")


# ─── Multi-voucher auto-debit ──────────────────────────────────────────────────

def _debit_multi_voucher(
    user, booking: ParkingBooking, amount: Decimal, transaction_type: str
) -> ParkingTransaction:
    """
    Debit `amount` across multiple vouchers (oldest first, largest-balance-first fallback).
    Uses pre-stored encrypted PIN per voucher — no per-voucher PIN entry needed at gate.
    """
    from portal.services.voucher_service import VoucherService
    from portal.utils.encryption import decrypt_data

    brand_id = _get_parkpe_brand_id()
    if not brand_id:
        raise ValueError("Parkpe voucher brand not configured.")

    vouchers = list(
        GiftVoucher.objects.filter(
            brand_id=brand_id,
            metadata__parkpe_user_id=user.pk,
            status__in=["ACTIVE", "PARTIALLY_REDEEMED"],
            current_balance__gt=Decimal("0"),
        ).order_by("-current_balance", "id")
    )

    total_available = sum(v.current_balance for v in vouchers)
    if total_available < amount:
        raise ValueError(
            f"Insufficient voucher balance. Available: ₹{total_available:.2f}, Required: ₹{amount:.2f}"
        )

    idempotency_key = f"parking-{booking.booking_reference}-{transaction_type}-multi"
    existing = ParkingTransaction.objects.filter(
        idempotency_key=idempotency_key, status=ParkingTransaction.STATUS_SUCCESS
    ).first()
    if existing:
        return existing

    txn = ParkingTransaction.objects.create(
        booking=booking,
        amount=amount,
        payment_method=ParkingTransaction.METHOD_VOUCHER,
        idempotency_key=idempotency_key,
        transaction_type=transaction_type,
        status=ParkingTransaction.STATUS_PENDING,
    )

    voucher_svc = VoucherService()
    remaining = amount
    try:
        for voucher in vouchers:
            if remaining <= Decimal("0"):
                break
            debit = min(remaining, voucher.current_balance)
            pin = None
            if voucher.metadata and voucher.metadata.get("encrypted_pin"):
                try:
                    pin = decrypt_data(voucher.metadata["encrypted_pin"])
                except Exception:
                    continue
            if not pin:
                continue
            voucher_svc.redeem_voucher_pin(
                voucher_code=voucher.voucher_code,
                pin=pin,
                amount=debit,
                transaction_ref=f"{idempotency_key}-{voucher.id}",
            )
            remaining -= debit

        if remaining > Decimal("0.01"):
            raise ValueError("Could not fully debit vouchers — partial debit, rolling back.")

        txn.status = ParkingTransaction.STATUS_SUCCESS
        txn.settled_at = timezone.now()
        txn.save(update_fields=["status", "settled_at", "updated_at"])
        return txn

    except Exception as e:
        txn.status = ParkingTransaction.STATUS_FAILED
        txn.failure_reason = str(e)
        txn.save(update_fields=["status", "failure_reason", "updated_at"])
        raise


# ─── Try voucher auto-debit for exit ──────────────────────────────────────────

def try_voucher_exit_payment(booking: ParkingBooking, raw_pin: str, attendant=None) -> dict:
    """
    Called when operator/customer wants to pay exit via voucher.
    Verifies profile PIN, checks voucher balance, debits, then completes exit.
    Returns summary dict.
    """
    verify_parking_tx_pin(booking.customer, raw_pin)

    with transaction.atomic():
        booking = ParkingBooking.objects.select_for_update().select_related(
            "slot__zone__location", "customer"
        ).get(pk=booking.pk)

        due_info = compute_exit_due(booking)
        due = due_info["due"]

        if due <= Decimal("0"):
            return _complete_exit_no_charge(booking, attendant, due_info)

        available = get_voucher_total_balance(booking.customer)
        if available < due:
            raise ValueError(
                f"Voucher balance ₹{available:.2f} is less than amount due ₹{due:.2f}. Use UPI to pay."
            )

        _debit_multi_voucher(
            user=booking.customer,
            booking=booking,
            amount=due,
            transaction_type="overstay" if due_info["overstay_amount"] > 0 else "charge",
        )
        result = _complete_exit(booking, attendant, due_info, payment_method="voucher")

    logger.info("parking_voucher_exit_paid", extra_data={"booking_ref": booking.booking_reference, "amount": str(due)})
    return result


# ─── Cashfree UPI exit order ───────────────────────────────────────────────────

def create_upi_exit_order(booking: ParkingBooking) -> dict:
    """
    Creates a Cashfree UPI payment order for the pending exit amount.
    Returns: cf_order_id, upi_link, upi_qr_data, amount, expires_at, exit_payment_id.
    """
    due_info = compute_exit_due(booking)
    due = due_info["due"]
    if due <= Decimal("0"):
        raise ValueError("No amount due for this booking exit.")

    # Expire any old pending UPI orders for this booking
    ParkingExitPayment.objects.filter(
        booking=booking, status=ParkingExitPayment.STATUS_PENDING, method=ParkingExitPayment.METHOD_UPI
    ).update(status=ParkingExitPayment.STATUS_EXPIRED)

    cf_order_id = f"PKPEXIT-{booking.booking_reference}-{uuid.uuid4().hex[:8].upper()}"
    expires_at = timezone.now() + timedelta(minutes=UPI_ORDER_TTL_MINUTES)

    exit_payment = ParkingExitPayment.objects.create(
        booking=booking,
        amount=due,
        method=ParkingExitPayment.METHOD_UPI,
        status=ParkingExitPayment.STATUS_PENDING,
        cf_order_id=cf_order_id,
        expires_at=expires_at,
    )

    try:
        from portal.services.vendors.cashfree_pg import CashfreePGClient
        cf = CashfreePGClient()

        phone = (booking.customer_phone or "9999999999").replace("+91", "").replace(" ", "")[-10:]
        result = cf.create_order(
            order_amount=float(due),
            order_currency="INR",
            order_id=cf_order_id,
            customer_details={
                "customer_id": f"CUST-{booking.customer_id}",
                "customer_phone": phone,
                "customer_email": booking.customer_email or "noreply@parkpe.in",
                "customer_name": booking.customer_name or "Customer",
            },
            order_meta={
                "return_url": f"https://parkpe.in/parking/exit-payment/{exit_payment.pk}/status",
                "notify_url": f"https://parkpe.in/api/parking/webhooks/cashfree/",
            },
            order_note=f"Parking exit {booking.booking_reference}",
            order_tags={"booking_ref": booking.booking_reference, "exit_payment_id": str(exit_payment.pk)},
        )

        session_id = result.get("payment_session_id") or result.get("cf_payment_session_id") or ""
        upi_link = _build_upi_link(cf_order_id, float(due), booking)

        exit_payment.cf_payment_session_id = session_id
        exit_payment.upi_link = upi_link
        exit_payment.upi_qr_data = upi_link
        exit_payment.save(update_fields=["cf_payment_session_id", "upi_link", "upi_qr_data", "updated_at"])

    except Exception as e:
        logger.warning("parking_upi_order_creation_failed", extra_data={"booking_ref": booking.booking_reference, "error": str(e)})
        # Still return the record — frontend can poll/retry
        upi_link = _build_upi_link(cf_order_id, float(due), booking)
        exit_payment.upi_link = upi_link
        exit_payment.upi_qr_data = upi_link
        exit_payment.save(update_fields=["upi_link", "upi_qr_data", "updated_at"])

    return {
        "exit_payment_id": exit_payment.pk,
        "cf_order_id": cf_order_id,
        "amount": float(due),
        "upi_link": exit_payment.upi_link,
        "upi_qr_data": exit_payment.upi_qr_data,
        "expires_at": expires_at.isoformat(),
        "payment_session_id": exit_payment.cf_payment_session_id,
        "currency": "INR",
    }


def _build_upi_link(order_id: str, amount: float, booking: ParkingBooking) -> str:
    """Build a UPI deep-link URI usable as a QR payload."""
    from core.config import payswap_config
    vpa = getattr(payswap_config, "PARKING_UPI_VPA", "parkpe@cashfree")
    name = "Parkpe Parking"
    note = f"Exit {booking.booking_reference}"
    return f"upi://pay?pa={vpa}&pn={name}&am={amount:.2f}&cu=INR&tn={note}&tr={order_id}"


# ─── Poll/check UPI payment status ────────────────────────────────────────────

def escalate_exit_payment_to_disputed(ep: ParkingExitPayment) -> None:
    """After UPI exit window lapses with no payment — surface dispute for manual gate handling."""
    with transaction.atomic():
        ep_locked = ParkingExitPayment.objects.select_for_update().get(pk=ep.pk)
        if ep_locked.status != ParkingExitPayment.STATUS_PENDING:
            return
        ep_locked.status = ParkingExitPayment.STATUS_EXPIRED
        ep_locked.save(update_fields=["status", "updated_at"])

        sess = (
            ParkingSession.objects.select_for_update()
            .filter(booking=ep_locked.booking)
            .first()
        )
        if sess:
            msg = "UPI exit payment expired — attendant review required."
            sess.notes = f"{sess.notes}\n{msg}".strip() if sess.notes else msg
            sess.state = ParkingSession.STATE_DISPUTED
            sess.save(update_fields=["notes", "state", "updated_at"])


def check_upi_payment_status(exit_payment_id: int) -> dict:
    """
    Poll Cashfree for payment status of an exit payment order.
    If paid → complete the booking exit automatically.
    Returns: { status, paid, amount, booking_reference, ... }
    """
    try:
        ep = ParkingExitPayment.objects.select_related("booking").get(pk=exit_payment_id)
    except ParkingExitPayment.DoesNotExist:
        raise ValueError("Exit payment record not found.")

    if ep.status == ParkingExitPayment.STATUS_PAID:
        return {"status": "paid", "paid": True, "amount": float(ep.amount), "booking_reference": ep.booking.booking_reference}

    if ep.status in (ParkingExitPayment.STATUS_EXPIRED, ParkingExitPayment.STATUS_FAILED):
        return {"status": ep.status, "paid": False, "amount": float(ep.amount), "booking_reference": ep.booking.booking_reference}

    # Auto-expire → escalate session to disputed for attendant resolution
    if ep.expires_at and timezone.now() > ep.expires_at:
        escalate_exit_payment_to_disputed(ep)
        return {"status": "expired", "paid": False, "amount": float(ep.amount), "booking_reference": ep.booking.booking_reference}

    # Poll Cashfree
    if ep.cf_order_id:
        try:
            from portal.services.vendors.cashfree_pg import CashfreePGClient
            cf = CashfreePGClient()
            order_data = cf.get_order(ep.cf_order_id)
            cf_status = (order_data.get("order_status") or "").upper()
            if cf_status == "PAID":
                _mark_upi_exit_paid(ep)
                return {"status": "paid", "paid": True, "amount": float(ep.amount), "booking_reference": ep.booking.booking_reference}
        except Exception as ex:
            logger.warning("parking_upi_status_poll_failed", extra_data={"exit_payment_id": exit_payment_id, "error": str(ex)})

    return {"status": "pending", "paid": False, "amount": float(ep.amount), "booking_reference": ep.booking.booking_reference}


def _mark_upi_exit_paid(ep: ParkingExitPayment) -> None:
    """Mark exit payment as paid and complete the booking exit."""
    with transaction.atomic():
        ep.status = ParkingExitPayment.STATUS_PAID
        ep.paid_at = timezone.now()
        ep.save(update_fields=["status", "paid_at", "updated_at"])

        # Record ParkingTransaction
        txn = ParkingTransaction.objects.create(
            booking=ep.booking,
            amount=ep.amount,
            payment_method=ParkingTransaction.METHOD_PG,
            idempotency_key=ep.cf_order_id,
            transaction_type="overstay" if ep.amount > 0 else "charge",
            status=ParkingTransaction.STATUS_SUCCESS,
            gateway_reference=ep.cf_order_id,
            settled_at=timezone.now(),
        )
        ep.parking_transaction = txn
        ep.save(update_fields=["parking_transaction"])

        due_info = compute_exit_due(ep.booking)
        _complete_exit(ep.booking, attendant=None, due_info=due_info, payment_method="upi")


# ─── Cashfree webhook processing ──────────────────────────────────────────────

def process_cashfree_webhook(payload: dict, signature: str = None) -> dict:
    """
    Process Cashfree payment webhook for parking exit payments.
    Called from the webhook view.
    """
    order_id = payload.get("data", {}).get("order", {}).get("order_id") or payload.get("order_id", "")
    if not order_id or not order_id.startswith("PKPEXIT-"):
        return {"processed": False, "reason": "not_parking_exit"}

    ep = ParkingExitPayment.objects.filter(cf_order_id=order_id).first()
    if not ep:
        return {"processed": False, "reason": "exit_payment_not_found"}

    ep.webhook_data = payload
    ep.save(update_fields=["webhook_data", "updated_at"])

    event_type = payload.get("type", "") or payload.get("event_type", "")
    payment_status = (
        payload.get("data", {}).get("payment", {}).get("payment_status")
        or payload.get("payment_status", "")
    ).upper()

    if payment_status == "SUCCESS" or event_type == "PAYMENT_SUCCESS_WEBHOOK":
        if ep.status != ParkingExitPayment.STATUS_PAID:
            _mark_upi_exit_paid(ep)
        return {"processed": True, "status": "paid", "order_id": order_id}

    if payment_status in ("FAILED", "USER_DROPPED"):
        ep.status = ParkingExitPayment.STATUS_FAILED
        ep.save(update_fields=["status", "updated_at"])
        return {"processed": True, "status": "failed", "order_id": order_id}

    return {"processed": True, "status": "no_action", "order_id": order_id}


# ─── Shared exit completion helpers ───────────────────────────────────────────

def _complete_exit(
    booking: ParkingBooking,
    attendant,
    due_info: dict,
    payment_method: str,
    exit_method_code: str | None = None,
) -> dict:
    """Finalise booking exit: set status=completed, release slot, update session, rollup revenue."""
    from portal.services.parking_service import _update_revenue

    now = timezone.now()
    final_amount = due_info["final_amount"]

    if exit_method_code is None:
        if payment_method == "upi":
            exit_method_code = ParkingSession.ENTRY_METHOD_QR
        elif payment_method == "voucher":
            exit_method_code = ParkingSession.ENTRY_METHOD_APP
        elif payment_method == "fastag":
            exit_method_code = ParkingSession.ENTRY_METHOD_FASTAG
        elif payment_method == "none":
            exit_method_code = ParkingSession.ENTRY_METHOD_QR
        else:
            exit_method_code = ParkingSession.ENTRY_METHOD_MANUAL

    booking.actual_exit_time = now
    booking.final_amount = final_amount
    booking.status = ParkingBooking.STATUS_COMPLETED
    booking.save(update_fields=["actual_exit_time", "final_amount", "status", "updated_at"])

    ParkingSlot.objects.filter(pk=booking.slot_id).update(
        status=ParkingSlot.STATUS_AVAILABLE, updated_at=now
    )
    ParkingSession.objects.filter(booking=booking).update(
        exit_time=now,
        exit_method=exit_method_code,
        state=ParkingSession.STATE_COMPLETED,
        updated_at=now,
    )
    _update_revenue(location=booking.slot.zone.location, date=now.date(), amount=final_amount)

    return {
        "booking_reference": booking.booking_reference,
        "entry_time": (booking.actual_entry_time or booking.from_dt).isoformat(),
        "exit_time": now.isoformat(),
        "duration_minutes": due_info["duration_minutes"],
        "final_amount": float(final_amount),
        "overstay_amount": float(due_info["overstay_amount"]),
        "payment_method": payment_method,
        "currency": "INR",
        "status": "completed",
    }


def _complete_exit_no_charge(booking: ParkingBooking, attendant, due_info: dict) -> dict:
    return _complete_exit(booking, attendant, due_info, payment_method="none")
