"""
Parking API Views — Parkpe Smart Parking Platform
All views use JWT authentication (JWTAuthentication + IsAuthenticated).
Response shapes match frontend/projects/parkpe/src/app/core/models/parking.model.ts
"""
from datetime import datetime
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from api.permissions import IsCustomerPortal, IsParkingRole
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from portal.models import (
    ParkingLocation,
    ParkingSlot,
    ParkingZone,
    ParkingRate,
    ParkingBooking,
    ParkingOperator,
    ParkingExitPayment,
    User,
    Profile,
    VehicleFasTagMapping,
)
from portal.services import parking_service, parking_notification_service
from portal.utils.logging_helper import get_logger

logger = get_logger(__name__)

PARKING_ROLE_PRIORITY = {
    ParkingOperator.ROLE_ATTENDANT: 1,
    ParkingOperator.ROLE_MANAGER: 2,
    ParkingOperator.ROLE_OWNER: 3,
}


def _operator_for_location(user, location_id):
    return ParkingOperator.objects.filter(
        user=user,
        location_id=location_id,
        is_active=True,
    ).first()


def _has_location_access(user, location_id):
    return _operator_for_location(user, location_id) is not None


def _has_owner_access(user, location_id):
    op = _operator_for_location(user, location_id)
    return bool(op and op.role == ParkingOperator.ROLE_OWNER)


def _has_owner_or_manager_access(user, location_id):
    op = _operator_for_location(user, location_id)
    return bool(op and op.role in {ParkingOperator.ROLE_OWNER, ParkingOperator.ROLE_MANAGER})


def _assert_booking_action_allowed(request, booking: ParkingBooking) -> None:
    """Customer of the booking, operator at that location, or staff."""
    if request.user.is_staff:
        return
    if booking.customer_id == request.user.id:
        return
    loc_id = booking.slot.zone.location_id
    if _has_location_access(request.user, loc_id):
        return
    raise PermissionDenied(detail="You are not allowed to perform this action on this booking.")


def _serialize_operator(op: ParkingOperator) -> dict:
    profile = getattr(op.user, "profile", None)
    name = (
        (getattr(profile, "full_name", "") or "").strip()
        or (getattr(profile, "first_name", "") or "").strip()
        or op.user.username
    )
    email = (getattr(profile, "email", "") or op.user.email or "").strip()
    phone = (getattr(profile, "phone", "") or "").strip()
    return {
        "id": op.id,
        "userId": op.user_id,
        "username": op.user.username,
        "name": name,
        "email": email,
        "phone": phone,
        "locationId": op.location_id,
        "locationName": op.location.name,
        "role": op.role,
        "isActive": op.is_active,
        "hubAssignmentId": op.hub_assignment_id,
        "createdAt": op.created_at.isoformat() if op.created_at else None,
    }


# ─── Serializer helpers (inline — no DRF serializers to keep consistent with BBPS style) ──

def _serialize_location(loc: ParkingLocation, include_slots: bool = False) -> dict:
    available = (
        ParkingSlot.objects.filter(zone__location=loc, status=ParkingSlot.STATUS_AVAILABLE, is_active=True).count()
    )
    rates = list(
        ParkingRate.objects.filter(location=loc, is_active=True).values(
            "vehicle_type", "per_hour_rate", "base_rate", "grace_minutes", "daily_cap"
        )
    )
    return {
        "id": str(loc.pk),
        "name": loc.name,
        "address": loc.address,
        "city": loc.city,
        "state": loc.state,
        "postalCode": loc.postal_code,
        "slotsCount": loc.total_slots,
        "availableSlots": available,
        "coordinates": {"latitude": float(loc.latitude), "longitude": float(loc.longitude)},
        "amenities": loc.amenities or [],
        "openingHours": loc.opening_hours or {},
        "description": loc.description,
        "images": loc.images or [],
        "rates": [
            {
                "durationType": "hourly",
                "amount": float(r["per_hour_rate"]),
                "currency": "INR",
                "description": f"{r['vehicle_type'].replace('_', ' ').title()} — ₹{r['per_hour_rate']}/hr",
            }
            for r in rates
        ],
    }


