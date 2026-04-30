"""
Parkpe Auth API – /api/auth/* for Angular frontend.
Login by email + password or phone + password; returns JWT and user in Angular shape.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
import base64
import json
import secrets
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from api.auth_parkpe.tokens import ParkPeRefreshToken

from django.core.cache import cache

from api.throttling import AuthOTPRateThrottle, AuthLoginRateThrottle
from api.auth_parkpe.serializers import user_to_angular
from portal.models import User, Profile, Wallet, PasskeyCredential
from portal.utils.logging_helper import get_logger
from portal.utils.phone_utils import safe_normalize_phone, phone_lookup_candidates
from portal.utils.masking import redact_email, mask_phone_for_log
from portal.services.otp_service import OTPService
from portal.services.notification_service_v2 import NotificationServiceV2
from portal.services.settings_service import (
    get_security_overview,
    update_user_settings,
)
from portal.models import DevicePushToken, UserSettingsAuditLog

from api.parkpe_logging import log_parkpe

logger = get_logger(__name__)
PASSKEY_REGISTER_CHALLENGE_PREFIX = "parkpe_passkey_register_challenge:"
PASSKEY_AUTH_CHALLENGE_PREFIX = "parkpe_passkey_auth_challenge:"
PASSKEY_CHALLENGE_TTL_SEC = 5 * 60
PIN_UNLOCK_WINDOW_SECONDS = 24 * 3600
PIN_MAX_ATTEMPTS = 5
PIN_LOCK_DURATION_MINUTES = 30
FLEET_ROLE_CODES = {
    "fleet_admin",
    "fleet_manager",
    "fleet_operator",
    "fleet_dispatcher",
}
PARTNER_ROLE_CODES = {
    "super_distributor",
    "distributor",
    "retailer",
}
PARKING_ROLE_CODES = {
    "parking_owner",
    "parking_manager",
    "parking_attendant",
}


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _passkey_rp_id(request) -> str:
    return (request.get_host() or "localhost").split(":")[0]


def _passkey_origin(request) -> str:
    origin = (request.headers.get("Origin") or "").strip()
    if origin:
        return origin.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _cache_passkey_challenge(prefix: str, user_id: int, challenge_b64: str, origin: str, rp_id: str):
    cache.set(
        f"{prefix}{user_id}",
        {"challenge": challenge_b64, "origin": origin, "rp_id": rp_id},
        timeout=PASSKEY_CHALLENGE_TTL_SEC,
    )


def _pop_passkey_challenge(prefix: str, user_id: int):
    key = f"{prefix}{user_id}"
    value = cache.get(key)
    cache.delete(key)
    return value


def _webauthn_module():
    try:
        from webauthn import verify_registration_response, verify_authentication_response
        from webauthn.helpers.structs import RegistrationCredential, AuthenticationCredential
    except Exception:
        return None
    return {
        "verify_registration_response": verify_registration_response,
        "verify_authentication_response": verify_authentication_response,
        "RegistrationCredential": RegistrationCredential,
        "AuthenticationCredential": AuthenticationCredential,
    }


def _is_pin_full_auth_fresh(user) -> bool:
    if not getattr(user, "last_full_auth_at", None):
        return False
    window_end = user.last_full_auth_at + timezone.timedelta(seconds=PIN_UNLOCK_WINDOW_SECONDS)
    return timezone.now() <= window_end


def _resolve_profile_by_phone(phone_raw: str):
    """Normalize phone and return Profile if found. Returns (profile, error_response) – one is None.
    Lookup tries: +91XXXXXXXXXX, 91XXXXXXXXXX, and 10-digit XXXXXXXX so DB-stored format doesn't matter."""
    normalized_phone, err = safe_normalize_phone(phone_raw)
    if err:
        return None, {"detail": "Invalid mobile number. Use 10-digit Indian mobile (e.g. 9876543210).", "status": 400}
    candidates = phone_lookup_candidates(normalized_phone)
    profile = (
        Profile.objects.filter(phone__in=candidates).select_related("user").first()
    )
    return profile, None


