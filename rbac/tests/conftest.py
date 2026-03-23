"""
Pytest fixtures for Hub RBAC tests.
Ensures portal Role records exist so User.create_user(role_code=...) works.
"""
import pytest
from portal.models import Role


@pytest.fixture(autouse=True)
def _ensure_roles(db):
    """Ensure portal Role records exist for role_codes used in rbac tests."""
    for code, name, category, level in [
        ("employee", "Employee", "b2b", 5),
        ("customer", "Customer", "b2c", 1),
        ("super_admin", "Super Admin", "b2b", 10),
    ]:
        Role.objects.get_or_create(
            code=code,
            defaults={"name": name, "category": category, "hierarchy_level": level, "mfa_required": False},
        )