def _serialize_slot(slot: ParkingSlot) -> dict:
    return {
        "id": str(slot.pk),
        "locationId": str(slot.zone.location_id),
        "code": slot.slot_code,
        "available": slot.status == ParkingSlot.STATUS_AVAILABLE,
        "status": slot.status,
        "vehicleType": slot.vehicle_type,
        "rate": slot.rate,
        "currency": "INR",
        "features": slot.features or [],
        "zoneId": str(slot.zone_id),
        "zoneName": slot.zone.zone_name,
        "floorLevel": slot.zone.floor_level,
        "zoneType": slot.zone.zone_type,
    }


def _serialize_booking(booking: ParkingBooking) -> dict:
    ticket_number = None
    ticket_pdf_url = None
    qr_image_url = None
    try:
        t = booking.ticket
        ticket_number = t.ticket_number
        ticket_pdf_url = t.pdf_url or None
        qr_image_url = t.qr_image_url or None
    except Exception:
        pass

    return {
        "id": str(booking.pk),
        "bookingReference": booking.booking_reference,
        "locationId": str(booking.slot.zone.location_id),
        "locationName": booking.location_name,
        "slotId": str(booking.slot_id),
        "slotCode": booking.slot_code,
        "vehicleNumber": booking.vehicle_number,
        "vehicleType": booking.vehicle_type,
        "from": booking.from_dt.isoformat(),
        "to": booking.to_dt.isoformat(),
        "duration": booking.duration_minutes,
        "amount": float(booking.final_amount or booking.estimated_amount),
        "estimatedAmount": float(booking.estimated_amount),
        "finalAmount": float(booking.final_amount) if booking.final_amount else None,
        "currency": booking.currency,
        "status": booking.status,
        "customer": {
            "name": booking.customer_name,
            "phone": booking.customer_phone,
            "email": booking.customer_email,
        },
        "qrCode": booking.qr_data or None,
        "qrImageUrl": qr_image_url,
        "ticketNumber": ticket_number,
        "ticketPdfUrl": ticket_pdf_url,
        "paymentId": None,
        "createdAt": booking.created_at.isoformat(),
        "actualEntryTime": booking.actual_entry_time.isoformat() if booking.actual_entry_time else None,
        "actualExitTime": booking.actual_exit_time.isoformat() if booking.actual_exit_time else None,
    }


# ─── Location Views ────────────────────────────────────────────────────────────

