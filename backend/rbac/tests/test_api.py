"""
API tests for Hub RBAC endpoints.
Super Admin can CRUD; Sub Admin only with required permission.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from rbac.models import Department, Project, HubRole, UserHubAssignment

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def super_admin_user(db):
    user = User.objects.create_user(username="super1", password="test", role_code="super_admin")
    user.is_superuser = True
    user.is_staff = True
    user.save()
    return user


@pytest.fixture
def sub_admin_user(db):
    user = User.objects.create_user(username="sub1", password="test", role_code="employee")
    dept = Department.objects.create(code="finance", name="Finance")
    proj = Project.objects.create(code="parkpe", name="Parkpe")
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get(app_label="rbac", model="department")
    perm = Permission.objects.get(content_type=ct, codename="view_department")
    role = HubRole.objects.create(department=dept, project=proj, code="viewer", name="Viewer")
    role.permissions.add(perm)
    assignment = UserHubAssignment.objects.create(user=user, department=dept, project=proj)
    assignment.roles.add(role)
    return user


@pytest.mark.django_db
class TestHubAPIUnauthenticated:
    def test_departments_list_requires_auth(self, api_client):
        response = api_client.get("/api/hub/departments/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_projects_list_requires_auth(self, api_client):
        response = api_client.get("/api/hub/projects/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.django_db
class TestHubAPISuperAdmin:
    def test_super_admin_can_list_departments(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)
        Department.objects.create(code="finance", name="Finance")
        response = api_client.get("/api/hub/departments/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results", response.data)) >= 1

    def test_super_admin_can_create_department(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)
        response = api_client.post(
            "/api/hub/departments/",
            {"code": "support", "name": "Support"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["code"] == "support"

    def test_super_admin_can_create_project(self, api_client, super_admin_user):
        api_client.force_authenticate(user=super_admin_user)
        response = api_client.post(
            "/api/hub/projects/",
            {"code": "parkpe", "name": "Parkpe"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["code"] == "parkpe"


@pytest.mark.django_db
class TestHubAPISubAdmin:
    def test_sub_admin_with_view_permission_can_list_departments(self, api_client, sub_admin_user):
        api_client.force_authenticate(user=sub_admin_user)
        response = api_client.get("/api/hub/departments/")
        assert response.status_code == status.HTTP_200_OK

    def test_sub_admin_without_add_permission_cannot_create_department(self, api_client, sub_admin_user):
        api_client.force_authenticate(user=sub_admin_user)
        response = api_client.post(
            "/api/hub/departments/",
            {"code": "sales", "name": "Sales"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