@method_decorator(csrf_exempt, name="dispatch")
class AuthLoginView(APIView):
    """POST /api/auth/login – body: { email?, phone?, password, rememberMe? }. Login by email or phone + password. Rate-limited per IP."""
    authentication_classes = []  # No SessionAuthentication so DRF does not enforce CSRF
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [AuthLoginRateThrottle]

    def post(self, request):
        data = request.data or {}
        email = (data.get("email") or "").strip()
        phone_raw = (data.get("phone") or "").strip()
        password = data.get("password") or ""

        # Require exactly one of email or phone
        if email and phone_raw:
            return Response(
                {"detail": "Provide either email or mobile number, not both."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not email and not phone_raw:
            return Response(
                {"detail": "Email or mobile number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not password:
            return Response(
                {"detail": "Password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "parkpe_auth_login attempt",
            extra_data={
                "email_redacted": redact_email(email) if email else None,
                "by_phone": bool(phone_raw),
            },
        )

        profile = None
        if email:
            profile = Profile.objects.filter(email__iexact=email).select_related("user").first()
        else:
            profile, err_resp = _resolve_profile_by_phone(phone_raw)
            if err_resp:
                return Response({"detail": err_resp["detail"]}, status=status.HTTP_400_BAD_REQUEST)

        if not profile:
            logger.warning("parkpe_auth_login invalid credentials (no profile)")
            log_parkpe("parkpe_auth", "Login failed", False, request, {"reason": "no_profile"})
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = profile.user
        if not user.is_active:
            logger.warning("parkpe_auth_login account disabled", extra_data={"user_id": user.pk})
            log_parkpe("parkpe_auth", "Login failed", False, request, {"reason": "account_disabled"})
            return Response(
                {"detail": "Account is disabled."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not authenticate(request, username=user.username, password=password):
            logger.warning("parkpe_auth_login invalid credentials (auth failed)")
            log_parkpe("parkpe_auth", "Login failed", False, request, {"reason": "invalid_password"})
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        rc = str(getattr(user, "role_code", "") or "").strip().lower()
        if rc.startswith("fleet_") or rc.startswith("parking_"):
            return Response(
                {
                    "detail": "This account must sign in through the Fleet or Parking login, not the consumer login.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user.last_full_auth_at = timezone.now()
        user.save(update_fields=["last_full_auth_at"])
        logger.info("parkpe_auth_login success", extra_data={"user_id": user.pk})
        log_parkpe("parkpe_auth", "Login success", True, request, {"user_id": user.pk})
        refresh = ParkPeRefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        # SimpleJWT access token default lifetime (e.g. 5 min) in seconds for expiresIn
        from rest_framework_simplejwt.settings import api_settings as jwt_settings
        access_lifetime = jwt_settings.ACCESS_TOKEN_LIFETIME
        expires_seconds = int(access_lifetime.total_seconds()) if hasattr(access_lifetime, "total_seconds") else 300

        return Response({
            "token": access,
            "refreshToken": refresh_str,
            "user": user_to_angular(user),
            "expiresIn": expires_seconds,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthFleetLoginView(APIView):
    """POST /api/auth/fleet/login – fleet login by email/phone + password for fleet roles."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [AuthLoginRateThrottle]

    def post(self, request):
        data = request.data or {}
        email = (data.get("email") or "").strip()
        phone_raw = (data.get("phone") or "").strip()
        password = data.get("password") or ""

        if email and phone_raw:
            return Response(
                {"detail": "Provide either email or mobile number, not both."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not email and not phone_raw:
            return Response(
                {"detail": "Email or mobile number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not password:
            return Response(
                {"detail": "Password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = None
        if email:
            profile = Profile.objects.filter(email__iexact=email).select_related("user").first()
        else:
            profile, err_resp = _resolve_profile_by_phone(phone_raw)
            if err_resp:
                return Response({"detail": err_resp["detail"]}, status=status.HTTP_400_BAD_REQUEST)

        if not profile:
            return Response(
                {"detail": "Invalid fleet credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = profile.user
        if not user.is_active:
            return Response(
                {"detail": "Account is disabled."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        role_code = str(getattr(user, "role_code", "") or "").strip().lower()
        if role_code not in FLEET_ROLE_CODES:
            return Response(
                {"detail": "Fleet access is not enabled for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not authenticate(request, username=user.username, password=password):
            return Response(
                {"detail": "Invalid fleet credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = ParkPeRefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        from rest_framework_simplejwt.settings import api_settings as jwt_settings

        access_lifetime = jwt_settings.ACCESS_TOKEN_LIFETIME
        expires_seconds = int(access_lifetime.total_seconds()) if hasattr(access_lifetime, "total_seconds") else 300
        log_parkpe("parkpe_auth", "Fleet login success", True, request, {"user_id": user.pk, "role_code": role_code})
        return Response({
            "token": access,
            "refreshToken": refresh_str,
            "user": user_to_angular(user),
            "expiresIn": expires_seconds,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthPartnerLoginView(APIView):
    """POST /api/auth/partner/login – partner login by email/phone + password for distributor roles."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [AuthLoginRateThrottle]

    def post(self, request):
        data = request.data or {}
        email = (data.get("email") or "").strip()
        phone_raw = (data.get("phone") or "").strip()
        password = data.get("password") or ""

        if email and phone_raw:
            return Response(
                {"detail": "Provide either email or mobile number, not both."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not email and not phone_raw:
            return Response(
                {"detail": "Email or mobile number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not password:
            return Response(
                {"detail": "Password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = None
        if email:
            profile = Profile.objects.filter(email__iexact=email).select_related("user").first()
        else:
            profile, err_resp = _resolve_profile_by_phone(phone_raw)
            if err_resp:
                return Response({"detail": err_resp["detail"]}, status=status.HTTP_400_BAD_REQUEST)

        if not profile:
            return Response(
                {"detail": "Invalid partner credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = profile.user
        if not user.is_active:
            return Response(
                {"detail": "Account is disabled."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        role_code = str(getattr(user, "role_code", "") or "").strip().lower()
        if role_code not in PARTNER_ROLE_CODES:
            return Response(
                {"detail": "Partner/distributor access is not enabled for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not authenticate(request, username=user.username, password=password):
            return Response(
                {"detail": "Invalid partner credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = ParkPeRefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        from rest_framework_simplejwt.settings import api_settings as jwt_settings

        access_lifetime = jwt_settings.ACCESS_TOKEN_LIFETIME
        expires_seconds = int(access_lifetime.total_seconds()) if hasattr(access_lifetime, "total_seconds") else 300
        log_parkpe("parkpe_auth", "Partner login success", True, request, {"user_id": user.pk, "role_code": role_code})
        return Response({
            "token": access,
            "refreshToken": refresh_str,
            "user": user_to_angular(user),
            "expiresIn": expires_seconds,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthParkingLoginView(APIView):
    """POST /api/auth/parking/login – parking login by email/phone + password for parking roles."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [AuthLoginRateThrottle]

    def post(self, request):
        data = request.data or {}
        email = (data.get("email") or "").strip()
        phone_raw = (data.get("phone") or "").strip()
        password = data.get("password") or ""

        if email and phone_raw:
            return Response(
                {"detail": "Provide either email or mobile number, not both."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not email and not phone_raw:
            return Response(
                {"detail": "Email or mobile number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not password:
            return Response(
                {"detail": "Password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = None
        if email:
            profile = Profile.objects.filter(email__iexact=email).select_related("user").first()
        else:
            profile, err_resp = _resolve_profile_by_phone(phone_raw)
            if err_resp:
                return Response({"detail": err_resp["detail"]}, status=status.HTTP_400_BAD_REQUEST)

        if not profile:
            return Response(
                {"detail": "Invalid parking credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = profile.user
        if not user.is_active:
            return Response(
                {"detail": "Account is disabled."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        role_code = str(getattr(user, "role_code", "") or "").strip().lower()
        has_parking_role = role_code in PARKING_ROLE_CODES
        has_operator_assignment = user.parking_operator_roles.filter(is_active=True).exists()
        # Allow explicit parking roles OR mapped operator assignments OR staff users.
        if not (has_parking_role or has_operator_assignment or user.is_staff):
            return Response(
                {"detail": "Parking operator access is not enabled for this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not authenticate(request, username=user.username, password=password):
            return Response(
                {"detail": "Invalid parking credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = ParkPeRefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        from rest_framework_simplejwt.settings import api_settings as jwt_settings

        access_lifetime = jwt_settings.ACCESS_TOKEN_LIFETIME
        expires_seconds = int(access_lifetime.total_seconds()) if hasattr(access_lifetime, "total_seconds") else 300
        log_parkpe("parkpe_auth", "Parking login success", True, request, {"user_id": user.pk, "role_code": role_code})
        return Response({
            "token": access,
            "refreshToken": refresh_str,
            "user": user_to_angular(user),
            "expiresIn": expires_seconds,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthOTPRequestView(APIView):
    """POST /api/auth/otp/request – body: { phone }. Sends OTP via Kaleyra to registered mobile. Login only for existing users. Rate-limited per IP."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [AuthOTPRateThrottle]

    def post(self, request):
        data = request.data or {}
        phone_raw = (data.get("phone") or "").strip()
        if not phone_raw:
            return Response(
                {"detail": "Mobile number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile, err_resp = _resolve_profile_by_phone(phone_raw)
        if err_resp:
            return Response({"detail": err_resp["detail"]}, status=err_resp["status"])
        if not profile:
            logger.warning("parkpe_auth_otp_request no account", extra_data={"phone_masked": phone_raw[:2] + "****"})
            return Response(
                {"detail": "No account found with this mobile number. Please sign up or use email login."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user = profile.user
        if not user.is_active:
            return Response(
                {"detail": "Account is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )
        otp_service = OTPService()
        success, msg = otp_service.send_otp(profile.phone, user_id=user.pk, async_send=True)
        if not success:
            message = msg or "Failed to send OTP. Please try again."
            if "AD400" in message or "disabled by admin" in message.lower():
                return Response(
                    {"detail": "AD400", "error": "AD400"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.info("parkpe_auth_otp_request sent", extra_data={"user_id": user.pk})
        log_parkpe("parkpe_auth", "OTP request sent", True, request, {"user_id": user.pk})
        return Response({
            "message": "OTP sent to your mobile number.",
            "expires_in": otp_service.otp_expiry,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthOTPVerifyView(APIView):
    """POST /api/auth/otp/verify – body: { phone, otp }. Verifies OTP and returns JWT (same shape as login). Rate-limited per IP."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [AuthOTPRateThrottle]

    def post(self, request):
        data = request.data or {}
        phone_raw = (data.get("phone") or "").strip()
        otp_code = (data.get("otp") or "").strip()
        if not phone_raw:
            return Response(
                {"detail": "Mobile number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not otp_code:
            return Response(
                {"detail": "OTP is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile, err_resp = _resolve_profile_by_phone(phone_raw)
        if err_resp:
            return Response({"detail": err_resp["detail"]}, status=err_resp["status"])
        if not profile:
            return Response(
                {"detail": "Invalid mobile number or OTP."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        otp_service = OTPService()
        ok, reason = otp_service.verify_otp(profile.phone, otp_code)
        if not ok:
            if reason == "locked":
                return Response(
                    {"detail": "Too many failed attempts. Try again in 30 minutes."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            logger.warning("parkpe_auth_otp_verify failed", extra_data={"user_id": profile.user_id})
            log_parkpe("parkpe_auth", "OTP verify failed", False, request, {"reason": "invalid_otp"})
            return Response(
                {"detail": "Invalid or expired OTP. Please request a new one."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = profile.user
        if not user.is_active:
            return Response(
                {"detail": "Account is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )
        user.last_full_auth_at = timezone.now()
        user.save(update_fields=["last_full_auth_at"])
        logger.info("parkpe_auth_otp_verify success", extra_data={"user_id": user.pk})
        log_parkpe("parkpe_auth", "OTP verify success", True, request, {"user_id": user.pk})
        refresh = ParkPeRefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        from rest_framework_simplejwt.settings import api_settings as jwt_settings
        access_lifetime = jwt_settings.ACCESS_TOKEN_LIFETIME
        expires_seconds = int(access_lifetime.total_seconds()) if hasattr(access_lifetime, "total_seconds") else 300
        return Response({
            "token": access,
            "refreshToken": refresh_str,
            "user": user_to_angular(user),
            "expiresIn": expires_seconds,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthProfileView(APIView):
    """GET /api/auth/profile and PATCH /api/auth/profile – require JWT."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        logger.info("parkpe_auth_profile get", extra_data={"user_id": request.user.pk})
        log_parkpe("parkpe_auth", "Profile get", True, request, {"user_id": request.user.pk})
        return Response(user_to_angular(request.user))

    def patch(self, request):
        user = request.user
        profile = getattr(user, "profile", None)
        if not profile:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data or {}
        changed = False
        if "profileType" in data and data["profileType"] is not None:
            profile_type = str(data["profileType"]).strip().lower()
            if profile_type in {"individual", "business", "corporate"}:
                profile.type = profile_type
                changed = True
        if "name" in data:
            parts = (data.get("name") or "").strip().split(None, 1)
            profile.first_name = parts[0] if parts else profile.first_name
            profile.last_name = parts[1] if len(parts) > 1 else (profile.last_name or "")
            changed = True
        if "phone" in data and data["phone"] is not None:
            profile.phone = str(data["phone"]).strip()
            changed = True
        addr_keys = (
            ("addressLine1", "address_line_1"),
            ("addressLine2", "address_line_2"),
            ("city", "city"),
            ("state", "state"),
            ("pincode", "pincode"),
            ("countryOfResidence", "country_of_residence"),
        )
        for json_key, model_attr in addr_keys:
            if json_key in data and data[json_key] is not None:
                val = str(data[json_key]).strip()
                setattr(profile, model_attr, val or None)
                changed = True
        is_business_profile = profile.type in {"business", "corporate"}
        kyb_keys = (
            ("businessName", "business_name"),
            ("businessRegistrationNumber", "business_registration_number"),
            ("businessType", "business_type"),
            ("taxId", "tax_id"),
        )
        if is_business_profile:
            for json_key, model_attr in kyb_keys:
                if json_key in data and data[json_key] is not None:
                    val = str(data[json_key]).strip()
                    setattr(profile, model_attr, val or None)
                    changed = True
            if "gstNumber" in data and data["gstNumber"] is not None:
                gst = str(data["gstNumber"]).strip().upper()[:15]
                profile.gst_number = gst or None
                changed = True
        else:
            for model_attr in ("business_name", "business_registration_number", "business_type", "gst_number", "tax_id"):
                if getattr(profile, model_attr, None):
                    setattr(profile, model_attr, None)
                    changed = True
        if changed:
            profile.save()

        settings_updates = {}
        if any(k in data for k in ("languagePreference", "timezone", "currencyPreference", "notificationPreferences", "settings")):
            privacy_blob = {}
            settings_blob = data.get("settings") if isinstance(data.get("settings"), dict) else {}
            if isinstance(settings_blob.get("privacy"), dict):
                privacy_blob = settings_blob.get("privacy", {})
            settings_updates = {
                "preferences": {
                    "language": data.get("languagePreference", profile.language_preference),
                    "timezone": data.get("timezone", profile.timezone),
                    "currency": data.get("currencyPreference", profile.currency_preference),
                },
                "notificationPreferences": data.get("notificationPreferences", profile.notification_preferences),
                "privacy": privacy_blob,
            }
            update_user_settings(
                user=user,
                updates=settings_updates,
                actor_user=request.user,
                source=UserSettingsAuditLog.SOURCE_PARKPE,
                request=request,
            )
        logger.info("parkpe_auth_profile update", extra_data={"user_id": user.pk})
        return Response(user_to_angular(user))


@method_decorator(csrf_exempt, name="dispatch")
class AuthSecurityOverviewView(APIView):
    """GET /api/auth/security-overview – unified security/session state."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_security_overview(request.user))


@method_decorator(csrf_exempt, name="dispatch")
class AuthSessionsRevokeView(APIView):
    """POST /api/auth/sessions/revoke – revoke one/all registered devices."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        data = request.data or {}
        device_id = data.get("device_id")
        qs = DevicePushToken.objects.filter(user=request.user)
        if device_id:
            qs = qs.filter(id=device_id)
        updated = qs.update(is_active=False)
        UserSettingsAuditLog.objects.create(
            user=request.user,
            actor_user=request.user,
            source=UserSettingsAuditLog.SOURCE_PARKPE,
            action="sessions_revoked",
            change_summary={"device_id": device_id, "revoked_count": updated},
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
        )
        return Response({"success": True, "revoked": updated})


@method_decorator(csrf_exempt, name="dispatch")
class AuthSecurityActivityView(APIView):
    """GET /api/auth/security-activity – recent settings/security activity for current user."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = list(
            UserSettingsAuditLog.objects.filter(user=request.user)
            .order_by("-created_at")[:50]
            .values("id", "source", "action", "change_summary", "created_at")
        )
        return Response({"items": items})


@method_decorator(csrf_exempt, name="dispatch")
class AuthLogoutView(APIView):
    """POST /api/auth/logout – no-op for JWT (client discards token)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        logger.info("parkpe_auth_logout", extra_data={"user_id": getattr(request.user, "pk", None)})
        log_parkpe("parkpe_auth", "Logout", True, request, {"user_id": getattr(request.user, "pk", None)})
        return Response({"success": True})


def _validate_register_payload(data, require_phone=True):
    """Validate registration payload; return (None, error_response) or (dict, None)."""
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""
    confirm = data.get("confirmPassword") or ""
    accept_terms = data.get("acceptTerms") is True
    # Optional address from pincode lookup
    pincode = (data.get("pincode") or "").strip() or None
    address_line_1 = (data.get("addressLine1") or data.get("address_line_1") or "").strip() or None
    address_line_2 = (data.get("addressLine2") or data.get("address_line_2") or "").strip() or None
    city = (data.get("city") or "").strip() or None
    state = (data.get("state") or "").strip() or None

    if not all([name, email, password]):
        return None, ({"message": "Name, email and password are required.", "userId": ""}, status.HTTP_400_BAD_REQUEST)
    if require_phone and not phone:
        return None, ({"message": "Mobile number is required.", "userId": ""}, status.HTTP_400_BAD_REQUEST)
    if password != confirm:
        return None, ({"message": "Password and confirm password do not match.", "userId": ""}, status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(password, user=None)
    except DjangoValidationError as e:
        return None, ({"message": " ".join(e.messages), "userId": ""}, status.HTTP_400_BAD_REQUEST)
    if not accept_terms:
        return None, ({"message": "You must accept the terms.", "userId": ""}, status.HTTP_400_BAD_REQUEST)
    if Profile.objects.filter(email__iexact=email).exists():
        return None, ({"message": "An account with this email already exists.", "userId": ""}, status.HTTP_400_BAD_REQUEST)
    if phone:
        normalized_phone, err = safe_normalize_phone(phone)
        if err:
            return None, ({"message": "Invalid mobile number. Use 10-digit Indian mobile (e.g. 9876543210).", "userId": ""}, status.HTTP_400_BAD_REQUEST)
        candidates = phone_lookup_candidates(normalized_phone)
        if Profile.objects.filter(phone__in=candidates).exists():
            return None, ({"message": "An account with this phone already exists.", "userId": ""}, status.HTTP_400_BAD_REQUEST)
        phone = normalized_phone
    return {
        "name": name,
        "email": email,
        "phone": phone or None,
        "password": password,
        "accept_terms": accept_terms,
        "pincode": pincode,
        "address_line_1": address_line_1,
        "address_line_2": address_line_2,
        "city": city,
        "state": state,
    }, None


PENDING_REGISTER_CACHE_PREFIX = "parkpe_register_pending:"
PENDING_REGISTER_TTL = 600  # 10 minutes


@method_decorator(csrf_exempt, name="dispatch")
class AuthRegisterSendOTPView(APIView):
    """POST /api/auth/register/send-otp – body: same as register. Validates, sends OTP to mobile, stores pending signup in cache. Rate-limited per IP."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [AuthOTPRateThrottle]

    def post(self, request):
        data = request.data or {}
        payload, err = _validate_register_payload(data, require_phone=True)
        if err:
            body, code = err
            return Response(body, status=code)

        from portal.models import Role
        try:
            Role.objects.get(code="customer")
        except Role.DoesNotExist:
            return Response(
                {"message": "Registration is not configured. Contact support.", "userId": ""},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        normalized_phone = payload["phone"]
        otp_service = OTPService()
        success, msg = otp_service.send_otp(normalized_phone, user_id=None, async_send=True)
        if not success:
            message = msg or "Failed to send OTP. Please try again."
            if "AD400" in message or "disabled by admin" in message.lower():
                return Response(
                    {"message": "AD400", "error": "AD400", "userId": ""},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"message": message, "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"{PENDING_REGISTER_CACHE_PREFIX}{normalized_phone}"
        cache.set(cache_key, payload, timeout=PENDING_REGISTER_TTL)
        logger.info(
            "parkpe_auth_register_send_otp sent",
            extra_data={"email_redacted": redact_email(payload["email"]), "phone_masked": mask_phone_for_log(normalized_phone)},
        )
        log_parkpe("parkpe_auth", "Register OTP sent", True, request, {"email_redacted": redact_email(payload["email"])})
        return Response({
            "message": "OTP sent to your mobile number.",
            "expires_in": otp_service.otp_expiry,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthRegisterVerifyView(APIView):
    """POST /api/auth/register/verify – body: { phone, otp, name, email, password, confirmPassword, acceptTerms }. Verifies OTP, creates user + profile with phone_verified=True, returns JWT. Rate-limited per IP."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [AuthOTPRateThrottle]

    def post(self, request):
        data = request.data or {}
        phone_raw = (data.get("phone") or "").strip()
        otp_code = (data.get("otp") or "").strip()
        if not phone_raw or not otp_code:
            return Response(
                {"message": "Mobile number and OTP are required.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_phone, err = safe_normalize_phone(phone_raw)
        if err:
            return Response(
                {"message": "Invalid mobile number.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_service = OTPService()
        ok, reason = otp_service.verify_otp(normalized_phone, otp_code)
        if not ok:
            if reason == "locked":
                return Response(
                    {"message": "Too many failed attempts. Try again in 30 minutes.", "userId": ""},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            logger.warning("parkpe_auth_register_verify otp_failed", extra_data={"phone_masked": mask_phone_for_log(normalized_phone)})
            log_parkpe("parkpe_auth", "Register verify failed", False, request, {"reason": "invalid_otp"})
            return Response(
                {"message": "Invalid or expired OTP. Please request a new one.", "userId": ""},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        cache_key = f"{PENDING_REGISTER_CACHE_PREFIX}{normalized_phone}"
        payload = cache.get(cache_key)
        if not payload:
            return Response(
                {"message": "Registration session expired. Please start again.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if payload.get("phone") != normalized_phone:
            return Response(
                {"message": "Mobile number does not match. Please start again.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache.delete(cache_key)

        name = payload["name"]
        email = payload["email"]
        password = payload["password"]

        from portal.models import Role
        from django.db import transaction
        try:
            Role.objects.get(code="customer")
        except Role.DoesNotExist:
            return Response(
                {"message": "Registration is not configured. Contact support.", "userId": ""},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        first_name = name.split(None, 1)[0] if name else "User"
        last_name = name.split(None, 1)[1] if name and len(name.split(None, 1)) > 1 else ""

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    role_code="customer",
                )
                user.email = email
                user.save()
                Profile.objects.create(
                    user=user,
                    first_name=first_name,
                    last_name=last_name or "",
                    email=email,
                    phone=normalized_phone,
                    type="individual",
                    email_verified=False,
                    phone_verified=True,
                    pincode=payload.get("pincode"),
                    address_line_1=payload.get("address_line_1"),
                    address_line_2=payload.get("address_line_2"),
                    city=payload.get("city"),
                    state=payload.get("state"),
                )
                Wallet.objects.get_or_create(user=user, defaults={"currency": "INR"})
        except Exception as e:
            logger.exception("parkpe_auth_register_verify create_user failed", extra_data={"email_redacted": redact_email(email)})
            return Response(
                {"message": "Account creation failed. Please try again.", "userId": ""},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Send welcome email (async, non-blocking)
        try:
            NotificationServiceV2.send_email(
                to_email=email,
                subject="Welcome to ParkPe",
                template_name="portal/emails/parkpe_welcome.html",
                context={
                    "first_name": first_name,
                    "signin_url": "",  # Optional: set PARKPE_APP_URL in config and pass login link
                },
                user_id=user.pk,
                async_send=True,
                use_parkpe=True,
            )
        except Exception as mail_err:
            logger.warning(
                "parkpe_auth_register_verify welcome_email_failed",
                extra_data={"user_id": user.pk, "error": str(mail_err)},
            )

        user.last_full_auth_at = timezone.now()
        user.save(update_fields=["last_full_auth_at"])
        logger.info("parkpe_auth_register_verify success", extra_data={"user_id": user.pk})
        log_parkpe("parkpe_auth", "Register success", True, request, {"user_id": user.pk})
        refresh = ParkPeRefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        from rest_framework_simplejwt.settings import api_settings as jwt_settings
        access_lifetime = jwt_settings.ACCESS_TOKEN_LIFETIME
        expires_seconds = int(access_lifetime.total_seconds()) if hasattr(access_lifetime, "total_seconds") else 300
        return Response({
            "message": "Registration successful.",
            "userId": str(user.pk),
            "token": access,
            "refreshToken": refresh_str,
            "user": user_to_angular(user),
            "expiresIn": expires_seconds,
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class AuthRegisterView(APIView):
    """POST /api/auth/register – body: { name, email, phone, password, confirmPassword, acceptTerms }. Creates user + profile (no OTP). Prefer register/send-otp + register/verify for mobile verification."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        return Response(
            {
                "message": "Direct registration is deprecated. Use /api/auth/register/send-otp and /api/auth/register/verify.",
                "otp_url": "/api/auth/register/send-otp",
            },
            status=status.HTTP_410_GONE,
        )


@method_decorator(csrf_exempt, name="dispatch")
class AuthPinStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        user = request.user
        now = timezone.now()
        locked_until = getattr(user, "pin_locked_until", None)
        return Response(
            {
                "hasPin": bool(getattr(user, "pin_hash", None)),
                "pinSetAt": user.pin_set_at.isoformat() if getattr(user, "pin_set_at", None) else None,
                "pinLockedUntil": locked_until.isoformat() if locked_until else None,
                "isLocked": bool(locked_until and locked_until > now),
                "fullAuthFresh": _is_pin_full_auth_fresh(user),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AuthPinSetView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        user = request.user
        body = request.data or {}
        pin = str(body.get("pin") or "").strip()
        current_pin = str(body.get("currentPin") or "").strip()
        force_reset = bool(body.get("forceReset"))

        if not pin or not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
            return Response({"detail": "PIN must be 4 to 6 digits."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        if user.pin_locked_until and user.pin_locked_until > now:
            return Response(
                {"detail": "PIN unlock is temporarily locked. Please verify with OTP.", "error": "PIN_LOCKED"},
                status=status.HTTP_423_LOCKED,
            )
        if not _is_pin_full_auth_fresh(user):
            return Response(
                {"detail": "Full verification is required before changing PIN.", "error": "PIN_FULL_AUTH_REQUIRED"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.pin_hash and not force_reset:
            if not current_pin or not check_password(current_pin, user.pin_hash):
                return Response(
                    {"detail": "Current PIN is incorrect.", "error": "PIN_CURRENT_MISMATCH"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        user.pin_hash = make_password(pin, salt=None)
        user.pin_set_at = now
        user.pin_failed_attempts = 0
        user.pin_locked_until = None
        user.save(update_fields=["pin_hash", "pin_set_at", "pin_failed_attempts", "pin_locked_until"])
        return Response({"success": True, "hasPin": True})


@method_decorator(csrf_exempt, name="dispatch")
class AuthPinVerifyView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        user = request.user
        pin = str((request.data or {}).get("pin") or "").strip()
        if not pin:
            return Response({"detail": "PIN is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.pin_hash:
            return Response(
                {"detail": "No PIN is set for this account.", "error": "PIN_NOT_SET"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        if user.pin_locked_until and user.pin_locked_until > now:
            return Response(
                {
                    "detail": "Too many failed attempts. PIN unlock is temporarily locked.",
                    "error": "PIN_LOCKED",
                    "pinLockedUntil": user.pin_locked_until.isoformat(),
                },
                status=status.HTTP_423_LOCKED,
            )
        if not _is_pin_full_auth_fresh(user):
            return Response(
                {"detail": "PIN window expired. Verify with OTP and set PIN again.", "error": "PIN_FULL_AUTH_REQUIRED"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if check_password(pin, user.pin_hash):
            user.pin_failed_attempts = 0
            user.save(update_fields=["pin_failed_attempts"])
            return Response({"success": True, "verified": True})

        user.pin_failed_attempts = int(user.pin_failed_attempts or 0) + 1
        if user.pin_failed_attempts >= PIN_MAX_ATTEMPTS:
            user.pin_locked_until = now + timezone.timedelta(minutes=PIN_LOCK_DURATION_MINUTES)
            user.save(update_fields=["pin_failed_attempts", "pin_locked_until"])
            return Response(
                {
                    "detail": "Too many wrong PIN attempts. Try again later or use OTP reset.",
                    "error": "PIN_LOCKED",
                    "pinLockedUntil": user.pin_locked_until.isoformat(),
                },
                status=status.HTTP_423_LOCKED,
            )

        user.save(update_fields=["pin_failed_attempts"])
        return Response(
            {
                "detail": "Invalid PIN.",
                "error": "PIN_INVALID",
                "remainingAttempts": PIN_MAX_ATTEMPTS - user.pin_failed_attempts,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        enabled = PasskeyCredential.objects.filter(user=request.user, is_active=True).exists()
        return Response({
            "supported": _webauthn_module() is not None,
            "enabled": enabled,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyRegisterOptionsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        if _webauthn_module() is None:
            return Response(
                {"detail": "Passkey backend is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        user = request.user
        challenge = _b64url_encode(secrets.token_bytes(32))
        rp_id = _passkey_rp_id(request)
        origin = _passkey_origin(request)
        _cache_passkey_challenge(PASSKEY_REGISTER_CHALLENGE_PREFIX, user.pk, challenge, origin, rp_id)

        profile = getattr(user, "profile", None)
        display_name = (
            f"{(profile.first_name or '').strip()} {(profile.last_name or '').strip()}".strip()
            if profile
            else user.username
        ) or user.username
        user_identifier = _b64url_encode(f"parkpe:{user.pk}".encode("utf-8"))

        existing = PasskeyCredential.objects.filter(user=user, is_active=True).values_list("credential_id", "transports")
        exclude_credentials = [
            {
                "type": "public-key",
                "id": cred_id,
                "transports": transports or ["internal"],
            }
            for cred_id, transports in existing
        ]

        return Response(
            {
                "publicKey": {
                    "challenge": challenge,
                    "rp": {"name": "ParkPe", "id": rp_id},
                    "user": {
                        "id": user_identifier,
                        "name": user.username,
                        "displayName": display_name,
                    },
                    "pubKeyCredParams": [
                        {"type": "public-key", "alg": -7},
                        {"type": "public-key", "alg": -257},
                    ],
                    "timeout": 60000,
                    "attestation": "none",
                    "excludeCredentials": exclude_credentials,
                    "authenticatorSelection": {
                        "authenticatorAttachment": "platform",
                        "residentKey": "preferred",
                        "userVerification": "required",
                    },
                }
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyRegisterVerifyView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        webauthn = _webauthn_module()
        if webauthn is None:
            return Response(
                {"detail": "Passkey backend is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = request.data or {}
        credential_data = payload.get("credential")
        if not isinstance(credential_data, dict):
            return Response({"detail": "Credential payload is required."}, status=status.HTTP_400_BAD_REQUEST)

        challenge_payload = _pop_passkey_challenge(PASSKEY_REGISTER_CHALLENGE_PREFIX, request.user.pk)
        if not challenge_payload:
            return Response({"detail": "Passkey setup session expired. Retry setup."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            verification = webauthn["verify_registration_response"](
                credential=webauthn["RegistrationCredential"].parse_raw(json.dumps(credential_data)),
                expected_challenge=_b64url_decode(challenge_payload["challenge"]),
                expected_origin=challenge_payload["origin"],
                expected_rp_id=challenge_payload["rp_id"],
                require_user_verification=True,
            )
        except Exception as exc:
            logger.warning(
                "parkpe_passkey_register_verify_failed",
                extra_data={"user_id": request.user.pk, "error": str(exc)},
            )
            return Response({"detail": "Passkey verification failed."}, status=status.HTTP_400_BAD_REQUEST)

        credential_id = _b64url_encode(verification.credential_id)
        transports = credential_data.get("response", {}).get("transports") or ["internal"]

        PasskeyCredential.objects.update_or_create(
            credential_id=credential_id,
            defaults={
                "user": request.user,
                "public_key": verification.credential_public_key,
                "sign_count": verification.sign_count or 0,
                "transports": transports,
                "is_active": True,
                "last_used_at": timezone.now(),
            },
        )
        return Response({"success": True, "enabled": True})


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyAuthOptionsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        if _webauthn_module() is None:
            return Response(
                {"detail": "Passkey backend is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        user = request.user
        credentials = list(
            PasskeyCredential.objects.filter(user=user, is_active=True).values_list("credential_id", "transports")
        )
        if not credentials:
            return Response({"detail": "No passkey is registered for this account."}, status=status.HTTP_400_BAD_REQUEST)

        challenge = _b64url_encode(secrets.token_bytes(32))
        rp_id = _passkey_rp_id(request)
        origin = _passkey_origin(request)
        _cache_passkey_challenge(PASSKEY_AUTH_CHALLENGE_PREFIX, user.pk, challenge, origin, rp_id)

        return Response(
            {
                "publicKey": {
                    "challenge": challenge,
                    "rpId": rp_id,
                    "timeout": 60000,
                    "userVerification": "required",
                    "allowCredentials": [
                        {
                            "type": "public-key",
                            "id": credential_id,
                            "transports": transports or ["internal"],
                        }
                        for credential_id, transports in credentials
                    ],
                }
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyAuthVerifyView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        webauthn = _webauthn_module()
        if webauthn is None:
            return Response(
                {"detail": "Passkey backend is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = request.data or {}
        credential_data = payload.get("credential")
        if not isinstance(credential_data, dict):
            return Response({"detail": "Credential payload is required."}, status=status.HTTP_400_BAD_REQUEST)

        raw_id = (credential_data.get("rawId") or credential_data.get("id") or "").strip()
        if not raw_id:
            return Response({"detail": "Credential id is missing."}, status=status.HTTP_400_BAD_REQUEST)

        stored = PasskeyCredential.objects.filter(
            user=request.user,
            credential_id=raw_id,
            is_active=True,
        ).first()
        if not stored:
            return Response({"detail": "Passkey not recognized for this user."}, status=status.HTTP_400_BAD_REQUEST)

        challenge_payload = _pop_passkey_challenge(PASSKEY_AUTH_CHALLENGE_PREFIX, request.user.pk)
        if not challenge_payload:
            return Response({"detail": "Passkey sign-in session expired. Retry unlock."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            verification = webauthn["verify_authentication_response"](
                credential=webauthn["AuthenticationCredential"].parse_raw(json.dumps(credential_data)),
                expected_challenge=_b64url_decode(challenge_payload["challenge"]),
                expected_origin=challenge_payload["origin"],
                expected_rp_id=challenge_payload["rp_id"],
                credential_public_key=bytes(stored.public_key),
                credential_current_sign_count=stored.sign_count or 0,
                require_user_verification=True,
            )
        except Exception as exc:
            logger.warning(
                "parkpe_passkey_auth_verify_failed",
                extra_data={"user_id": request.user.pk, "error": str(exc)},
            )
            return Response({"detail": "Passkey verification failed."}, status=status.HTTP_400_BAD_REQUEST)

        stored.sign_count = verification.new_sign_count or stored.sign_count
        stored.last_used_at = timezone.now()
        stored.save(update_fields=["sign_count", "last_used_at", "updated_at"])
        return Response({"success": True, "verified": True})


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyDisableView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        PasskeyCredential.objects.filter(user=request.user, is_active=True).update(is_active=False, updated_at=timezone.now())
        return Response({"success": True, "enabled": False})


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyCredentialsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        credentials = (
            PasskeyCredential.objects.filter(user=request.user, is_active=True)
            .order_by("-updated_at")
        )
        items = [
            {
                "id": c.id,
                "label": c.label or "My Device",
                "transports": c.transports or [],
                "createdAt": c.created_at.isoformat() if c.created_at else None,
                "lastUsedAt": c.last_used_at.isoformat() if c.last_used_at else None,
            }
            for c in credentials
        ]
        return Response({"items": items})


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyCredentialDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def patch(self, request, credential_id: int):
        credential = PasskeyCredential.objects.filter(
            id=credential_id, user=request.user, is_active=True
        ).first()
        if not credential:
            return Response({"detail": "Passkey not found."}, status=status.HTTP_404_NOT_FOUND)

        label = str((request.data or {}).get("label") or "").strip()
        if not label:
            return Response({"detail": "Label is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(label) > 80:
            return Response({"detail": "Label must be 80 characters or less."}, status=status.HTTP_400_BAD_REQUEST)

        credential.label = label
        credential.save(update_fields=["label", "updated_at"])
        return Response({"success": True, "id": credential.id, "label": credential.label})

    def delete(self, request, credential_id: int):
        credential = PasskeyCredential.objects.filter(
            id=credential_id, user=request.user, is_active=True
        ).first()
        if not credential:
            return Response({"detail": "Passkey not found."}, status=status.HTTP_404_NOT_FOUND)
        credential.is_active = False
        credential.save(update_fields=["is_active", "updated_at"])
        enabled = PasskeyCredential.objects.filter(user=request.user, is_active=True).exists()
        return Response({"success": True, "enabled": enabled})


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyRecoveryRequestOTPView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    throttle_classes = [AuthOTPRateThrottle]

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        phone = (getattr(profile, "phone", "") or "").strip()
        if not phone:
            return Response(
                {"detail": "No registered mobile number found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        otp_service = OTPService()
        success, msg = otp_service.send_otp(phone, user_id=request.user.pk, async_send=True)
        if not success:
            message = msg or "Failed to send OTP. Please try again."
            if "AD400" in message or "disabled by admin" in message.lower():
                return Response({"detail": "AD400", "error": "AD400"}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "OTP sent to your mobile number.", "expires_in": otp_service.otp_expiry})


@method_decorator(csrf_exempt, name="dispatch")
class AuthPasskeyRecoveryVerifyOTPView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    throttle_classes = [AuthOTPRateThrottle]

    def post(self, request):
        otp_code = str((request.data or {}).get("otp") or "").strip()
        if not otp_code:
            return Response({"detail": "OTP is required."}, status=status.HTTP_400_BAD_REQUEST)
        profile = getattr(request.user, "profile", None)
        phone = (getattr(profile, "phone", "") or "").strip()
        if not phone:
            return Response(
                {"detail": "No registered mobile number found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_service = OTPService()
        ok, reason = otp_service.verify_otp(phone, otp_code)
        if not ok:
            if reason == "locked":
                return Response(
                    {"detail": "Too many failed attempts. Try again in 30 minutes."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {"detail": "Invalid or expired OTP. Please request a new one."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        revoked = PasskeyCredential.objects.filter(user=request.user, is_active=True).update(
            is_active=False,
            updated_at=timezone.now(),
        )
        return Response({"success": True, "revoked": revoked, "enabled": False})


@method_decorator(csrf_exempt, name="dispatch")
class AuthForgotPasswordView(APIView):
    """POST /api/auth/forgot-password – body: { email }. Placeholder: returns message."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        email = (request.data or {}).get("email") or ""
        logger.info("parkpe_auth_forgot_password request", extra_data={"email_redacted": redact_email(email)})
        if not email:
            logger.warning("parkpe_auth_forgot_password missing email")
            return Response(
                {"message": "Email is required.", "resetTokenSent": False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "message": "Password reset is not yet available. Please contact support.",
                "resetTokenSent": False,
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
