"""
Session lock / PIN unlock helpers (identity from signed cookie).
Used by middleware and views; OTP/2FA is primary auth, PIN is secondary re-unlock only.
"""
import json
from django.core.signing import Signer, BadSignature
from django.utils import timezone

from portal.models import User

LOCK_IDENTITY_COOKIE_NAME = 'lock_identity'
PIN_UNLOCK_WINDOW_SECONDS = 24 * 3600  # 24 hours from last_full_auth_at


def get_user_from_lock_cookie(request):
    """
    Return User if valid lock_identity cookie present, else None.
    Does not check PIN/lock state or last_full_auth_at window.
    """
    raw = request.COOKIES.get(LOCK_IDENTITY_COOKIE_NAME)
    if not raw:
        return None
    try:
        signer = Signer()
        payload = json.loads(signer.unsign(raw))
        user_id = payload.get('user_id')
        if not user_id:
            return None
        return User.objects.filter(pk=user_id).first()
    except (BadSignature, TypeError, ValueError, json.JSONDecodeError):
        return None


def can_offer_pin_unlock(user):
    """True if user has PIN set, is not locked, and last_full_auth_at is within window."""
    if not user or not user.pin_hash:
        return False
    now = timezone.now()
    if user.pin_locked_until and user.pin_locked_until > now:
        return False
    if not user.last_full_auth_at:
        return False
    window_end = user.last_full_auth_at + timezone.timedelta(seconds=PIN_UNLOCK_WINDOW_SECONDS)
    return now <= window_end
