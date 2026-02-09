"""
DRF permission classes for API Management:
- APIRegistryStatusPermission: block when API status is OFF
- APIRegistryAccessPermission: check role/permissions for user or API key
"""
from rest_framework import permissions

from .models import APIRegistry
from .registry import get_registry_for_request


class APIRegistryStatusPermission(permissions.BasePermission):
    """
    If the request matches an APIRegistry entry and status is OFF, deny access.
    If no registry entry exists, allow (backward compatible: unregistered APIs still work).
    """

    message = "This API is currently disabled."

    def has_permission(self, request, view):
        registry = get_registry_for_request(request)
        if registry is None:
            return True
        return registry.status == APIRegistry.STATUS_ON


class APIRegistryAccessPermission(permissions.BasePermission):
    """
    Check access based on APIRegistry allowed_role_codes, min_role_hierarchy,
    and required_permissions. For API-key principals, check APIKey.permissions.
    """

    message = "You do not have permission to access this API."

    def has_permission(self, request, view):
        registry = get_registry_for_request(request)
        if registry is None:
            return True

        # API key (partner) flow
        api_key_obj = getattr(request, "api_key_obj", None) or getattr(
            request, "api_key", None
        )
        if api_key_obj is not None:
            return self._check_api_key_access(registry, api_key_obj)

        # User flow (authenticated or anon)
        if not request.user or not request.user.is_authenticated:
            # Anonymous: allow only if allowed_role_codes includes something like 'anon'
            return "anon" in (registry.allowed_role_codes or [])

        return self._check_user_access(registry, request.user)

    def _check_api_key_access(self, registry, api_key_obj):
        if not api_key_obj.is_active():
            return False
        # Optional: registry could store required service permissions for partners
        # For now, if registry exists and API key is active, allow (v2 partners)
        return True

    def _check_user_access(self, registry, user):
        role_code = getattr(user, "role_code", None)
        if not role_code:
            return False

        allowed = registry.allowed_role_codes or []
        if allowed and role_code.lower() not in [r.lower() for r in allowed]:
            # Check min_role_hierarchy as fallback
            if registry.min_role_hierarchy is not None and hasattr(user, "role") and user.role:
                if user.role.hierarchy_level >= registry.min_role_hierarchy:
                    return self._check_required_permissions(registry, user)
                return False
            return False

        return self._check_required_permissions(registry, user)

    def _check_required_permissions(self, registry, user):
        perms = registry.required_permissions or []
        if not perms:
            return True
        return user.has_perms(perms)
