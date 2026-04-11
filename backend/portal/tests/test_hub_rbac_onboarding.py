import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from portal.models import Role
from portal.utils.permission_utils import user_has_permission
from rbac.models import Department, Project, HubRole, UserHubAssignment

User = get_user_model()


def _ensure_role(code, name):
    Role.objects.get_or_create(
        code=code,
        defaults={"name": name},
    )


@pytest.mark.django_db
def test_user_has_permission_resolves_full_permission_name_from_hub_assignment():
    _ensure_role("employee", "Employee")
    user = User.objects.create_user(username="rbac-u1", password="testpass123", role_code="employee")
    dept = Department.objects.create(code="finance", name="Finance")
    project = Project.objects.create(code="payswap", name="Payswap")
    perm = Permission.objects.get(codename="change_user")
    role = HubRole.objects.create(
        department=dept,
        project=project,
        code="ops_manager",
        name="Ops Manager",
        is_active=True,
    )
    role.permissions.add(perm)
    assignment = UserHubAssignment.objects.create(user=user, department=dept, project=project, is_active=True)
    assignment.roles.add(role)

    assert user_has_permission(user, "portal.change_user") is True


@pytest.mark.django_db
def test_user_create_redirects_to_hub_assignment_flow():
    client = Client()
    _ensure_role("super_admin", "Super Admin")
    _ensure_role("employee", "Employee")
    super_admin = User.objects.create_user(
        username="super-onboard",
        password="testpass123",
        role_code="super_admin",
        is_superuser=True,
        is_staff=True,
        mfa_configured=True,
    )
    client.force_login(super_admin)

    response = client.post(
        reverse("user_create"),
        data={
            "first_name": "Rbac",
            "email": "rbac-onboard@example.com",
            "phone": "+919876543210",
            "username": "rbacemployee",
            "role_code": "employee",
            "password1": "testpass123",
            "password2": "testpass123",
        },
    )

    created_user = User.objects.exclude(pk=super_admin.pk).latest("pk")
    assert response.status_code == 302
    assert response.url == f"{reverse('hub_rbac_assignment_create')}?user_id={created_user.pk}"


@pytest.mark.django_db
def test_assignment_update_rejects_role_from_other_department_or_project():
    client = Client()
    _ensure_role("super_admin", "Super Admin")
    _ensure_role("employee", "Employee")
    super_admin = User.objects.create_user(
        username="supassign",
        password="testpass123",
        role_code="super_admin",
        is_superuser=True,
        is_staff=True,
        mfa_configured=True,
    )
    assignee = User.objects.create_user(username="rbacu2", password="testpass123", role_code="employee")
    client.force_login(super_admin)

    dept_a = Department.objects.create(code="support", name="Support")
    dept_b = Department.objects.create(code="ops", name="Operations")
    project_a = Project.objects.create(code="parkpe", name="ParkPe")
    project_b = Project.objects.create(code="payswap", name="Payswap")

    valid_role = HubRole.objects.create(department=dept_a, project=project_a, code="agent", name="Agent", is_active=True)
    invalid_role = HubRole.objects.create(department=dept_b, project=project_b, code="head", name="Head", is_active=True)

    assignment = UserHubAssignment.objects.create(
        user=assignee,
        department=dept_a,
        project=project_a,
        is_active=True,
    )
    assignment.roles.add(valid_role)

    response = client.post(
        reverse("hub_rbac_assignment_edit", kwargs={"pk": assignment.pk}),
        data={
            "user": assignee.pk,
            "department": dept_a.pk,
            "project": project_a.pk,
            "designation": "Executive",
            "is_active": "on",
            "roles": [str(invalid_role.pk)],
        },
    )

    assignment.refresh_from_db()
    role_ids = set(assignment.roles.values_list("pk", flat=True))
    assert response.status_code == 200
    assert invalid_role.pk not in role_ids
