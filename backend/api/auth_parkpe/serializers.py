"""
Shared serializers for Parkpe auth and Connect. Single source for user → Angular shape.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from portal.models import User

from portal.services.billing_party_service import profile_billing_address_complete


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
    role_code = str(getattr(user, "role_code", "") or "").strip().lower()
    if role_code in ("super_admin", "admin"):
        role = "admin"
    elif role_code.startswith("fleet_"):
        role = "fleet"
    else:
        role = "user"
    notification_prefs = {}
    settings_blob = {}
    if profile:
        notification_prefs = profile.notification_preferences if isinstance(profile.notification_preferences, dict) else {}
        settings_blob = profile.settings if isinstance(profile.settings, dict) else {}
    billing_complete = profile_billing_address_complete(profile) if profile else False
    return {
        "id": str(user.pk),
        "name": name or user.username,
        "email": email,
        "phone": phone or "",
        "role": role,
        "roleCode": role_code,
        "avatar": None,
        "emailVerified": getattr(profile, "email_verified", False) if profile else False,
        "phoneVerified": getattr(profile, "phone_verified", False) if profile else False,
        "createdAt": user.date_joined.isoformat() if user.date_joined else None,
        "updatedAt": None,
        "languagePreference": getattr(profile, "language_preference", "en") if profile else "en",
        "timezone": getattr(profile, "timezone", "Asia/Kolkata") if profile else "Asia/Kolkata",
        "currencyPreference": getattr(profile, "currency_preference", "INR") if profile else "INR",
        "notificationPreferences": notification_prefs,
        "settings": settings_blob,
        "addressLine1": (getattr(profile, "address_line_1", None) or "").strip() if profile else "",
        "addressLine2": (getattr(profile, "address_line_2", None) or "").strip() if profile else "",
        "city": (getattr(profile, "city", None) or "").strip() if profile else "",
        "state": (getattr(profile, "state", None) or "").strip() if profile else "",
        "pincode": (getattr(profile, "pincode", None) or "").strip() if profile else "",
        "countryOfResidence": (getattr(profile, "country_of_residence", None) or "India").strip() if profile else "India",
        "gstNumber": (getattr(profile, "gst_number", None) or "").strip() if profile else "",
        "billingAddressComplete": billing_complete,
    }