class ParkingLocationListView(APIView):
    """GET /api/parking/locations/ — list or geo-search parking locations."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]

    def get(self, request):
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        radius = request.query_params.get("radius_km", "5")
        city = request.query_params.get("city")

        if lat and lng:
            try:
                results = parking_service.find_nearby_locations(
                    lat=float(lat),
                    lng=float(lng),
                    radius_km=float(radius),
                    city=city,
                )
                data = []
                for dist, loc in results:
                    d = _serialize_location(loc)
                    d["distanceKm"] = round(dist, 2)
                    data.append(d)
            except (ValueError, TypeError) as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            qs = ParkingLocation.objects.filter(is_active=True).select_related("owner")
            if city:
                qs = qs.filter(city__iexact=city)
            data = [_serialize_location(loc) for loc in qs]

        return Response({"locations": data, "count": len(data)})


class ParkingLocationDetailView(APIView):
    """GET /api/parking/locations/<id>/ — single location detail."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]

    def get(self, request, location_id):
        try:
            loc = ParkingLocation.objects.get(pk=location_id, is_active=True)
        except ParkingLocation.DoesNotExist:
            return Response({"detail": "Location not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_location(loc))


# ─── Slot Views ────────────────────────────────────────────────────────────────

class ParkingSlotListView(APIView):
    """GET /api/parking/locations/<id>/slots/ — real-time slot availability."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]

    def get(self, request, location_id):
        try:
            ParkingLocation.objects.get(pk=location_id, is_active=True)
        except ParkingLocation.DoesNotExist:
            return Response({"detail": "Location not found."}, status=status.HTTP_404_NOT_FOUND)

        vehicle_type = request.query_params.get("vehicle_type")
        slots_qs = parking_service.get_slot_availability(location_id)
        if vehicle_type:
            slots_qs = slots_qs.filter(vehicle_type=vehicle_type)

        slots = [_serialize_slot(s) for s in slots_qs]

        # Group by zone
        zones: dict = {}
        for s in slots_qs:
            zid = str(s.zone_id)
            if zid not in zones:
                zones[zid] = {
                    "id": zid,
                    "name": s.zone.zone_name,
                    "floor": s.zone.floor_level,
                    "type": s.zone.zone_type,
                    "available": 0,
                    "total": 0,
                }
            zones[zid]["total"] += 1
            if s.status == ParkingSlot.STATUS_AVAILABLE:
                zones[zid]["available"] += 1

        return Response({
            "locationId": str(location_id),
            "slots": slots,
            "zones": list(zones.values()),
            "totalSlots": len(slots),
            "availableSlots": sum(1 for s in slots_qs if s.status == ParkingSlot.STATUS_AVAILABLE),
        })


# ─── Price Estimate ────────────────────────────────────────────────────────────

class ParkingRateEstimateView(APIView):
    """GET /api/parking/rates/estimate/?location_id=&vehicle_type=&duration_hours="""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]

    def get(self, request):
        location_id = request.query_params.get("location_id")
        vehicle_type = request.query_params.get("vehicle_type", "four_wheeler")
        duration_hours = request.query_params.get("duration_hours", "1")

        if not location_id:
            return Response({"detail": "location_id required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            estimate = parking_service.estimate_price(
                location_id=int(location_id),
                vehicle_type=vehicle_type,
                duration_hours=float(duration_hours),
            )
        except (ValueError, TypeError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(estimate)


# ─── Booking Views ─────────────────────────────────────────────────────────────

class ParkingBookingCreateView(APIView):
    """POST /api/parking/bookings/ — create a booking."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]
    parser_classes = [JSONParser]

    def post(self, request):
        data = request.data
        required = ["slotId", "vehicleNumber", "vehicleType", "from", "to"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return Response(
                {"detail": f"Missing required fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from_dt = datetime.fromisoformat(data["from"].replace("Z", "+00:00"))
            to_dt = datetime.fromisoformat(data["to"].replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            return Response({"detail": f"Invalid date format: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        if from_dt >= to_dt:
            return Response({"detail": "End time must be after start time."}, status=status.HTTP_400_BAD_REQUEST)

        idempotency_key = (
            request.META.get("HTTP_X_IDEMPOTENCY_KEY")
            or request.META.get("HTTP_IDEMPOTENCY_KEY")
            or data.get("idempotencyKey")
        )

        try:
            booking = parking_service.create_booking(
                customer=request.user,
                slot_id=int(data["slotId"]),
                vehicle_number=data["vehicleNumber"],
                vehicle_type=data["vehicleType"],
                from_dt=from_dt,
                to_dt=to_dt,
                idempotency_key=idempotency_key,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("parking_booking_create_error", extra_data={"error": str(e)})
            return Response({"detail": "Booking failed. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Ensure ticket, send notifications async via Celery
        from portal.services.parking_service import _ensure_ticket
        ticket = _ensure_ticket(booking)

        try:
            from portal.tasks.parking_tasks import send_booking_notifications_task
            send_booking_notifications_task.delay(str(booking.pk))
        except Exception:
            # Fallback: send synchronously if Celery unavailable
            parking_notification_service.send_booking_confirmation_whatsapp(booking, ticket)
            parking_notification_service.send_booking_confirmation_email(booking, ticket)

        return Response(
            {"success": True, "booking": _serialize_booking(booking)},
            status=status.HTTP_201_CREATED,
        )


class ParkingBookingDetailView(APIView):
    """GET /api/parking/bookings/<ref>/ — booking detail."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_ref):
        try:
            booking = ParkingBooking.objects.select_related(
                "slot__zone__location", "customer"
            ).get(booking_reference=booking_ref)
        except ParkingBooking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
        if request.user.is_staff:
            return Response(_serialize_booking(booking))
        if booking.customer_id == request.user.id:
            return Response(_serialize_booking(booking))
        if _has_location_access(request.user, booking.slot.zone.location_id):
            return Response(_serialize_booking(booking))
        return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)


class ParkingBookingEntryView(APIView):
    """POST /api/parking/bookings/<ref>/entry/ — validate entry QR/OTP."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, booking_ref):
        try:
            booking = ParkingBooking.objects.select_related("slot__zone__location", "customer").get(
                booking_reference=booking_ref
            )
        except ParkingBooking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            _assert_booking_action_allowed(request, booking)
        except PermissionDenied as e:
            return Response({"detail": str(e.detail)}, status=status.HTTP_403_FORBIDDEN)

        qr_payload = request.data.get("qrPayload") or request.data.get("qr_payload")
        otp = request.data.get("otp")

        try:
            booking = parking_service.process_entry(
                booking_reference=booking_ref,
                qr_payload=qr_payload,
                otp=otp,
                acting_user=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "success": True,
            "message": f"Welcome! Slot {booking.slot_code} — entry recorded.",
            "entryTime": booking.actual_entry_time.isoformat(),
            "booking": _serialize_booking(booking),
        })


class ParkingBookingExitView(APIView):
    """POST /api/parking/bookings/<ref>/exit/ — record exit and finalize charge."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, booking_ref):
        try:
            booking = ParkingBooking.objects.select_related("slot__zone__location", "customer").get(
                booking_reference=booking_ref
            )
        except ParkingBooking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            _assert_booking_action_allowed(request, booking)
        except PermissionDenied as e:
            return Response({"detail": str(e.detail)}, status=status.HTTP_403_FORBIDDEN)

        try:
            summary = parking_service.process_exit(booking_reference=booking_ref)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("parking_exit_error", extra_data={"error": str(e)})
            return Response({"detail": "Exit processing failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Send exit receipt WhatsApp
        try:
            booking = ParkingBooking.objects.get(booking_reference=booking_ref)
            parking_notification_service.send_exit_receipt_whatsapp(booking)
        except Exception:
            pass

        return Response({"success": True, **summary})


class ParkingBookingCancelView(APIView):
    """POST /api/parking/bookings/<ref>/cancel/ — cancel booking."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, booking_ref):
        reason = request.data.get("reason", "")
        try:
            booking = parking_service.cancel_booking(
                booking_reference=booking_ref,
                reason=reason,
                cancelled_by=request.user,
            )
        except PermissionDenied as e:
            return Response({"detail": str(e.detail)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True, "booking": _serialize_booking(booking)})


class ParkingTicketResendView(APIView):
    """POST /api/parking/bookings/<ref>/ticket/resend/ — resend WhatsApp + Email."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]

    def post(self, request, booking_ref):
        # Verify ownership
        try:
            ParkingBooking.objects.get(booking_reference=booking_ref, customer=request.user)
        except ParkingBooking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = parking_notification_service.resend_ticket(booking_ref)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True, **result})


# ─── Customer History ──────────────────────────────────────────────────────────

class ParkingCustomerHistoryView(APIView):
    """GET /api/parking/customer/history/ — customer's booking history."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]

    def get(self, request):
        page = int(request.query_params.get("page", 1))
        page_size = min(int(request.query_params.get("page_size", 20)), 50)
        status_filter = request.query_params.get("status")

        qs = ParkingBooking.objects.filter(customer=request.user).select_related(
            "slot__zone__location"
        ).order_by("-created_at")

        if status_filter:
            qs = qs.filter(status=status_filter)

        total = qs.count()
        offset = (page - 1) * page_size
        bookings = qs[offset: offset + page_size]

        return Response({
            "bookings": [_serialize_booking(b) for b in bookings],
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": (offset + page_size) < total,
        })


# ─── Owner Dashboard Views ─────────────────────────────────────────────────────

class ParkingOwnerLocationsView(APIView):
    """GET /api/parking/owner/locations/ — locations managed by this operator."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsParkingRole]

    def get(self, request):
        operator_locations = ParkingOperator.objects.filter(
            user=request.user, is_active=True
        ).select_related("location")

        data = []
        for op in operator_locations:
            d = _serialize_location(op.location)
            d["operatorRole"] = op.role
            data.append(d)

        return Response({"locations": data, "count": len(data)})


class ParkingOwnerProfileView(APIView):
    """GET /api/parking/owner/me/ — current operator role + locations."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsParkingRole]

    def get(self, request):
        ops = list(
            ParkingOperator.objects.filter(user=request.user, is_active=True).select_related("location")
        )
        if not ops and not request.user.is_staff:
            return Response({"detail": "Parking operator access is not enabled."}, status=status.HTTP_403_FORBIDDEN)

        top_role = None
        if ops:
            top_role = max(ops, key=lambda op: PARKING_ROLE_PRIORITY.get(op.role, 0)).role
        elif request.user.is_staff:
            top_role = ParkingOperator.ROLE_OWNER

        locations = [
            {
                "id": op.location_id,
                "name": op.location.name,
                "role": op.role,
                "isActive": op.is_active,
            }
            for op in ops
        ]
        return Response({
            "role": top_role,
            "locations": locations,
            "isStaff": bool(request.user.is_staff),
        })


class ParkingOwnerRevenueView(APIView):
    """GET /api/parking/owner/revenue/?location_id=&days=30 — owner revenue summary."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsParkingRole]

    def get(self, request):
        location_id = request.query_params.get("location_id")
        days = int(request.query_params.get("days", 30))

        if not location_id:
            return Response({"detail": "location_id required."}, status=status.HTTP_400_BAD_REQUEST)

        # Verify operator access
        has_access = _has_owner_or_manager_access(request.user, location_id)
        if not has_access and not request.user.is_staff:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        summary = parking_service.get_owner_revenue_summary(
            location_id=int(location_id), days=days
        )
        return Response(summary)


class ParkingOwnerSlotStatusUpdateView(APIView):
    """PUT /api/parking/owner/slots/<id>/status/ — attendant updates slot status manually."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsParkingRole]
    parser_classes = [JSONParser]

    def put(self, request, slot_id):
        new_status = request.data.get("status")
        valid_statuses = [
            ParkingSlot.STATUS_AVAILABLE,
            ParkingSlot.STATUS_BLOCKED,
            ParkingSlot.STATUS_MAINTENANCE,
        ]
        if new_status not in valid_statuses:
            return Response(
                {"detail": f"Invalid status. Allowed: {valid_statuses}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            slot = ParkingSlot.objects.select_related("zone__location").get(pk=slot_id)
        except ParkingSlot.DoesNotExist:
            return Response({"detail": "Slot not found."}, status=status.HTTP_404_NOT_FOUND)

        # Verify operator access
        has_access = ParkingOperator.objects.filter(
            user=request.user,
            location=slot.zone.location,
            is_active=True,
        ).exists()
        if not has_access and not request.user.is_staff:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        slot.status = new_status
        slot.save(update_fields=["status", "updated_at"])

        return Response({"success": True, "slot": _serialize_slot(slot)})


class ParkingOwnerBookingsView(APIView):
    """GET /api/parking/owner/bookings/?location_id= — all bookings for a location."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsParkingRole]

    def get(self, request):
        location_id = request.query_params.get("location_id")
        if not location_id:
            return Response({"detail": "location_id required."}, status=status.HTTP_400_BAD_REQUEST)

        # Verify operator access
        has_access = ParkingOperator.objects.filter(
            user=request.user,
            location_id=location_id,
            is_active=True,
        ).exists()
        if not has_access and not request.user.is_staff:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        date_filter = request.query_params.get("date")  # YYYY-MM-DD
        status_filter = request.query_params.get("status")

        qs = ParkingBooking.objects.filter(
            slot__zone__location_id=location_id
        ).select_related("slot__zone__location", "customer").order_by("-created_at")

        if date_filter:
            qs = qs.filter(created_at__date=date_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)

        bookings = qs[:100]
        return Response({
            "bookings": [_serialize_booking(b) for b in bookings],
            "count": qs.count(),
        })


class ParkingOwnerTeamView(APIView):
    """
    GET /api/parking/locations/<id>/team/ — list operators for location (owner/manager).
    POST /api/parking/locations/<id>/team/ — create/invite operator for location (owner-only).
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsParkingRole]
    parser_classes = [JSONParser]

    def get(self, request, location_id):
        if not (_has_owner_or_manager_access(request.user, location_id) or request.user.is_staff):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        ops = ParkingOperator.objects.filter(
            location_id=location_id
        ).select_related("user__profile", "location").order_by("-is_active", "role", "created_at")
        return Response({
            "operators": [_serialize_operator(op) for op in ops],
            "count": ops.count(),
        })

    def post(self, request, location_id):
        if not (_has_owner_access(request.user, location_id) or request.user.is_staff):
            return Response({"detail": "Only location owner can manage team users."}, status=status.HTTP_403_FORBIDDEN)

        email = (request.data.get("email") or "").strip()
        username = (request.data.get("username") or "").strip()
        role = (request.data.get("role") or "").strip()
        role_choices = {
            ParkingOperator.ROLE_OWNER,
            ParkingOperator.ROLE_MANAGER,
            ParkingOperator.ROLE_ATTENDANT,
        }
        if role not in role_choices:
            return Response({"detail": "Invalid role."}, status=status.HTTP_400_BAD_REQUEST)
        if not email and not username:
            return Response({"detail": "email or username is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = None
        if email:
            profile = Profile.objects.filter(email__iexact=email).select_related("user").first()
            if profile:
                user = profile.user
        if user is None and username:
            user = User.objects.filter(username__iexact=username).first()
        if user is None:
            return Response({"detail": "User not found for provided email/username."}, status=status.HTTP_404_NOT_FOUND)

        try:
            location = ParkingLocation.objects.get(pk=location_id, is_active=True)
        except ParkingLocation.DoesNotExist:
            return Response({"detail": "Location not found."}, status=status.HTTP_404_NOT_FOUND)

        op, _ = ParkingOperator.objects.update_or_create(
            user=user,
            location=location,
            defaults={
                "role": role,
                "is_active": True,
                "notes": (request.data.get("notes") or "").strip(),
            },
        )
        op = ParkingOperator.objects.select_related("user__profile", "location").get(pk=op.pk)
        return Response({"success": True, "operator": _serialize_operator(op)})


class ParkingOwnerTeamDetailView(APIView):
    """
    PATCH /api/parking/locations/<id>/team/<operator_id>/ — update role / active status (owner-only).
    DELETE /api/parking/locations/<id>/team/<operator_id>/ — deactivate operator (owner-only).
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsParkingRole]
    parser_classes = [JSONParser]

    def _get_op(self, location_id, operator_id):
        return ParkingOperator.objects.select_related("user__profile", "location").filter(
            pk=operator_id,
            location_id=location_id,
        ).first()

    def patch(self, request, location_id, operator_id):
        if not (_has_owner_access(request.user, location_id) or request.user.is_staff):
            return Response({"detail": "Only location owner can manage team users."}, status=status.HTTP_403_FORBIDDEN)

        op = self._get_op(location_id, operator_id)
        if not op:
            return Response({"detail": "Operator not found."}, status=status.HTTP_404_NOT_FOUND)

        role = request.data.get("role")
        is_active = request.data.get("isActive")
        if role is not None:
            if role not in {
                ParkingOperator.ROLE_OWNER,
                ParkingOperator.ROLE_MANAGER,
                ParkingOperator.ROLE_ATTENDANT,
            }:
                return Response({"detail": "Invalid role."}, status=status.HTTP_400_BAD_REQUEST)
            op.role = role
        if is_active is not None:
            op.is_active = bool(is_active)
        notes = request.data.get("notes")
        if notes is not None:
            op.notes = str(notes).strip()
        op.save(update_fields=["role", "is_active", "notes", "updated_at"])
        return Response({"success": True, "operator": _serialize_operator(op)})

    def delete(self, request, location_id, operator_id):
        if not (_has_owner_access(request.user, location_id) or request.user.is_staff):
            return Response({"detail": "Only location owner can manage team users."}, status=status.HTTP_403_FORBIDDEN)

        op = self._get_op(location_id, operator_id)
        if not op:
            return Response({"detail": "Operator not found."}, status=status.HTTP_404_NOT_FOUND)
        op.is_active = False
        op.save(update_fields=["is_active", "updated_at"])
        return Response({"success": True})


# ─── Exit Preview ─────────────────────────────────────────────────────────────

class ParkingExitPreviewView(APIView):
    """
    GET /api/parking/bookings/<ref>/exit-preview/
    Returns current due amount, voucher balance, payment options.
    Operator or customer can call this before initiating exit payment.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_ref):
        try:
            booking = ParkingBooking.objects.select_related(
                "slot__zone__location", "customer"
            ).get(booking_reference=booking_ref)
        except ParkingBooking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

        if booking.customer != request.user and not request.user.is_staff:
            has_op = ParkingOperator.objects.filter(
                user=request.user, location=booking.slot.zone.location, is_active=True
            ).exists()
            if not has_op:
                return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from portal.services.parking_payment_service import compute_exit_due, get_voucher_total_balance
        from portal.services.parking_service import _has_parking_tx_pin, _build_payment_options

        due_info = compute_exit_due(booking)
        voucher_balance = get_voucher_total_balance(booking.customer)
        has_pin = _has_parking_tx_pin(booking.customer)

        return Response({
            "bookingReference": booking_ref,
            "durationMinutes": due_info["duration_minutes"],
            "finalAmount": float(due_info["final_amount"]),
            "alreadyPaid": float(due_info["already_paid"]),
            "due": float(due_info["due"]),
            "overstayAmount": float(due_info["overstay_amount"]),
            "voucherBalance": float(voucher_balance),
            "voucherSufficient": voucher_balance >= due_info["due"],
            "hasParkingTxPin": has_pin,
            "paymentOptions": _build_payment_options(voucher_balance >= due_info["due"]),
            "currency": "INR",
        })


# ─── Pay Exit via Voucher (auto-debit with profile TX PIN) ────────────────────

class ParkingExitPayVoucherView(APIView):
    """
    POST /api/parking/bookings/<ref>/pay-exit/voucher/
    Body: { pin: "1234" }
    Verifies profile TX PIN → multi-voucher debit → completes exit.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, booking_ref):
        pin = (request.data.get("pin") or "").strip()
        if not pin:
            return Response({"detail": "PIN is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            booking = ParkingBooking.objects.select_related(
                "slot__zone__location", "customer"
            ).get(booking_reference=booking_ref, customer=request.user)
        except ParkingBooking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

        if booking.status != ParkingBooking.STATUS_ACTIVE:
            return Response({"detail": f"Cannot pay for booking with status: {booking.status}"}, status=status.HTTP_400_BAD_REQUEST)

        from portal.services.parking_payment_service import try_voucher_exit_payment
        try:
            result = try_voucher_exit_payment(booking, raw_pin=pin, attendant=None)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("parking_voucher_exit_error", extra_data={"booking_ref": booking_ref, "error": str(e)})
            return Response({"detail": "Payment failed. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"success": True, **result})


# ─── Pay Exit via UPI (Cashfree) ──────────────────────────────────────────────

class ParkingExitPayUPIView(APIView):
    """
    POST /api/parking/bookings/<ref>/pay-exit/upi/
    Creates a Cashfree UPI order. Returns UPI link/QR for customer to scan.
    Owner page polls /payment-status/ until confirmed.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, booking_ref):
        try:
            booking = ParkingBooking.objects.select_related(
                "slot__zone__location", "customer"
            ).get(booking_reference=booking_ref)
        except ParkingBooking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

        # Allow customer or operator
        if booking.customer != request.user and not request.user.is_staff:
            has_op = ParkingOperator.objects.filter(
                user=request.user, location=booking.slot.zone.location, is_active=True
            ).exists()
            if not has_op:
                return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        if booking.status != ParkingBooking.STATUS_ACTIVE:
            return Response({"detail": f"Cannot pay for booking with status: {booking.status}"}, status=status.HTTP_400_BAD_REQUEST)

        from portal.services.parking_payment_service import create_upi_exit_order
        try:
            result = create_upi_exit_order(booking)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("parking_upi_exit_order_error", extra_data={"booking_ref": booking_ref, "error": str(e)})
            return Response({"detail": "Could not create payment order."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"success": True, **result})


# ─── Payment Status Polling ───────────────────────────────────────────────────

class ParkingExitPaymentStatusView(APIView):
    """
    GET /api/parking/exit-payments/<id>/status/
    Polls Cashfree for UPI payment status. Returns { paid, status, ... }.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, exit_payment_id):
        try:
            ep = ParkingExitPayment.objects.select_related("booking__customer").get(pk=exit_payment_id)
        except ParkingExitPayment.DoesNotExist:
            return Response({"detail": "Exit payment not found."}, status=status.HTTP_404_NOT_FOUND)

        booking = ep.booking
        if booking.customer != request.user and not request.user.is_staff:
            has_op = ParkingOperator.objects.filter(
                user=request.user, location=booking.slot.zone.location, is_active=True
            ).exists()
            if not has_op:
                return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from portal.services.parking_payment_service import check_upi_payment_status
        result = check_upi_payment_status(exit_payment_id)
        return Response(result)


# ─── Cashfree Webhook ─────────────────────────────────────────────────────────

class ParkingCashfreeWebhookView(APIView):
    """
    POST /api/parking/webhooks/cashfree/
    Receives Cashfree payment webhook for parking exit UPI orders.
    No authentication — IP/signature verified inside service.
    """
    authentication_classes = []
    permission_classes = []
    parser_classes = [JSONParser]

    def post(self, request):
        from portal.services.parking_payment_service import process_cashfree_webhook
        payload = request.data or {}
        signature = request.META.get("HTTP_X_WEBHOOK_SIGNATURE") or request.META.get("HTTP_X_CASHFREE_SIGNATURE", "")
        try:
            result = process_cashfree_webhook(payload, signature=signature)
        except Exception as e:
            logger.exception("parking_cashfree_webhook_error", extra_data={"error": str(e)})
            return Response({"status": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"status": "ok", "processed": result.get("processed"), "payment_status": result.get("status"), "order_id": result.get("order_id")})


# ─── Profile Transaction PIN ──────────────────────────────────────────────────

class ParkingTxPinSetView(APIView):
    """
    POST /api/parking/tx-pin/set/
    Body: { pin: "1234" }
    Sets or updates the profile-level parking transaction PIN.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]
    parser_classes = [JSONParser]

    def post(self, request):
        pin = (request.data.get("pin") or "").strip()
        if not pin:
            return Response({"detail": "PIN is required."}, status=status.HTTP_400_BAD_REQUEST)
        from portal.services.parking_payment_service import set_parking_tx_pin
        try:
            set_parking_tx_pin(request.user, pin)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True, "message": "Parking transaction PIN set successfully."})


class ParkingTxPinVerifyView(APIView):
    """
    POST /api/parking/tx-pin/verify/
    Body: { pin: "1234" }
    Verifies PIN without debiting — useful for UX pre-validation.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]
    parser_classes = [JSONParser]

    def post(self, request):
        pin = (request.data.get("pin") or "").strip()
        from portal.services.parking_payment_service import verify_parking_tx_pin
        try:
            verify_parking_tx_pin(request.user, pin)
        except ValueError as e:
            return Response({"detail": str(e), "valid": False}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"valid": True, "message": "PIN verified."})


# ─── FASTag user mapping ───────────────────────────────────────────────────────


def _serialize_fastag_mapping(m: VehicleFasTagMapping) -> dict:
    return {
        "id": str(m.pk),
        "vehicleNumber": m.vehicle_number,
        "fastagId": m.fastag_id,
        "issuer": m.fastag_issuer,
        "isVerified": m.is_verified,
        "isActive": m.is_active,
        "linkedVehicleId": m.linked_vehicle_id,
        "lastBalanceInr": float(m.last_balance_inr),
        "balanceFetchedAt": m.balance_fetched_at.isoformat() if m.balance_fetched_at else None,
    }


class ParkingFastagListView(APIView):
    """GET /api/parking/fastag/mappings/ — current user's FASTag links."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]

    def get(self, request):
        rows = VehicleFasTagMapping.objects.filter(user=request.user).order_by("-updated_at")
        return Response({"mappings": [_serialize_fastag_mapping(m) for m in rows]})


class ParkingFastagLinkView(APIView):
    """
    POST /api/parking/fastag/link/
    Body: { vehicleNumber, fastagId, issuer, fastagWalletId? }
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerPortal]
    parser_classes = [JSONParser]

    def post(self, request):
        vehicle_number = (request.data.get("vehicleNumber") or request.data.get("vehicle_number") or "").strip()
        fastag_id = (request.data.get("fastagId") or request.data.get("fastag_id") or "").strip()
        issuer = (request.data.get("issuer") or "npci").strip()[:20]
        wallet = (request.data.get("fastagWalletId") or request.data.get("fastag_wallet_id") or "").strip()[:200]
        if not vehicle_number or not fastag_id:
            return Response({"detail": "vehicleNumber and fastagId are required."}, status=status.HTTP_400_BAD_REQUEST)
        vehicle_number = vehicle_number.upper().replace(" ", "")

        if VehicleFasTagMapping.objects.filter(fastag_id=fastag_id).exclude(user=request.user).exists():
            return Response({"detail": "This FASTag is already linked to another account."}, status=status.HTTP_400_BAD_REQUEST)

        mapping, _created = VehicleFasTagMapping.objects.update_or_create(
            user=request.user,
            vehicle_number=vehicle_number,
            defaults={
                "fastag_id": fastag_id,
                "fastag_issuer": issuer,
                "fastag_wallet_id": wallet,
                "is_verified": True,
                "is_active": True,
            },
        )
        return Response({"success": True, "mapping": _serialize_fastag_mapping(mapping)})
