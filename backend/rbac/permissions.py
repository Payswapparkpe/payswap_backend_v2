"""
DRF permission classes for Hub RBAC.
Super Admin bypasses all checks. Sub Admin must have required permission via Hub assignments.
"""
from rest_framework import permissions

from rbac.utils import get_user_hub_permissions, is_super_admin


class IsSuperAdminOrHasHubPermission(permissions.BasePermission):
    """
    Allow if request.user is Super Admin, or has the required Hub permission.
    View must set required_permission (str, e.g. 'rbac.view_department') or
    required_permissions (list of str; any one suffices).
    Optionally scopes permission check to request.hub_project_code / request.hub_department_code
    (set by HubContextMiddleware).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if is_super_admin(request.user):
            return True

        # Support permission_map[action] or required_permission / required_permissions
        permission_map = getattr(view, "permission_map", None)
        if permission_map and hasattr(view, "action"):
            raw = permission_map.get(view.action)
        else:
            raw = getattr(view, "required_permission", None)
        required_list = getattr(view, "required_permissions", None)
        if required_list is not None:
            perms_to_check = list(required_list)
        elif raw:
            perms_to_check = [raw] if isinstance(raw, str) else list(raw)
        else:
            return False

        project_code = getattr(request, "hub_project_code", None)
        department_code = getattr(request, "hub_department_code", None)
        user_perms = get_user_hub_permissions(
            request.user,
            project_code=project_code,
            department_code=department_code,
        )

        # Sentinel: Super Admin already returned True above; user_perms here is a set
        if user_perms is None:
            return True

        return any(p in user_perms for p in perms_to_check)
