"""
ParkPe Connect API – call token (OTP-verified) and call initiate (Kaleyra click-to-call).
"""
import secrets

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import JSONParser

from api.throttling import ConnectCallRateThrottle
from portal.models import VehicleQRCode, ConnectCallLog, Profile
from portal.services.otp_service import OTPService
from portal.utils.phone_utils import safe_normalize_phone
from portal.utils.masking import mask_phone_for_log

from ._common import vehicle_log, CONNECT_CALL_TOKEN_PREFIX, CONNECT_CALL_TOKEN_TTL


def _resolve_scanner_phone_for_call(request) -> tuple[str | None, str | None, Response | None]:
    """
    Resolve scanner_phone for call/initiate: require JWT or call_token (OTP-verified).
    Returns (scanner_phone, token_qr_code, None) on success,
    or (None, None, error_response) on failure.
    """
    if getattr(request, "user", None) and getattr(request.user, "is_authenticated", False) and request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        phone = (getattr(profile, "phone", None) or "").strip()
        if phone:
            return phone, None, None
        return None, None, Response(
            {"detail": "Your account has no phone number. Add a phone in profile to use Call."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    call_token = (request.data.get("call_token") or "").strip()
    if not call_token:
        return None, None, Response(
            {
                "detail": "Authentication required. Log in, or verify your phone with OTP and use the call token from POST /api/connect/call/token/.",
                "code": "call_token_required",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )
    cache_key = f"{CONNECT_CALL_TOKEN_PREFIX}{call_token}"
    payload = cache.get(cache_key)
    if not payload or not isinstance(payload, dict):
        return None, None, Response(
            {"detail": "Invalid or expired call token. Please verify your phone again and get a new token."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    scanner_phone = (payload.get("phone") or "").strip()
    token_qr_code = (payload.get("qr_code") or "").strip()
    if not scanner_phone:
        cache.delete(cache_key)
        return None, None, Response({"detail": "Invalid call token."}, status=status.HTTP_400_BAD_REQUEST)
    cache.delete(cache_key)
    return scanner_phone, token_qr_code or None, None


class ConnectCallTokenView(APIView):
    """
    POST /api/connect/call/token/ – body: { qr_code, scanner_phone, otp }.
    Verifies OTP for scanner_phone, then returns a short-lived call_token for use in call/initiate.
    """
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ConnectCallRateThrottle]

    def post(self, request):
        qr_code = (request.data.get("qr_code") or "").strip()
        scanner_phone_raw = (request.data.get("scanner_phone") or "").strip()
        otp_code = (request.data.get("otp") or "").strip()
        if not qr_code or not scanner_phone_raw or not otp_code:
            return Response(
                {"detail": "qr_code, scanner_phone and otp are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        normalized_phone, err = safe_normalize_phone(scanner_phone_raw)
        if err:
            return Response(
                {"detail": "Invalid mobile number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not VehicleQRCode.objects.filter(code=qr_code).exists():
            return Response({"detail": "Invalid or expired QR code."}, status=status.HTTP_404_NOT_FOUND)
        otp_service = OTPService()
        ok, _ = otp_service.verify_otp(normalized_phone, otp_code)
        if not ok:
            vehicle_log(request, "WARNING", "connect_call_token_otp_failed", {"phone_masked": mask_phone_for_log(normalized_phone)})
            return Response(
                {"detail": "Invalid or expired OTP. Please request a new one."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token_id = secrets.token_urlsafe(32)
        cache_key = f"{CONNECT_CALL_TOKEN_PREFIX}{token_id}"
        cache.set(cache_key, {"phone": normalized_phone, "qr_code": qr_code}, timeout=CONNECT_CALL_TOKEN_TTL)
        vehicle_log(request, "INFO", "connect_call_token_issued", {"phone_masked": mask_phone_for_log(normalized_phone)})
        return Response({"call_token": token_id, "expires_in": CONNECT_CALL_TOKEN_TTL})


class ConnectCallInitiateView(APIView):
    """POST /api/connect/call/initiate – masked call via Kaleyra. Requires JWT or call_token."""
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ConnectCallRateThrottle]

    def post(self, request):
        qr_code = (request.data.get("qr_code") or "").strip()
        if not qr_code:
            return Response(
                {"detail": "qr_code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        scanner_phone, token_qr_code, err_resp = _resolve_scanner_phone_for_call(request)
        if err_resp is not None:
            return err_resp
        if token_qr_code and token_qr_code != qr_code:
            return Response(
                {"detail": "Call token is not valid for this QR code."},
                status=status.HTTP_403_FORBIDDEN,
            )
        vehicle_log(
            request, "INFO", "connect_call_initiate_start",
            {"qr_code_len": len(qr_code), "scanner_phone_masked": mask_phone_for_log(scanner_phone)},
        )
        qr = VehicleQRCode.objects.select_related("vehicle", "vehicle__user", "vehicle__user__profile").filter(
            code=qr_code
        ).first()
        if not qr:
            return Response({"detail": "Invalid or expired QR code."}, status=status.HTTP_404_NOT_FOUND)
        vehicle = qr.vehicle
        owner = vehicle.user
        owner_id = owner.pk
        scanner_masked = mask_phone_for_log(scanner_phone)

        phone_candidates = [scanner_phone, scanner_phone[-10:] if len(scanner_phone) >= 10 else scanner_phone]
        scanner_profile = Profile.objects.filter(phone__in=phone_candidates).only("connect_blocked_until").first()
        if scanner_profile and getattr(scanner_profile, "connect_blocked_until", None):
            if timezone.now() < scanner_profile.connect_blocked_until:
                ConnectCallLog.objects.create(
                    qr_code=qr_code[:128],
                    vehicle_id=vehicle.pk,
                    scanner_phone_masked=scanner_masked,
                    owner_id=owner_id,
                    success=False,
                )
                return Response(
                    {"detail": "You are temporarily blocked from Connect. Contact support if you believe this is an error."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        profile = getattr(owner, "profile", None)
        owner_phone = (getattr(profile, "phone", None) or "").strip()
        if not owner_phone:
            ConnectCallLog.objects.create(
                qr_code=qr_code[:128],
                vehicle_id=vehicle.pk,
                scanner_phone_masked=scanner_masked,
                owner_id=owner_id,
                success=False,
            )
            return Response(
                {"detail": "Vehicle owner has no phone number registered."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from portal.services.vendors.kaleyra import KaleyraClient
            client = KaleyraClient()
            result = client.click_to_call(
                from_number=scanner_phone,
                to_number=owner_phone,
            )
            kaleyra_call_id = ""
            if isinstance(result, dict):
                kaleyra_call_id = str(result.get("call_id") or result.get("id") or "")[:128]
            vehicle_log(
                request,
                "INFO",
                "connect_call_initiate_ok",
                {"vehicle_id": vehicle.pk, "kaleyra_call_id": kaleyra_call_id or None},
            )
            ConnectCallLog.objects.create(
                qr_code=qr_code[:128],
                vehicle_id=vehicle.pk,
                scanner_phone_masked=scanner_masked,
                owner_id=owner_id,
                success=True,
                kaleyra_call_id=kaleyra_call_id,
            )
            try:
                from portal.services.hub_cost_service import record_hub_cost
                record_hub_cost('ivr', 'kaleyra', unit_count=1, reference_id=kaleyra_call_id or None)
            except Exception:
                pass
            # Notify owner via SMS so they have context before the bridge call rings
            try:
                from portal.tasks.notification_tasks import send_sms_task
                masked_reg = vehicle.registration_number[:4] + "****"
                send_sms_task.delay(
                    phone_number=owner_phone,
                    message=f"Someone scanned your ParkPe Connect QR ({masked_reg}) and is trying to call you. Please answer the incoming call.",
                )
            except Exception:
                pass
            return Response({
                "success": True,
                "message": "Call initiated. You will be connected shortly.",
                "data": result,
            })
        except ValueError as e:
            vehicle_log(request, "WARNING", "connect_call_initiate_validation_error", {"detail": str(e)})
            ConnectCallLog.objects.create(
                qr_code=qr_code[:128],
                vehicle_id=vehicle.pk,
                scanner_phone_masked=scanner_masked,
                owner_id=owner_id,
                success=False,
            )
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            vehicle_log(request, "ERROR", "connect_call_initiate_kaleyra_error", {"vehicle_id": vehicle.pk, "error": str(e)})
            ConnectCallLog.objects.create(
                qr_code=qr_code[:128],
                vehicle_id=vehicle.pk,
                scanner_phone_masked=scanner_masked,
                owner_id=owner_id,
                success=False,
            )
            return Response(
                {"detail": "Voice service error. Please try again or contact support."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
