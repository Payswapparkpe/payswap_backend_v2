"""
RC visibility: when to show vehicle_rc vs set rc_locked.
Compare profile name with RC owner; allow temporary unlock via VehicleRCUnlock.
"""
from django.utils import timezone

from portal.models import VehicleRCData, VehicleRCUnlock


def _normalize_name(s: str | None) -> str:
    if s is None:
        return ""
    return " ".join(str(s).strip().upper().split())


def rc_owner_matches_profile(user, raw_response: dict | None) -> bool:
    if not raw_response:
        return False
    rc_owner = raw_response.get("owner")
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    profile_name = getattr(profile, "full_name", None) or ""
    return _normalize_name(profile_name) == _normalize_name(rc_owner)


def has_valid_rc_unlock(user, vehicle) -> bool:
    return VehicleRCUnlock.objects.filter(
        user=user,
        vehicle=vehicle,
        expires_at__gt=timezone.now(),
    ).exists()


def get_vehicle_rc_display(vehicle, user) -> tuple[dict | None, bool]:
    """
    Return (vehicle_rc_payload, rc_locked).
    - If no RC data: (None, False).
    - If owner matches, paid for RC view, or valid unlock: (raw_response, False).
    - Else: (None, True).
    """
    rc = getattr(vehicle, "rc_data", None) or VehicleRCData.objects.filter(vehicle=vehicle).first()
    if not rc or not getattr(rc, "raw_response", None):
        return None, False
    raw = rc.raw_response
    if rc_owner_matches_profile(user, raw):
        return raw, False
    # Owner paid Rs 50 from voucher to view full RC
    if getattr(vehicle, "user_id", None) == getattr(user, "pk", None) and getattr(vehicle, "rc_view_paid_at", None):
        return raw, False
    if has_valid_rc_unlock(user, vehicle):
        return raw, False
    return None, True
