"""
Staff / super-admin permission helpers.
Used by business_overview, api/internal run-job.
"""
# noqa: D100


def _is_super_admin_allowed(user):
    """Staff or role super_admin, admin, super (portal admin-level access)."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "is_staff", False) or getattr(user, "role_code", "").lower() in (
        "super_admin",
        "admin",
    )


def is_super_admin(user):
    """Strictest check: only super_admin role or is_superuser (for API/audit e.g. run-job)."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "is_superuser", False) or getattr(user, "role_code", "").lower() == "super_admin"
