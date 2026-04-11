"""
ParkPe Connect API – vehicle CRUD, by-QR lookup, by-registration. Shared helpers for chat (mask, owner name).
"""
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from api.throttling import ConnectScanRateThrottle
from portal.models import (
    Vehicle,
    VehicleQRCode,
    VehicleRCData,
    VehicleRCUnlock,
    ParkPeVoucherTransaction,
    Profile,
    GiftVoucher,
)

# Individual users: max 4 vehicles. Corporate: unlimited (monthly charges apply).
INDIVIDUAL_MAX_VEHICLES = 4
from portal.services.cashfree_vehicle_rc import fetch_vehicle_rc
from portal.services.parkpe_voucherx_bridge import get_parkpe_brand_id
from portal.services.voucher_service import VoucherService
from portal.services.otp_service import OTPService
from portal.utils.phone_utils import normalize_phone_number
from portal.tasks.connect_tasks import fetch_connect_vehicle_rc_task

from ._common import logger, vehicle_log
from ..serializers import (
    VehicleSerializer,
    VehicleCreateSerializer,
    VehicleByQRResponseSerializer,
)

def _normalize_value(value: str | None) -> str:
    """Normalize free-text values for relaxed comparisons."""
    if value is None:
        return ""
    return " ".join(str(value).strip().upper().split())


def _mask_registration(reg: str) -> str:
    """Mask registration number for public display (e.g. KA01AB****)."""
    if not reg or len(reg) < 4:
        return "****"
    return reg[:4].upper() + "*" * min(len(reg) - 4, 4)


def _owner_display_name(vehicle: Vehicle) -> str:
    """Non-PII display name for vehicle owner (e.g. 'Vehicle Owner')."""
    user = vehicle.user
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "first_name", None):
        return f"{profile.first_name.strip()}***"
    return "Vehicle Owner"


