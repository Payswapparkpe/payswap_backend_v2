"""
Tests for Hub RBAC permission helpers and DRF permission class.
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from rbac.models import Department, Project, HubRole, UserHubAssignment
from rbac.utils import is_super_admin, get_user_hub_permissions

User = get_user_model()


@pytest.mark.django_db
class TestIsSuperAdmin:
    def test_anonymous_is_not_super_admin(self):
        from django.contrib.auth.models import AnonymousUser
        assert is_super_admin(AnonymousUser()) is False

    def test_regular_user_is_not_super_admin(self):
        user = User.objects.create_user(username="u1", password="test", role_code="customer")
        assert is_super_admin(user) is False

    def test_superuser_is_super_admin(self):
        user = User.objects.create_user(username="u2", password="test", role_code="employee")
        user.is_superuser = True
        user.save()
        assert is_super_admin(user) is True


@pytest.mark.django_db
class TestGetUserHubPermissions:
    def test_super_admin_returns_none_sentinel(self):
        user = User.objects.create_user(username="u3", password="test", role_code="employee")
        user.is_superuser = True
        user.save()
        perms = get_user_hub_permissions(user)
        assert perms is None

    def test_unauthenticated_returns_empty(self):
        from django.contrib.auth.models import AnonymousUser
        perms = get_user_hub_permissions(AnonymousUser())
        assert perms == set()

    def test_sub_admin_gets_union_of_role_permissions(self):
        user = User.objects.create_user(username="u4", password="test", role_code="employee")
        dept = Department.objects.create(code="finance", name="Finance")
        proj = Project.objects.create(code="parkpe", name="Parkpe")
        ct = ContentType.objects.get(app_label="rbac", model="department")
        p1 = Permission.objects.get(content_type=ct, codename="view_department")
        p2 = Permission.objects.get(content_type=ct, codename="add_department")
        role1 = HubRole.objects.create(department=dept, project=proj, code="r1", name="Role 1")
        role1.permissions.add(p1)
        role2 = HubRole.objects.create(department=dept, project=proj, code="r2", name="Role 2")
        role2.permissions.add(p2)
        assignment = UserHubAssignment.objects.create(user=user, department=dept, project=proj)
        assignment.roles.add(role1, role2)
        perms = get_user_hub_permissions(user)
        assert "rbac.view_department" in perms
        assert "rbac.add_department" in perms

    def test_filter_by_project_code(self):
        user = User.objects.create_user(username="u5", password="test", role_code="employee")
        dept = Department.objects.create(code="support", name="Support")
        proj1 = Project.objects.create(code="parkpe", name="Parkpe")
        proj2 = Project.objects.create(code="payswap", name="Payswap")
        ct = ContentType.objects.get(app_label="rbac", model="project")
        p_view = Permission.objects.get(content_type=ct, codename="view_project")
        role1 = HubRole.objects.create(department=dept, project=proj1, code="r1", name="R1")
        role1.permissions.add(p_view)
        role2 = HubRole.objects.create(department=dept, project=proj2, code="r2", name="R2")
        role2.permissions.add(p_view)
        a1 = UserHubAssignment.objects.create(user=user, department=dept, project=proj1)
        a1.roles.add(role1)
        a2 = UserHubAssignment.objects.create(user=user, department=dept, project=proj2)
        a2.roles.add(role2)
        perms_parkpe = get_user_hub_permissions(user, project_code="parkpe")
        perms_payswap = get_user_hub_permissions(user, project_code="payswap")
        assert "rbac.view_project" in perms_parkpe
        assert "rbac.view_project" in perms_payswap
        # Scoped to parkpe only
        perms = get_user_hub_permissions(user, project_code="parkpe")
        assert perms == perms_parkpe
