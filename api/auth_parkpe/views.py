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

from portal.models import User, Profile
from portal.utils.logging_helper import get_logger
from portal.utils.phone_utils import safe_normalize_phone
from portal.services.otp_service import OTPService

logger = get_logger(__name__)


def _phone_lookup_candidates(normalized_phone: str):
    """Return list of phone strings to try when looking up Profile. DB may store 10-digit, 91..., or +91..."""
    candidates = [normalized_phone]
    if normalized_phone.startswith("+91"):
        candidates.append(normalized_phone[1:])  # 91XXXXXXXXXX
        if len(normalized_phone) == 13:  # +91 + 10 digits
            candidates.append(normalized_phone[3:])  # 10-digit only (XXXXXXXXXX)
    elif normalized_phone.startswith("91") and len(normalized_phone) == 12:
        candidates.append(normalized_phone[2:])  # 10-digit only
    return candidates


def _resolve_profile_by_phone(phone_raw: str):
    """Normalize phone and return Profile if found. Returns (profile, error_response) – one is None.
    Lookup tries: +91XXXXXXXXXX, 91XXXXXXXXXX, and 10-digit XXXXXXXX so DB-stored format doesn't matter."""
    normalized_phone, err = safe_normalize_phone(phone_raw)
    if err:
        return None, {"detail": "Invalid mobile number. Use 10-digit Indian mobile (e.g. 9876543210).", "status": 400}
    candidates = _phone_lookup_candidates(normalized_phone)
    profile = (
        Profile.objects.filter(phone__in=candidates).select_related("user").first()
    )
    return profile, None


def _redact_email(email: str) -> str:
    """Redact email for logging (e.g. a***@b.com)."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}" if len(local) > 1 else f"***@{domain}"


def _user_to_angular(user: User) -> dict:
    """Map Django User + Profile to Angular User shape."""
    profile = getattr(user, "profile", None)
    if profile:
        name = profile.full_name or f"{getattr(profile, 'first_name', '') or user.username}".strip() or user.username
        email = profile.email or user.email or ""
        phone = getattr(profile, "phone", "") or ""
    else:
        name = getattr(user, "first_name", "") or user.username
        email = user.email or ""
        phone = ""
    role = "admin" if getattr(user, "role_code", "") in ("admin", "super") else "user"
    return {
        "id": str(user.pk),
        "name": name or user.username,
        "email": email,
        "phone": phone or "",
        "role": role,
        "avatar": None,
        "emailVerified": getattr(profile, "email_verified", False) if profile else False,
        "phoneVerified": getattr(profile, "phone_verified", False) if profile else False,
        "createdAt": user.date_joined.isoformat() if user.date_joined else None,
        "updatedAt": None,
    }


@method_decorator(csrf_exempt, name="dispatch")
class AuthLoginView(APIView):
    """POST /api/auth/login – body: { email?, phone?, password, rememberMe? }. Login by email or phone + password."""
    authentication_classes = []  # No SessionAuthentication so DRF does not enforce CSRF
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

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
                "email_redacted": _redact_email(email) if email else None,
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
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = profile.user
        if not user.is_active:
            logger.warning("parkpe_auth_login account disabled", extra_data={"user_id": user.pk})
            return Response(
                {"detail": "Account is disabled."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not authenticate(request, username=user.username, password=password):
            logger.warning("parkpe_auth_login invalid credentials (auth failed)")
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        logger.info("parkpe_auth_login success", extra_data={"user_id": user.pk})
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
            "user": _user_to_angular(user),
            "expiresIn": expires_seconds,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthOTPRequestView(APIView):
    """POST /api/auth/otp/request – body: { phone }. Sends OTP via Kaleyra to registered mobile. Login only for existing users."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

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
        return Response({
            "message": "OTP sent to your mobile number.",
            "expires_in": otp_service.otp_expiry,
        })


@method_decorator(csrf_exempt, name="dispatch")
class AuthOTPVerifyView(APIView):
    """POST /api/auth/otp/verify – body: { phone, otp }. Verifies OTP and returns JWT (same shape as login)."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

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
        if not otp_service.verify_otp(profile.phone, otp_code):
            logger.warning("parkpe_auth_otp_verify failed", extra_data={"user_id": profile.user_id})
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
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        from rest_framework_simplejwt.settings import api_settings as jwt_settings
        access_lifetime = jwt_settings.ACCESS_TOKEN_LIFETIME
        expires_seconds = int(access_lifetime.total_seconds()) if hasattr(access_lifetime, "total_seconds") else 300
        return Response({
            "token": access,
            "refreshToken": refresh_str,
            "user": _user_to_angular(user),
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
        return Response(_user_to_angular(request.user))

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
        return Response(_user_to_angular(user))


@method_decorator(csrf_exempt, name="dispatch")
class AuthLogoutView(APIView):
    """POST /api/auth/logout – no-op for JWT (client discards token)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        logger.info("parkpe_auth_logout", extra_data={"user_id": getattr(request.user, "pk", None)})
        return Response({"success": True})


@method_decorator(csrf_exempt, name="dispatch")
class AuthRegisterView(APIView):
    """POST /api/auth/register – body: { name, email, phone, password, confirmPassword, acceptTerms }. Creates user + profile."""
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        data = request.data or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        phone = (data.get("phone") or "").strip()
        password = data.get("password") or ""
        confirm = data.get("confirmPassword") or ""
        accept_terms = data.get("acceptTerms") is True

        logger.info("parkpe_auth_register attempt", extra_data={"email_redacted": _redact_email(email)})

        if not all([name, email, password]):
            return Response(
                {"message": "Name, email and password are required.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if password != confirm:
            return Response(
                {"message": "Password and confirm password do not match.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(password) < 6:
            return Response(
                {"message": "Password must be at least 6 characters.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not accept_terms:
            logger.warning("parkpe_auth_register terms not accepted")
            return Response(
                {"message": "You must accept the terms.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Profile.objects.filter(email__iexact=email).exists():
            logger.warning("parkpe_auth_register email already exists")
            return Response(
                {"message": "An account with this email already exists.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if phone and Profile.objects.filter(phone=phone).exists():
            return Response(
                {"message": "An account with this phone already exists.", "userId": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from portal.models import Role
        try:
            role = Role.objects.get(code="customer")
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
        logger.info("parkpe_auth_forgot_password request", extra_data={"email_redacted": _redact_email(email)})
        if not email:
            logger.warning("parkpe_auth_forgot_password missing email")
            return Response(
                {"message": "Email is required.", "resetTokenSent": False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # TODO: integrate with portal forgot-password flow (send reset link)
        return Response({
            "message": "If an account exists with this email, you will receive a reset link.",
            "resetTokenSent": True,
        })