class VehicleListCreateView(APIView):
    """GET /api/connect/vehicles/ – list my vehicles. POST – create vehicle (and QR)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        vehicle_log(request, "INFO", "vehicle_list", {"user_id": request.user.pk})
        qs = Vehicle.objects.filter(user=request.user).select_related('qr_code', 'rc_data').order_by('-is_primary', '-created_at')
        serializer = VehicleSerializer(qs, many=True, context={'request': request})
        profile = getattr(request.user, "profile", None)
        user_type = getattr(profile, "type", None) or "individual"
        vehicle_count = qs.count()
        max_vehicles = None if user_type == "corporate" else INDIVIDUAL_MAX_VEHICLES
        vehicle_log(request, "INFO", "vehicle_list_ok", {"user_id": request.user.pk, "count": vehicle_count})
        return Response({
            "results": serializer.data,
            "meta": {
                "user_type": user_type,
                "vehicle_count": vehicle_count,
                "max_vehicles": max_vehicles,
                "can_add_more": max_vehicles is None or vehicle_count < max_vehicles,
            },
        })

    def post(self, request):
        if request.data.get("accept_ownership_declaration") is not True:
            vehicle_log(request, "WARNING", "vehicle_create_declaration_not_accepted", {"user_id": request.user.pk})
            return Response(
                {"detail": "You must accept the vehicle ownership declaration to add a vehicle."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Individual users: max 4 vehicles. Corporate: unlimited.
        profile = getattr(request.user, "profile", None)
        user_type = getattr(profile, "type", None) or "individual"
        current_count = Vehicle.objects.filter(user=request.user).count()
        if user_type == "individual" and current_count >= INDIVIDUAL_MAX_VEHICLES:
            vehicle_log(request, "WARNING", "vehicle_create_limit_exceeded", {"user_id": request.user.pk, "count": current_count})
            return Response(
                {
                    "detail": f"You can add up to {INDIVIDUAL_MAX_VEHICLES} vehicles as an Individual user. Upgrade to Corporate to add more vehicles (monthly charges apply). Go to Settings or contact support.",
                    "code": "vehicle_limit_exceeded",
                    "max_vehicles": INDIVIDUAL_MAX_VEHICLES,
                    "user_type": user_type,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = request.data.copy()
        data['user'] = request.user.id
        serializer = VehicleCreateSerializer(data=data, partial=False)
        serializer.is_valid(raise_exception=True)
        reg = (serializer.validated_data.get('registration_number') or '').strip().upper()
        reg_norm = _normalize_registration(reg)
        vehicle_log(request, "INFO", "vehicle_create_start", {"user_id": request.user.pk, "reg": reg})
        if Vehicle.objects.filter(user=request.user, registration_number_normalized=reg_norm).exists():
            vehicle_log(request, "WARNING", "vehicle_create_duplicate_reg", {"user_id": request.user.pk, "reg": reg})
            return Response(
                {"detail": "A vehicle with this registration number already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        vehicle = serializer.save(
            user=request.user,
            ownership_declaration_accepted_at=timezone.now(),
        )
        # First vehicle for this user is always primary
        if Vehicle.objects.filter(user=request.user).count() == 1:
            vehicle.is_primary = True
            vehicle.save(update_fields=['is_primary'])
        code = secrets.token_urlsafe(10).replace('-', '').replace('_', '')[:14]
        while VehicleQRCode.objects.filter(code=code).exists():
            code = secrets.token_urlsafe(10).replace('-', '').replace('_', '')[:14]
        VehicleQRCode.objects.create(vehicle=vehicle, code=code)
        vehicle_log(request, "INFO", "vehicle_create_qr_created", {"user_id": request.user.pk, "vehicle_id": vehicle.pk, "reg": reg})
        # First vehicle: free RC fetch. Second and subsequent: RC is chargeable (user pays then fetches via pay-rc-view + fetch-rc).
        vehicle_count = Vehicle.objects.filter(user=request.user).count()
        if vehicle_count == 1:
            try:
                rc_response, rc_reason, rc_details = fetch_vehicle_rc(reg)
                if rc_response:
                    VehicleRCData.objects.update_or_create(
                        vehicle=vehicle,
                        defaults={"raw_response": rc_response},
                    )
                    vehicle_log(request, "INFO", "vehicle_create_rc_saved", {"vehicle_id": vehicle.pk, "reg": reg})
                else:
                    extra = {"vehicle_id": vehicle.pk, "reg": reg, "rc_reason": rc_reason}
                    if rc_details:
                        extra.update(rc_details)
                    vehicle_log(request, "INFO", f"vehicle_create_rc_no_data (reason: {rc_reason or 'unknown'})", extra)
            except Exception as e:
                vehicle_log(request, "WARNING", "vehicle_create_rc_exception", {"vehicle_id": vehicle.pk, "reg": reg, "error": str(e)})
        else:
            vehicle_log(request, "INFO", "vehicle_create_rc_chargeable", {"vehicle_id": vehicle.pk, "reg": reg})
        vehicle.refresh_from_db()
        vehicle = Vehicle.objects.filter(pk=vehicle.pk).select_related('qr_code', 'rc_data').first()
        payload = VehicleSerializer(vehicle, context={'request': request}).data
        vehicle_log(request, "INFO", "vehicle_create_ok", {"user_id": request.user.pk, "vehicle_id": vehicle.pk, "reg": reg})
        return Response(payload, status=status.HTTP_201_CREATED)


class VehicleDetailView(APIView):
    """GET /api/connect/vehicles/<id>/ – get one. PATCH – update. DELETE – delete."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _get_vehicle(self, request, pk):
        return Vehicle.objects.filter(user=request.user).select_related('qr_code', 'rc_data').filter(pk=pk).first()

    def get(self, request, pk):
        vehicle_log(request, "INFO", "vehicle_detail_get", {"user_id": request.user.pk, "vehicle_id": pk})
        vehicle = self._get_vehicle(request, pk)
        if not vehicle:
            vehicle_log(request, "WARNING", "vehicle_detail_not_found", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            rc = getattr(vehicle, "rc_data", None)
            if not rc:
                rc = VehicleRCData.objects.filter(vehicle=vehicle).first()
            if not rc:
                vehicle_log(request, "INFO", "vehicle_detail_lazy_rc_fetch", {"vehicle_id": pk, "reg": vehicle.registration_number})
                fetch_connect_vehicle_rc_task.delay(vehicle.pk)
        except Exception as e:
            vehicle_log(request, "WARNING", "vehicle_detail_rc_error", {"vehicle_id": pk, "error": str(e)})
        vehicle = Vehicle.objects.filter(user=request.user).select_related('qr_code', 'rc_data').filter(pk=pk).first()
        payload = VehicleSerializer(vehicle, context={'request': request}).data
        if not getattr(vehicle, "rc_data", None):
            payload["rc_pending"] = True
        vehicle_log(request, "INFO", "vehicle_detail_ok", {"user_id": request.user.pk, "vehicle_id": pk})
        return Response(payload)

    def patch(self, request, pk):
        vehicle_log(request, "INFO", "vehicle_patch_start", {"user_id": request.user.pk, "vehicle_id": pk})
        vehicle = self._get_vehicle(request, pk)
        if not vehicle:
            vehicle_log(request, "WARNING", "vehicle_patch_not_found", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = VehicleCreateSerializer(vehicle, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        reg = (serializer.validated_data.get('registration_number') or vehicle.registration_number).strip().upper()
        reg_norm = _normalize_registration(reg)
        if reg_norm != _normalize_registration(vehicle.registration_number) and Vehicle.objects.filter(
            user=request.user,
            registration_number_normalized=reg_norm,
        ).exists():
            vehicle_log(request, "WARNING", "vehicle_patch_duplicate_reg", {"user_id": request.user.pk, "vehicle_id": pk, "reg": reg})
            return Response(
                {"detail": "Another vehicle with this registration number already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        vehicle.refresh_from_db()
        vehicle_log(request, "INFO", "vehicle_patch_ok", {"user_id": request.user.pk, "vehicle_id": pk})
        vehicle = Vehicle.objects.filter(user=request.user).select_related('qr_code', 'rc_data').filter(pk=pk).first()
        return Response(VehicleSerializer(vehicle, context={'request': request}).data)

    def delete(self, request, pk):
        vehicle_log(request, "INFO", "vehicle_delete_direct_rejected", {"user_id": request.user.pk, "vehicle_id": pk})
        return Response(
            {"detail": "Vehicle delete requires OTP. Use POST /api/connect/vehicles/<id>/delete-request then POST /api/connect/vehicles/<id>/delete with otp."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


def _get_user_phone(user):
    """Get user's phone from Profile for OTP. Returns (normalized_phone, error_response)."""
    profile = getattr(user, "profile", None)
    if not profile:
        return None, {"detail": "Profile not found."}
    phone = (getattr(profile, "phone", None) or "").strip()
    if not phone:
        return None, {"detail": "No mobile number linked. Add mobile in profile to delete vehicle with OTP."}
    try:
        return normalize_phone_number(phone), None
    except ValueError:
        return None, {"detail": "Invalid mobile number in profile."}


class VehicleDeleteRequestView(APIView):
    """POST /api/connect/vehicles/<id>/delete-request – send OTP to user's registered mobile for vehicle deletion."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, pk):
        vehicle_log(request, "INFO", "vehicle_delete_request_start", {"user_id": request.user.pk, "vehicle_id": pk})
        vehicle = Vehicle.objects.filter(user=request.user).filter(pk=pk).first()
        if not vehicle:
            vehicle_log(request, "WARNING", "vehicle_delete_request_not_found", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        phone, err = _get_user_phone(request.user)
        if err:
            vehicle_log(request, "WARNING", "vehicle_delete_request_no_phone", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response(err, status=status.HTTP_400_BAD_REQUEST)
        otp_service = OTPService()
        success, msg = otp_service.send_otp(phone, user_id=request.user.pk, async_send=True)
        if not success:
            vehicle_log(request, "WARNING", "vehicle_delete_request_otp_failed", {"user_id": request.user.pk, "vehicle_id": pk, "msg": msg})
            return Response({"detail": msg or "Failed to send OTP."}, status=status.HTTP_400_BAD_REQUEST)
        vehicle_log(request, "INFO", "vehicle_delete_request_ok", {"user_id": request.user.pk, "vehicle_id": pk})
        return Response({"message": "OTP sent to your registered mobile."})


class VehicleDeleteConfirmView(APIView):
    """POST /api/connect/vehicles/<id>/delete – body: { \"otp\": \"123456\" }. Verify OTP and delete vehicle."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, pk):
        vehicle_log(request, "INFO", "vehicle_delete_confirm_start", {"user_id": request.user.pk, "vehicle_id": pk})
        vehicle = Vehicle.objects.filter(user=request.user).filter(pk=pk).first()
        if not vehicle:
            vehicle_log(request, "WARNING", "vehicle_delete_confirm_not_found", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        otp = (request.data.get("otp") or "").strip()
        if not otp:
            vehicle_log(request, "WARNING", "vehicle_delete_confirm_no_otp", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "OTP is required."}, status=status.HTTP_400_BAD_REQUEST)
        phone, err = _get_user_phone(request.user)
        if err:
            return Response(err, status=status.HTTP_400_BAD_REQUEST)
        otp_service = OTPService()
        ok, _ = otp_service.verify_otp(phone, otp)
        if not ok:
            vehicle_log(request, "WARNING", "vehicle_delete_confirm_otp_invalid", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)
        reg = vehicle.registration_number
        vehicle.delete()
        vehicle_log(request, "INFO", "vehicle_delete_confirm_ok", {"user_id": request.user.pk, "vehicle_id": pk, "reg": reg})
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleUnlockRCView(APIView):
    """POST /api/connect/vehicles/<id>/unlock-rc/ – verify ownership with owner name, chassis, engine; grant temporary RC access."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, pk):
        vehicle_log(request, "INFO", "vehicle_unlock_rc_start", {"user_id": request.user.pk, "vehicle_id": pk})
        vehicle = Vehicle.objects.filter(user=request.user).select_related("rc_data").filter(pk=pk).first()
        if not vehicle:
            vehicle_log(request, "WARNING", "vehicle_unlock_rc_not_found", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        rc = getattr(vehicle, "rc_data", None) or VehicleRCData.objects.filter(vehicle=vehicle).first()
        if not rc or not rc.raw_response:
            vehicle_log(request, "WARNING", "vehicle_unlock_rc_no_rc_data", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response(
                {"detail": "No RC data available for this vehicle to verify against."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw = rc.raw_response
        owner_name = (request.data.get("owner_name") or "").strip()
        chassis_number = (request.data.get("chassis_number") or "").strip()
        engine_number = (request.data.get("engine_number") or "").strip()
        if not owner_name or not chassis_number or not engine_number:
            return Response(
                {"detail": "owner_name, chassis_number and engine_number are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            _normalize_value(owner_name) != _normalize_value(raw.get("owner"))
            or _normalize_value(chassis_number) != _normalize_value(str(raw.get("chassis") or ""))
            or _normalize_value(engine_number) != _normalize_value(str(raw.get("engine") or ""))
        ):
            vehicle_log(request, "WARNING", "vehicle_unlock_rc_verification_failed", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response(
                {"detail": "Verification failed. Please check owner name, chassis and engine number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        expires_at = timezone.now() + timedelta(minutes=15)
        VehicleRCUnlock.objects.update_or_create(
            user=request.user,
            vehicle=vehicle,
            defaults={"expires_at": expires_at},
        )
        vehicle_log(request, "INFO", "vehicle_unlock_rc_ok", {"user_id": request.user.pk, "vehicle_id": pk})
        return Response({"unlocked": True})


class VehicleFetchRCView(APIView):
    """POST /api/connect/vehicles/<id>/fetch-rc/ – fetch RC from API, save, return vehicle with vehicle_rc. First vehicle free; 2nd+ require payment (Rs 50) first."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        vehicle_log(request, "INFO", "vehicle_fetch_rc_start", {"user_id": request.user.pk, "vehicle_id": pk})
        vehicle = Vehicle.objects.filter(user=request.user).filter(pk=pk).first()
        if not vehicle:
            vehicle_log(request, "WARNING", "vehicle_fetch_rc_not_found", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        # Second and subsequent vehicles: RC is chargeable. Require payment before fetch.
        first_vehicle = Vehicle.objects.filter(user=request.user).order_by("created_at").values_list("pk", flat=True).first()
        if first_vehicle != vehicle.pk and not vehicle.rc_view_paid_at:
            vehicle_log(request, "INFO", "vehicle_fetch_rc_payment_required", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response(
                {
                    "detail": "RC is chargeable for 2nd and subsequent vehicles. Pay ₹50 from voucher first (Pay ₹50 button), then fetch RC.",
                    "code": "rc_payment_required",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        reg = (vehicle.registration_number or "").strip().upper()
        if not reg:
            vehicle_log(request, "WARNING", "vehicle_fetch_rc_no_reg", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "Vehicle has no registration number."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rc_response, rc_reason, rc_details = fetch_vehicle_rc(reg)
        except Exception as e:
            vehicle_log(request, "ERROR", "vehicle_fetch_rc_exception", {"vehicle_id": pk, "reg": reg, "error": str(e)})
            return Response(
                {"detail": f"RC fetch failed: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        if not rc_response:
            extra = {"vehicle_id": pk, "reg": reg, "rc_reason": rc_reason}
            if rc_details:
                extra.update(rc_details)
            vehicle_log(request, "INFO", f"vehicle_fetch_rc_no_data (reason: {rc_reason or 'unknown'})", extra)
            payload = VehicleSerializer(vehicle, context={'request': request}).data
            rc_messages = {
                "no_credentials": "RC API is not configured (missing credentials). Contact support.",
                "invalid_reg": "Invalid registration number.",
                "http_error": "RC API returned an error. The registration number may not be in the database.",
                "invalid_status": "No RC data found for this registration number. It may be invalid or not available.",
                "exception": "Verification service request failed (network or temporary error). Please try again later.",
            }
            payload["rc_message"] = rc_messages.get(
                rc_reason or "",
                "No RC data returned for this registration number.",
            )
            return Response(payload, status=status.HTTP_200_OK)
        try:
            VehicleRCData.objects.update_or_create(
                vehicle=vehicle,
                defaults={"raw_response": rc_response},
            )
        except Exception as e:
            vehicle_log(request, "ERROR", "vehicle_fetch_rc_save_failed", {"vehicle_id": pk, "reg": reg, "error": str(e)})
            return Response(
                {"detail": f"Failed to save RC data: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        vehicle = Vehicle.objects.filter(user=request.user).select_related('qr_code', 'rc_data').filter(pk=pk).first()
        payload = VehicleSerializer(vehicle, context={'request': request}).data
        vehicle_log(request, "INFO", "vehicle_fetch_rc_ok", {"user_id": request.user.pk, "vehicle_id": pk, "reg": reg})
        return Response(payload)


RC_VIEW_AMOUNT = 50


class VehiclePayRCView(APIView):
    """POST /api/connect/vehicles/<id>/pay-rc-view/ – pay Rs 50 from selected voucher (voucher_id + pin) to unlock full RC view."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from decimal import Decimal

        vehicle_log(request, "INFO", "vehicle_pay_rc_start", {"user_id": request.user.pk, "vehicle_id": pk})
        vehicle = Vehicle.objects.filter(user=request.user).select_related("rc_data").filter(pk=pk).first()
        if not vehicle:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if vehicle.rc_view_paid_at:
            payload = VehicleSerializer(vehicle, context={"request": request}).data
            return Response({"already_paid": True, "vehicle": payload}, status=status.HTTP_200_OK)

        data = request.data or {}
        voucher_id = data.get("voucher_id")
        pin = data.get("pin")
        if voucher_id is None or not str(pin or "").strip():
            return Response(
                {"detail": "Select a voucher and enter PIN to pay for RC view."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            voucher_id = int(voucher_id)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid voucher selection."}, status=status.HTTP_400_BAD_REQUEST)

        brand_id = get_parkpe_brand_id()
        if not brand_id:
            return Response(
                {"detail": "Voucher service not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        voucher = (
            GiftVoucher.objects.filter(
                id=voucher_id,
                brand_id=brand_id,
                metadata__parkpe_user_id=request.user.pk,
                status__in=["ACTIVE", "PARTIALLY_REDEEMED"],
                current_balance__gte=RC_VIEW_AMOUNT,
            )
            .first()
        )
        if not voucher:
            return Response(
                {"detail": "Voucher not found or insufficient balance. Need Rs 50."},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        amount = Decimal(str(RC_VIEW_AMOUNT))
        from portal.utils.transaction_id import generate_transaction_id

        reference_id = generate_transaction_id()
        try:
            VoucherService().redeem_voucher_pin(
                voucher_code=voucher.voucher_code,
                pin=str(pin).strip(),
                amount=amount,
                transaction_ref=reference_id,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            vehicle.rc_view_paid_at = timezone.now()
            vehicle.save(update_fields=["rc_view_paid_at", "updated_at"])
            ParkPeVoucherTransaction.objects.create(
                user=request.user,
                amount=amount,
                transaction_type=ParkPeVoucherTransaction.DEBIT,
                balance_after=None,
                reference_id=reference_id,
                service_code="RC_VIEW",
                description=f"RC view – {vehicle.registration_number}",
            )
        vehicle = Vehicle.objects.filter(user=request.user).select_related("qr_code", "rc_data").get(pk=pk)
        payload = VehicleSerializer(vehicle, context={"request": request}).data
        vehicle_log(request, "INFO", "vehicle_pay_rc_ok", {"user_id": request.user.pk, "vehicle_id": pk})
        return Response({"paid": True, "vehicle": payload}, status=status.HTTP_200_OK)


class VehicleQRView(APIView):
    """GET /api/connect/vehicles/<id>/qr/ – get QR code string and optional image URL for owner."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        vehicle_log(request, "INFO", "vehicle_qr_get", {"user_id": request.user.pk, "vehicle_id": pk})
        vehicle = Vehicle.objects.filter(user=request.user).select_related('qr_code').filter(pk=pk).first()
        if not vehicle:
            vehicle_log(request, "WARNING", "vehicle_qr_not_found", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        qr = getattr(vehicle, 'qr_code', None)
        if not qr:
            vehicle_log(request, "WARNING", "vehicle_qr_missing", {"user_id": request.user.pk, "vehicle_id": pk})
            return Response({"detail": "QR code not found for this vehicle."}, status=status.HTTP_404_NOT_FOUND)
        scan_path = f"/connect/scan/{qr.code}"
        vehicle_log(request, "INFO", "vehicle_qr_ok", {"user_id": request.user.pk, "vehicle_id": pk})
        return Response({
            "qr_code": qr.code,
            "scan_path": scan_path,
            "scan_url": request.build_absolute_uri(scan_path),
        })


def _vehicle_by_qr_payload(qr, vehicle):
    """Build public scan payload for a vehicle + its QR."""
    owner_profile = getattr(vehicle.user, "profile", None)
    owner_phone = (getattr(owner_profile, "phone", None) or "").strip()
    return {
        "vehicle_id": vehicle.id,
        "qr_code": qr.code,
        "registration_number_masked": _mask_registration(vehicle.registration_number),
        "brand": vehicle.brand or "",
        "model": vehicle.model or "",
        "year": vehicle.year,
        "owner_display_name": _owner_display_name(vehicle),
        "owner_phone_configured": bool(owner_phone),
        "contact_options": ["call", "chat"],
    }


class VehicleByQRView(APIView):
    """GET /api/connect/vehicle/by-qr/<qr_code>/ – public; masked vehicle + contact options. Rate-limited per IP."""
    permission_classes = [AllowAny]
    throttle_classes = [ConnectScanRateThrottle]

    def get(self, request, qr_code):
        qr = VehicleQRCode.objects.select_related('vehicle', 'vehicle__user').filter(code=qr_code.strip()).first()
        if not qr:
            return Response({"detail": "Invalid or expired QR code."}, status=status.HTTP_404_NOT_FOUND)
        vehicle = qr.vehicle

        # Analytics: Log scan (async – off request path for scale)
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
            lat = request.META.get('HTTP_X_GPS_LAT') or None
            lng = request.META.get('HTTP_X_GPS_LNG') or None
            from portal.tasks.logging_tasks import create_connect_scan_log_task
            create_connect_scan_log_task.delay(
                qr_code=qr.code,
                vehicle_id=vehicle.pk,
                scanned_by_id=request.user.pk if request.user.is_authenticated else None,
                ip_address=ip,
                user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:500],
                location_lat=lat,
                location_lng=lng,
            )
        except Exception as e:
            vehicle_log(request, "WARNING", "connect_scan_log_enqueue_failed", {"error": str(e)})

        payload = _vehicle_by_qr_payload(qr, vehicle)
        serializer = VehicleByQRResponseSerializer(payload)
        return Response(serializer.data)


def _normalize_registration(reg: str) -> str:
    """Normalize for lookup: strip, upper, single spaces removed."""
    if not reg:
        return ""
    return "".join(reg.strip().upper().split())


class VehicleByRegistrationView(APIView):
    """GET /api/connect/vehicle/by-registration/<registration_number>/ – public; same as by-qr for scan flow."""
    permission_classes = [AllowAny]
    throttle_classes = [ConnectScanRateThrottle]

    def get(self, request, registration_number):
        norm = _normalize_registration(registration_number)
        if not norm or len(norm) < 2:
            return Response(
                {"detail": "Enter a valid vehicle registration number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        vehicle = Vehicle.objects.filter(
            registration_number_normalized=norm
        ).select_related("user", "user__profile").first()
        if not vehicle:
            return Response(
                {"detail": "No Connect vehicle found with this registration number."},
                status=status.HTTP_404_NOT_FOUND,
            )
        qr = VehicleQRCode.objects.filter(vehicle=vehicle).first()
        if not qr:
            return Response(
                {"detail": "This vehicle is not linked to a Connect QR yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Analytics: Log scan async (same as by-QR flow)
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
            lat = request.META.get('HTTP_X_GPS_LAT') or None
            lng = request.META.get('HTTP_X_GPS_LNG') or None
            from portal.tasks.logging_tasks import create_connect_scan_log_task
            create_connect_scan_log_task.delay(
                qr_code=qr.code,
                vehicle_id=vehicle.pk,
                scanned_by_id=request.user.pk if request.user.is_authenticated else None,
                ip_address=ip,
                user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:500],
                location_lat=lat,
                location_lng=lng,
            )
        except Exception as e:
            vehicle_log(request, "WARNING", "connect_reg_scan_log_enqueue_failed", {"error": str(e)})
        payload = _vehicle_by_qr_payload(qr, vehicle)
        serializer = VehicleByQRResponseSerializer(payload)
        return Response(serializer.data)
