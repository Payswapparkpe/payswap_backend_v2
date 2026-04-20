"""
ParkPe Connect API – scanner send OTP and verify OTP (JWT or minimal user).
"""
import secrets

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import JSONParser
from rest_framework_simplejwt.tokens import RefreshToken

from api.utils.client_ip import get_client_ip

from portal.models import (
    Vehicle,
    VehicleQRCode,
    User,
    Profile,
    Wallet,
    ConnectQrOnboardLog,
)
from portal.services.otp_service import OTPService
from portal.utils.phone_utils import safe_normalize_phone, phone_lookup_candidates
from portal.utils.masking import mask_phone_for_log
from portal.utils.user_utils import generate_username, get_role_prefix
from api.auth_parkpe.serializers import user_to_angular

from api.throttling import ConnectScannerVerifyThrottle
from ._common import (
    vehicle_log,
    CONNECT_SCANNER_OTP_RATE_LIMIT_KEY,
    CONNECT_SCANNER_OTP_RATE_LIMIT_COUNT,
    CONNECT_SCANNER_OTP_RATE_LIMIT_WINDOW,
)


class ConnectScannerSendOTPView(APIView):
    """POST /api/connect/scanner/send-otp/ – body: { phone, qr_code }. Sends OTP to scanner; rate-limited."""
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        phone_raw = (request.data.get("phone") or "").strip()
        qr_code = (request.data.get("qr_code") or "").strip()
        if not phone_raw:
            return Response(
                {"detail": "Phone number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        normalized_phone, err = safe_normalize_phone(phone_raw)
        if err:
            return Response(
                {"detail": "Invalid mobile number. Use 10-digit Indian mobile (e.g. 9876543210)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if qr_code:
            qr = VehicleQRCode.objects.select_related("vehicle").filter(code=qr_code.strip()).first()
            if not qr or qr.vehicle.connect_scope != Vehicle.SCOPE_CONSUMER:
                return Response(
                    {"detail": "Invalid QR code."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        rate_key = f"{CONNECT_SCANNER_OTP_RATE_LIMIT_KEY}{normalized_phone}"
        timestamps = cache.get(rate_key) or []
        now = timezone.now().timestamp()
        timestamps = [t for t in timestamps if now - t < CONNECT_SCANNER_OTP_RATE_LIMIT_WINDOW]
        if len(timestamps) >= CONNECT_SCANNER_OTP_RATE_LIMIT_COUNT:
            return Response(
                {"detail": "Too many OTP requests. Please try again after 10 minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        otp_service = OTPService()
        success, msg = otp_service.send_otp(normalized_phone, user_id=None, async_send=True)
        if not success:
            return Response(
                {"detail": msg or "Failed to send OTP. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        timestamps.append(now)
        cache.set(rate_key, timestamps, timeout=CONNECT_SCANNER_OTP_RATE_LIMIT_WINDOW + 60)
        vehicle_log(request, "INFO", "connect_scanner_send_otp_ok", {"phone_masked": mask_phone_for_log(normalized_phone)})
        return Response({"message": "OTP sent to your mobile number."})


class ConnectScannerVerifyOTPView(APIView):
    """POST /api/connect/scanner/verify-otp/ – body: { phone, otp, qr_code }. Verify OTP; return JWT (existing or new minimal user)."""
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ConnectScannerVerifyThrottle]  # SEC-003: limit verify attempts per IP

    def post(self, request):
        phone_raw = (request.data.get("phone") or "").strip()
        otp_code = (request.data.get("otp") or "").strip()
        qr_code = (request.data.get("qr_code") or "").strip()
        if not phone_raw or not otp_code:
            return Response(
                {"detail": "Phone number and OTP are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        normalized_phone, err = safe_normalize_phone(phone_raw)
        if err:
            return Response(
                {"detail": "Invalid mobile number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # SEC-003: per-phone failed verify attempt counter (lock after threshold)
        fail_key = f"otp_verify_fail:{normalized_phone}"
        fail_count = cache.get(fail_key, 0)
        if fail_count >= 10:
            return Response(
                {"detail": "Too many failed attempts. Try again in 30 minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        otp_service = OTPService()
        ok, _ = otp_service.verify_otp(normalized_phone, otp_code)
        if not ok:
            cache.set(fail_key, fail_count + 1, timeout=1800)  # 30 min window
            vehicle_log(request, "WARNING", "connect_scanner_verify_otp_failed", {"phone_masked": mask_phone_for_log(normalized_phone)})
            return Response(
                {"detail": "Invalid or expired OTP. Please request a new one."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        cache.delete(fail_key)  # reset on success
        cache.set(f"connect_recent_call_verify:{normalized_phone}", 1, timeout=900)

        vehicle_for_onboard = None
        if qr_code:
            qr = VehicleQRCode.objects.select_related("vehicle").filter(code=qr_code.strip()).first()
            if not qr or qr.vehicle.connect_scope != Vehicle.SCOPE_CONSUMER:
                return Response(
                    {"detail": "Invalid QR code."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            vehicle_for_onboard = qr.vehicle

        candidates = phone_lookup_candidates(normalized_phone)
        profile = Profile.objects.filter(phone__in=candidates).select_related("user").first()
        if profile:
            user = profile.user
            is_new_user = False
            vehicle_log(request, "INFO", "connect_scanner_verify_otp_existing_user", {"user_id": user.pk})
        else:
            from portal.models import Role
            try:
                Role.objects.get(code="customer")
            except Role.DoesNotExist:
                return Response(
                    {"detail": "Registration is not configured. Contact support."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            # User.username max_length is 15 (e.g. C00XXXXXXXX); do not use a long "connect_..." string.
            username = generate_username(get_role_prefix("customer"))
            placeholder_email = f"connect_{normalized_phone}@parkpe.connect"
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username,
                        email=placeholder_email,
                        password=secrets.token_urlsafe(24),
                        role_code="customer",
                    )
                    Profile.objects.create(
                        user=user,
                        first_name="Connect",
                        last_name="User",
                        email=placeholder_email,
                        phone=normalized_phone,
                        type="individual",
                        email_verified=False,
                        phone_verified=True,
                    )
                    Wallet.objects.get_or_create(user=user, defaults={"currency": "INR"})
            except Exception as e:
                vehicle_log(request, "ERROR", "connect_scanner_verify_otp_create_user_failed", {"error": str(e)})
                return Response(
                    {"detail": "Account creation failed. Please try again."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            is_new_user = True
            vehicle_log(request, "INFO", "connect_scanner_verify_otp_new_user", {"user_id": user.pk})
        if qr_code and vehicle_for_onboard:
            try:
                ConnectQrOnboardLog.objects.create(
                    user=user,
                    qr_code=qr_code.strip()[:128],
                    vehicle=vehicle_for_onboard,
                    is_new_user=is_new_user,
                    ip_address=get_client_ip(request),
                )
            except Exception:
                vehicle_log(request, "ERROR", "connect_qr_onboard_log_failed", {"user_id": user.pk})

        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        return Response({
            "token": access,
            "refreshToken": refresh_str,
            "user": user_to_angular(user),
            "is_new_user": is_new_user,
        }, status=status.HTTP_200_OK)
