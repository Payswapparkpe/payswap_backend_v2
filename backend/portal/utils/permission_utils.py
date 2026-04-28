"""
Permission checking utilities
"""
from typing import List
from django.contrib.auth.models import User
from portal.utils.staff_utils import is_super_admin
from rbac.utils import get_user_hub_permissions


def _split_permission(permission_codename: str, app_label: str = 'portal'):
    raw = (permission_codename or '').strip()
    if '.' in raw:
        parts = raw.split('.', 1)
        return parts[0], parts[1]
    return app_label, raw


def _user_has_custom_permission(user: User, perm_name: str) -> bool:
    """
    Check UserPermission table for an active direct-grant on this user.
    UserPermission stores per-user permission grants/revokes with audit trail.
    """
    try:
        from portal.models import UserPermission
        app_label, codename = perm_name.split(".", 1) if "." in perm_name else ("portal", perm_name)
        return UserPermission.objects.filter(
            user=user,
            permission__codename=codename,
            permission__content_type__app_label=app_label,
            is_active=True,
            revoked_at__isnull=True,
        ).exists()
    except Exception:
        return False


def user_has_permission(user: User, permission_codename: str, app_label: str = 'portal') -> bool:
    """
    Check if user has a specific permission via any of:
      1. Super Admin bypass
      2. Django group/user permission (role-based via setup_roles)
      3. UserPermission direct grant (per-user audit trail table)
      4. Hub RBAC assignment (via UserHubAssignment + HubRole)

    Args:
        user: User instance
        permission_codename: Permission codename (e.g. 'change_user' or 'portal.change_user')
        app_label: App label (default: 'portal')

    Returns:
        True if user has permission via any of the above paths
    """
    if not user or not user.is_authenticated:
        return False
    if is_super_admin(user):
        return True

    label, codename = _split_permission(permission_codename, app_label)
    if not codename:
        return False
    perm_name = f"{label}.{codename}"

    # Path 2: Django role-based group permissions
    if user.has_perm(perm_name):
        return True

    # Path 3: UserPermission direct grant
    if _user_has_custom_permission(user, perm_name):
        return True

    # Path 4: Hub RBAC assignment union (unscoped — any active assignment)
    hub_perms = get_user_hub_permissions(user)
    if hub_perms is None:
        return True
    return perm_name in hub_perms


def user_has_any_permission(user: User, permission_codenames: List[str], app_label: str = 'portal') -> bool:
    """
    Check if user has any of the specified permissions
    
    Args:
        user: User instance
        permission_codenames: List of permission codenames
        app_label: App label (default: 'portal')
    
    Returns:
        True if user has at least one permission
    """
    for codename in permission_codenames:
        if user_has_permission(user, codename, app_label):
            return True
    return False


def user_has_all_permissions(user: User, permission_codenames: List[str], app_label: str = 'portal') -> bool:
    """
    Check if user has all specified permissions
    
    Args:
        user: User instance
        permission_codenames: List of permission codenames
        app_label: App label (default: 'portal')
    
    Returns:
        True if user has all permissions
    """
    for codename in permission_codenames:
        if not user_has_permission(user, codename, app_label):
            return False
    return True


def user_has_hub_permission(user: User, permission_codename: str, app_label: str = 'portal', project_code=None, department_code=None) -> bool:
    """
    Check permission through Hub RBAC only (plus super admin bypass).
    """
    if not user or not user.is_authenticated:
        return False
    if is_super_admin(user):
        return True
    label, codename = _split_permission(permission_codename, app_label)
    if not codename:
        return False
    perm_name = f"{label}.{codename}"
    hub_perms = get_user_hub_permissions(
        user,
        project_code=project_code,
        department_code=department_code,
    )
    if hub_perms is None:
        return True
    return perm_name in hub_perms


def get_user_role(user: User) -> str:
    """
    Get user's role code
    
    Args:
        user: User instance
    
    Returns:
        Role code string
    """
    if hasattr(user, 'role'):
        return user.role.code if hasattr(user.role, 'code') else str(user.role)
    return 'unknown'
