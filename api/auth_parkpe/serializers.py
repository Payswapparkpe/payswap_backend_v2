"""
Shared serializers for Parkpe auth and Connect. Single source for user → Angular shape.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from portal.models import User


def user_to_angular(user: "User") -> dict:
    """Map Django User + Profile to Angular User shape (login, profile, scanner verify)."""
    profile = getattr(user, "profile", None)
    if profile:
        name = profile.full_name or f"{getattr(profile, 'first_name', '') or user.username}".strip() or user.username
        email = profile.email or user.email or ""
        phone = getattr(profile, "phone", "") or ""
    else:
        name = getattr(user, "first_name", "") or user.username
        email = user.email or ""
        phone = ""
    role = "admin" if getattr(user, "role_code", "") in ("super_admin", "admin") else "user"
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
