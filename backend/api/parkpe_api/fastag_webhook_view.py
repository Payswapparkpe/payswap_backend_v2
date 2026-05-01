"""
FASTag gate scanner webhook — HMAC-authenticated, idempotent event pipeline.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from portal.models import (
    FasTagGatewayEvent,
    ParkingBooking,
    ParkingLocation,
    ParkingSession,
    VehicleFasTagMapping,
)
from portal.services import parking_service
from portal.utils.logging_helper import get_logger

logger = get_logger("api.parking.fastag_webhook")


def _sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _norm_vehicle(v: str) -> str:
    return (v or "").upper().replace(" ", "")


@method_decorator(csrf_exempt, name="dispatch")
class FasTagScannerWebhookView(APIView):
    """
    POST /api/parking/webhooks/fastag-scanner/
    Header: X-ParkPe-Signature: <hex HMAC-SHA256 of raw body>
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.body or b""
        sig_header = (request.META.get("HTTP_X_PARKPE_SIGNATURE") or "").strip()

        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return Response({"detail": "Invalid JSON."}, status=400)

        location_code = (data.get("location_code") or "").strip()
        idempotency_key = (data.get("idempotency_key") or "").strip()
        if not idempotency_key:
            return Response({"detail": "idempotency_key required."}, status=400)

        loc = ParkingLocation.objects.filter(location_code=location_code).first()
        if not loc or not (loc.webhook_secret or "").strip():
            return Response({"detail": "Unauthorized."}, status=401)

        expected = _sign_body(loc.webhook_secret.strip(), raw)
        if not hmac.compare_digest(expected, sig_header):
            return Response({"detail": "Invalid signature."}, status=401)

        dup = FasTagGatewayEvent.objects.filter(idempotency_key=idempotency_key).first()
        if dup and dup.processed_at and dup.raw_payload.get("webhook_response"):
            return Response(dup.raw_payload["webhook_response"])

        gate_id = (data.get("gate_id") or "").strip() or "unknown"
        event_type = (data.get("event_type") or "").strip().lower()
        fastag_id = (data.get("fastag_id") or "").strip()
        vehicle_number = _norm_vehicle(data.get("vehicle_number") or "")
        vehicle_count = int(data.get("vehicle_count") or 1)

        tailgating = vehicle_count > 1
        if not tailgating and event_type == FasTagGatewayEvent.EVENT_EXIT:
            recent = (
                FasTagGatewayEvent.objects.filter(
                    gate_id=gate_id,
                    event_type=FasTagGatewayEvent.EVENT_EXIT,
                    processed_at__isnull=False,
                )
                .order_by("-processed_at")
                .first()
            )
            if recent and recent.processed_at:
                if timezone.now() - recent.processed_at < timedelta(seconds=10):
                    tailgating = True

        with transaction.atomic():
            ev, created = FasTagGatewayEvent.objects.select_for_update().get_or_create(
                idempotency_key=idempotency_key,
                defaults={
                    "location": loc,
                    "gate_id": gate_id,
                    "event_type": event_type
                    if event_type in (FasTagGatewayEvent.EVENT_ENTRY, FasTagGatewayEvent.EVENT_EXIT)
                    else FasTagGatewayEvent.EVENT_ENTRY,
                    "fastag_id": fastag_id,
                    "vehicle_number": vehicle_number,
                    "raw_payload": dict(data),
                    "status": FasTagGatewayEvent.STATUS_RECEIVED,
                },
            )
            if not created and ev.processed_at:
                return Response(ev.raw_payload.get("webhook_response") or {"action": "hold_barrier"})

        if tailgating:
            self._finalize_event(ev, FasTagGatewayEvent.STATUS_TAILGATING_SUSPECT, None)
            resp = {"action": "hold_barrier", "reason": "tailgating_suspect", "session_id": None}
            self._save_response(ev, resp)
            return Response(resp)

        mapping = (
            VehicleFasTagMapping.objects.filter(
                fastag_id=fastag_id,
                is_active=True,
            ).first()
            if fastag_id
            else None
        )
        if not mapping and vehicle_number:
            mapping = VehicleFasTagMapping.objects.filter(
                vehicle_number=vehicle_number,
                is_active=True,
            ).first()

        if not mapping:
            self._finalize_event(ev, FasTagGatewayEvent.STATUS_UNMATCHED, None)
            resp = {"action": "hold_barrier", "reason": "unmatched", "session_id": None}
            self._save_response(ev, resp)
            return Response(resp)

        booking = None
        if event_type == FasTagGatewayEvent.EVENT_ENTRY:
            booking = (
                ParkingBooking.objects.filter(
                    customer=mapping.user,
                    slot__zone__location=loc,
                    vehicle_number__iexact=vehicle_number or mapping.vehicle_number,
                    status__in=[ParkingBooking.STATUS_CONFIRMED, ParkingBooking.STATUS_PENDING],
                )
                .select_related("slot__zone__location")
                .order_by("-created_at")
                .first()
            )
        else:
            booking = (
                ParkingBooking.objects.filter(
                    customer=mapping.user,
                    slot__zone__location=loc,
                    vehicle_number__iexact=vehicle_number or mapping.vehicle_number,
                    status=ParkingBooking.STATUS_ACTIVE,
                )
                .select_related("slot__zone__location")
                .order_by("-created_at")
                .first()
            )

        if not booking:
            self._finalize_event(ev, FasTagGatewayEvent.STATUS_UNMATCHED, None)
            resp = {"action": "hold_barrier", "reason": "no_booking", "session_id": None}
            self._save_response(ev, resp)
            return Response(resp)

        try:
            if event_type == FasTagGatewayEvent.EVENT_ENTRY:
                parking_service.process_entry(
                    booking_reference=booking.booking_reference,
                    qr_payload=None,
                    otp=None,
                    attendant=None,
                    acting_user=mapping.user,
                    entry_method_override=ParkingSession.ENTRY_METHOD_FASTAG,
                )
                sess = ParkingSession.objects.filter(booking=booking).first()
                session_pk = str(sess.pk) if sess else ""
                self._finalize_event(ev, FasTagGatewayEvent.STATUS_MATCHED, sess.pk if sess else None)
                resp = {"action": "raise_barrier", "session_id": session_pk}
                self._save_response(ev, resp)
                return Response(resp)

            summary = parking_service.process_exit(
                booking_reference=booking.booking_reference,
                exit_method=ParkingSession.ENTRY_METHOD_FASTAG,
            )
            sess = ParkingSession.objects.filter(booking=booking).first()
            session_pk = str(sess.pk) if sess else ""
            if summary.get("status") == "payment_required":
                resp = {"action": "hold_barrier", "session_id": session_pk, "reason": "payment_required"}
            else:
                resp = {"action": "raise_barrier", "session_id": session_pk}
            self._finalize_event(ev, FasTagGatewayEvent.STATUS_MATCHED, sess.pk if sess else None)
            self._save_response(ev, resp)
            return Response(resp)
        except Exception as ex:
            logger.exception("fastag_webhook_process_failed", extra_data={"error": str(ex)})
            self._finalize_event(ev, FasTagGatewayEvent.STATUS_ERROR, None)
            resp = {"action": "hold_barrier", "reason": "error", "detail": str(ex)}
            self._save_response(ev, resp)
            return Response(resp, status=200)

    def _finalize_event(self, ev: FasTagGatewayEvent, status: str, session_id):
        with transaction.atomic():
            e = FasTagGatewayEvent.objects.select_for_update().get(pk=ev.pk)
            e.status = status
            e.processed_at = timezone.now()
            if session_id:
                e.session_id = session_id
            e.save(update_fields=["status", "processed_at", "session"])

    def _save_response(self, ev: FasTagGatewayEvent, resp: dict):
        payload = dict(ev.raw_payload or {})
        payload["webhook_response"] = resp
        FasTagGatewayEvent.objects.filter(pk=ev.pk).update(raw_payload=payload)
