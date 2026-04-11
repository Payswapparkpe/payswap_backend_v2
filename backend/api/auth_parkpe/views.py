"""
Parkpe Auth API – /api/auth/* for Angular frontend.
Login by email + password or phone + password; returns JWT and user in Angular shape.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import authenticate
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken

from django.core.cache import cache

from api.throttling import AuthOTPRateThrottle, AuthLoginRateThrottle
from api.auth_parkpe.serializers import user_to_angular
from portal.models import User, Profile, Wallet
from portal.utils.logging_helper import get_logger
from portal.utils.phone_utils import safe_normalize_phone, phone_lookup_candidates
from portal.utils.masking import redact_email, mask_phone_for_log
from portal.services.otp_service import OTPService
from portal.services.notification_service_v2 import NotificationServiceV2

from api.parkpe_logging import log_parkpe

logger = get_logger(__name__)


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

        logger.info("parkpe_auth_login success", extra_data={"user_id": user.pk})
        log_parkpe("parkpe_auth", "Login success", True, request, {"user_id": user.pk})
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        # SimpleJWT access token default lifetime (e.g. 5 min) in seconds for expiresIn
        from django.conf import settings
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
            return Response(
                {"detail": msg or "Failed to send OTP. Please try again."},
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
        logger.info("parkpe_auth_otp_verify success", extra_data={"user_id": user.pk})
        log_parkpe("parkpe_auth", "OTP verify success", True, request, {"user_id": user.pk})
        refresh = RefreshToken.for_user(user)
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
        if "name" in data:
            parts = (data.get("name") or "").strip().split(None, 1)
            profile.first_name = parts[0] if parts else profile.first_name
            profile.last_name = parts[1] if len(parts) > 1 else (profile.last_name or "")
            profile.save()
        if "phone" in data and data["phone"] is not None:
            profile.phone = str(data["phone"]).strip()
            profile.save()
        logger.info("parkpe_auth_profile update", extra_data={"user_id": user.pk})
        return Response(user_to_angular(user))


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
    if len(password) < 6:
        return None, ({"message": "Password must be at least 6 characters.", "userId": ""}, status.HTTP_400_BAD_REQUEST)
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
            return Response(
                {"message": msg or "Failed to send OTP. Please try again.", "userId": ""},
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

        logger.info("parkpe_auth_register_verify success", extra_data={"user_id": user.pk})
        log_parkpe("parkpe_auth", "Register success", True, request, {"user_id": user.pk})
        refresh = RefreshToken.for_user(user)
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
        data = request.data or {}
        payload, err = _validate_register_payload(data, require_phone=False)
        if err:
            body, code = err
            return Response(body, status=code)

        name = payload["name"]
        email = payload["email"]
        phone = payload["phone"]
        password = payload["password"]

        logger.info("parkpe_auth_register attempt", extra_data={"email_redacted": redact_email(email)})

        from portal.models import Role
        try:
            Role.objects.get(code="customer")
        except Role.DoesNotExist:
            return Response(
                {"message": "Registration is not configured. Contact support.", "userId": ""},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        first_name = name.split(None, 1)[0] if name else "User"
        last_name = name.split(None, 1)[1] if name and len(name.split(None, 1)) > 1 else ""

        user = User.objects.create_user(
            email=email,
            password=password,
            role_code="customer",
        )
        user.email = email
        user.save()

        if not phone:
            phone = f"91{user.pk:010d}"
        Profile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name or "",
            email=email,
            phone=phone,
            type="individual",
            email_verified=False,
            phone_verified=False,
            pincode=payload.get("pincode"),
            address_line_1=payload.get("address_line_1"),
            address_line_2=payload.get("address_line_2"),
            city=payload.get("city"),
            state=payload.get("state"),
        )

        # Send welcome email (async, non-blocking)
        try:
            NotificationServiceV2.send_email(
                to_email=email,
                subject="Welcome to ParkPe",
                template_name="portal/emails/parkpe_welcome.html",
                context={"first_name": first_name, "signin_url": ""},
                user_id=user.pk,
                async_send=True,
                use_parkpe=True,
            )
        except Exception as mail_err:
            logger.warning(
                "parkpe_auth_register welcome_email_failed",
                extra_data={"user_id": user.pk, "error": str(mail_err)},
            )

        logger.info("parkpe_auth_register success", extra_data={"user_id": user.pk})
        return Response(
            {"message": "Registration successful.", "userId": str(user.pk), "requiresVerification": False},
            status=status.HTTP_201_CREATED,
        )


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
