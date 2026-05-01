"""
ParkPe API permission classes — JWT role_code claims + staff bypass for ops tools.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission


def get_effective_role_code(request) -> str:
    token = getattr(request, "auth", None)
    if token is not None and hasattr(token, "get"):
        rc = token.get("role_code")
        if rc:
            return str(rc).strip().lower()
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return str(getattr(user, "role_code", "") or "").strip().lower()
    return ""


def _staff_bypass(request) -> bool:
    u = getattr(request, "user", None)
    return bool(u and u.is_authenticated and getattr(u, "is_staff", False))


class IsCustomerPortal(BasePermission):
    """
    Allows consumers (non-fleet, non-parking roles). Staff bypass.
    Blocks fleet_* and parking_* from consumer-only ParkPe surfaces.
    """

    message = "This endpoint is only available to consumer accounts."

    def has_permission(self, request, view):
        if _staff_bypass(request):
            return True
        rc = get_effective_role_code(request)
        if not rc:
            return True
        return not (rc.startswith("fleet_") or rc.startswith("parking_"))


class IsParkingRole(BasePermission):
    """Requires parking_* role_code or JWT parking_location_ids (operator mapping). Staff bypass."""

    message = "Parking operator access required."

    def has_permission(self, request, view):
        if _staff_bypass(request):
            return True
        rc = get_effective_role_code(request)
        if rc.startswith("parking_"):
            return True
        token = getattr(request, "auth", None)
        if token is not None and hasattr(token, "get"):
            pids = token.get("parking_location_ids")
            if pids:
                return True
        return False


class IsFleetRole(BasePermission):
    """Requires fleet_* role_code. Staff bypass."""

    message = "Fleet access required."

    def has_permission(self, request, view):
        if _staff_bypass(request):
            return True
        rc = get_effective_role_code(request)
        return bool(rc.startswith("fleet_"))
