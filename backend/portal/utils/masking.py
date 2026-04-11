"""
Centralized masking for logs and responses. Never log PII (full phone, email, OTP).
"""
from portal.utils.phone_utils import mask_phone_number


def redact_email(email: str) -> str:
    """Redact email for logging (e.g. a***@b.com)."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}" if len(local) > 1 else f"***@{domain}"


def mask_email_for_log(email: str) -> str:
    """Alias for redact_email (same behavior)."""
    return redact_email(email)


def mask_phone_for_log(phone: str) -> str:
    """Mask phone for logs (e.g. ******3210). Safe for logging."""
    if not phone:
        return "****"
    return mask_phone_number(phone, show_last_digits=4)
