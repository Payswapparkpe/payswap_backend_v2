"""
Hub RBAC permission helpers.
Super Admin bypass: reuse portal's definition. Sub Admin permissions from UserHubAssignment + HubRole.
"""
from django.contrib.auth import get_user_model

# Reuse portal's Super Admin definition (is_superuser or role_code super_admin)
from portal.utils.staff_utils import is_super_admin as _portal_is_super_admin


def is_super_admin(user):
    """
    True if user is Super Admin (bypasses all Hub RBAC checks).
    Delegates to portal.utils.staff_utils.is_super_admin.
    """
    return _portal_is_super_admin(user)


def get_user_hub_permissions(user, project_code=None, department_code=None):
    """
    Return set of permission strings (e.g. 'rbac.view_department') the user has via Hub assignments.
    Super Admin: returns None as sentinel meaning "all permissions" (caller treats None as allow-all).
    Otherwise: active UserHubAssignment for user, optionally filtered by project_code/department_code,
    then union of all HubRole.permissions for assigned roles.
    """
    User = get_user_model()
    if not user or not isinstance(user, User) or not user.is_authenticated:
        return set()

    if is_super_admin(user):
        return None  # Sentinel: caller should treat as "has all permissions"

    from rbac.models import UserHubAssignment

    qs = UserHubAssignment.objects.filter(
        user=user,
        is_active=True,
    ).prefetch_related("roles__permissions", "department", "project")

    if project_code:
        qs = qs.filter(project__code=project_code)
    if department_code:
        qs = qs.filter(department__code=department_code)

    perms = set()
    for assignment in qs:
        for role in assignment.roles.filter(is_active=True):
            for perm in role.permissions.all():
                # Use natural key: content_type.app_label.codename (Django's has_perm format)
                perms.add(f"{perm.content_type.app_label}.{perm.codename}")

    return perms
