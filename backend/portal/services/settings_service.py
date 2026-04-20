"""
Unified settings service shared by Hub and ParkPe surfaces.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from django.utils import timezone

from portal.models import DevicePushToken, PasskeyCredential, Profile, UserSettingsAuditLog

SUPPORTED_LANGUAGES = {"en", "hi"}
SUPPORTED_CURRENCIES = {"INR", "USD"}

DEFAULT_NOTIFICATION_PREFERENCES = {
    "push": True,
    "email": True,
    "sms": False,
    "in_app": True,
    "quiet_hours_enabled": False,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00",
    "critical_alert_override": True,
}


def _normalize_notification_preferences(value: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_NOTIFICATION_PREFERENCES)
    if isinstance(value, dict):
        merged.update(value)
    for key in ("push", "email", "sms", "in_app", "quiet_hours_enabled", "critical_alert_override"):
        merged[key] = bool(merged.get(key))
    for key in ("quiet_hours_start", "quiet_hours_end"):
        merged[key] = str(merged.get(key) or DEFAULT_NOTIFICATION_PREFERENCES[key])[:5]
    return merged


def get_settings_payload(user) -> dict[str, Any]:
    profile = getattr(user, "profile", None)
    settings_blob = (profile.settings if profile and isinstance(profile.settings, dict) else {}) or {}
    privacy = settings_blob.get("privacy", {}) if isinstance(settings_blob.get("privacy"), dict) else {}
    notification_prefs = _normalize_notification_preferences(
        profile.notification_preferences if profile else None
    )

    return {
        "preferences": {
            "language": (profile.language_preference if profile else "en") or "en",
            "timezone": (profile.timezone if profile else "Asia/Kolkata") or "Asia/Kolkata",
            "currency": (profile.currency_preference if profile else "INR") or "INR",
        },
        "notificationPreferences": notification_prefs,
        "privacy": {
            "marketingConsent": bool(privacy.get("marketingConsent", False)),
            "productTips": bool(privacy.get("productTips", True)),
            "securityAlerts": bool(privacy.get("securityAlerts", True)),
        },
    }


def update_user_settings(
    *,
    user,
    updates: dict[str, Any],
    actor_user=None,
    source: str = UserSettingsAuditLog.SOURCE_SYSTEM,
    request=None,
) -> dict[str, Any]:
    profile = getattr(user, "profile", None)
    if profile is None:
        raise ValueError("Profile not found.")

    changes: dict[str, Any] = {}
    preferences = updates.get("preferences", {}) if isinstance(updates.get("preferences"), dict) else {}
    notifications = updates.get("notificationPreferences")
    privacy = updates.get("privacy", {}) if isinstance(updates.get("privacy"), dict) else {}

    new_language = str(preferences.get("language", profile.language_preference) or profile.language_preference).lower()
    if new_language not in SUPPORTED_LANGUAGES:
        new_language = profile.language_preference or "en"
    if new_language != profile.language_preference:
        changes["language"] = {"from": profile.language_preference, "to": new_language}
        profile.language_preference = new_language

    new_timezone = str(preferences.get("timezone", profile.timezone) or profile.timezone).strip()[:50]
    if new_timezone and new_timezone != profile.timezone:
        changes["timezone"] = {"from": profile.timezone, "to": new_timezone}
        profile.timezone = new_timezone

    new_currency = str(preferences.get("currency", profile.currency_preference) or profile.currency_preference).upper()
    if new_currency not in SUPPORTED_CURRENCIES:
        new_currency = profile.currency_preference or "INR"
    if new_currency != profile.currency_preference:
        changes["currency"] = {"from": profile.currency_preference, "to": new_currency}
        profile.currency_preference = new_currency

    if isinstance(notifications, dict):
        prev_notification_prefs = _normalize_notification_preferences(profile.notification_preferences)
        next_notification_prefs = _normalize_notification_preferences(notifications)
        if prev_notification_prefs != next_notification_prefs:
            changes["notificationPreferences"] = {"from": prev_notification_prefs, "to": next_notification_prefs}
            profile.notification_preferences = next_notification_prefs

    current_settings = deepcopy(profile.settings) if isinstance(profile.settings, dict) else {}
    current_privacy = current_settings.get("privacy", {}) if isinstance(current_settings.get("privacy"), dict) else {}
    next_privacy = {
        "marketingConsent": bool(privacy.get("marketingConsent", current_privacy.get("marketingConsent", False))),
        "productTips": bool(privacy.get("productTips", current_privacy.get("productTips", True))),
        "securityAlerts": bool(privacy.get("securityAlerts", current_privacy.get("securityAlerts", True))),
    }
    if next_privacy != current_privacy:
        changes["privacy"] = {"from": current_privacy, "to": next_privacy}
        current_settings["privacy"] = next_privacy
        profile.settings = current_settings

    if changes:
        profile.last_updated_by = actor_user if actor_user and getattr(actor_user, "is_authenticated", False) else None
        profile.save(
            update_fields=[
                "language_preference",
                "timezone",
                "currency_preference",
                "notification_preferences",
                "settings",
                "last_updated_by",
                "updated_at",
            ]
        )
        UserSettingsAuditLog.objects.create(
            user=user,
            actor_user=actor_user if actor_user and getattr(actor_user, "is_authenticated", False) else None,
            source=source,
            action="settings_updated",
            change_summary=changes,
            ip_address=getattr(request, "META", {}).get("REMOTE_ADDR") if request else None,
            user_agent=(getattr(request, "META", {}).get("HTTP_USER_AGENT") or "")[:500] if request else "",
        )

    return get_settings_payload(user)


def get_security_overview(user) -> dict[str, Any]:
    profile = getattr(user, "profile", None)
    now = timezone.now()
    devices = list(
        DevicePushToken.objects.filter(user=user)
        .order_by("-last_seen_at", "-updated_at")[:20]
        .values("id", "device_platform", "app_platform", "is_active", "last_seen_at", "updated_at")
    )
    passkey_enabled = PasskeyCredential.objects.filter(user=user, is_active=True).exists()
    return {
        "mfa": {
            "enabled": bool(getattr(user, "mfa_enabled", False)),
            "configured": bool(getattr(user, "mfa_configured", False)),
            "method": getattr(user, "mfa_method", None),
        },
        "passkey": {"enabled": passkey_enabled},
        "pinLock": {
            "pinSet": bool(getattr(user, "pin_hash", None)),
            "pinSetAt": user.pin_set_at.isoformat() if getattr(user, "pin_set_at", None) else None,
            "pinLockedUntil": user.pin_locked_until.isoformat() if getattr(user, "pin_locked_until", None) else None,
            "fullAuthFresh": bool(getattr(user, "last_full_auth_at", None) and user.last_full_auth_at >= (now - timedelta(hours=24))),
        },
        "connect": {
            "blockedUntil": profile.connect_blocked_until.isoformat() if profile and profile.connect_blocked_until else None,
            "warningCount": int(profile.connect_warning_count or 0) if profile else 0,
        },
        "devices": devices,
    }
