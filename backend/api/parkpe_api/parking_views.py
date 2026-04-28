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
from rest_framework.permissions import IsAuthenticated
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
)
from portal.services import parking_service, parking_notification_service
from portal.utils.logging_helper import get_logger

logger = get_logger(__name__)


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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]
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
            ).get(booking_reference=booking_ref, customer=request.user)
        except ParkingBooking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_booking(booking))


class ParkingBookingEntryView(APIView):
    """POST /api/parking/bookings/<ref>/entry/ — validate entry QR/OTP."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, booking_ref):
        qr_payload = request.data.get("qrPayload") or request.data.get("qr_payload")
        otp = request.data.get("otp")

        try:
            booking = parking_service.process_entry(
                booking_reference=booking_ref,
                qr_payload=qr_payload,
                otp=otp,
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
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True, "booking": _serialize_booking(booking)})


class ParkingTicketResendView(APIView):
    """POST /api/parking/bookings/<ref>/ticket/resend/ — resend WhatsApp + Email."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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


class ParkingOwnerRevenueView(APIView):
    """GET /api/parking/owner/revenue/?location_id=&days=30 — owner revenue summary."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        location_id = request.query_params.get("location_id")
        days = int(request.query_params.get("days", 30))

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

        summary = parking_service.get_owner_revenue_summary(
            location_id=int(location_id), days=days
        )
        return Response(summary)


class ParkingOwnerSlotStatusUpdateView(APIView):
    """PUT /api/parking/owner/slots/<id>/status/ — attendant updates slot status manually."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
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
    permission_classes = [IsAuthenticated]

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
