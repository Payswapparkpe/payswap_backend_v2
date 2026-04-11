"""
Tests for Hub RBAC models.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from rbac.models import Department, Project, HubRole, UserHubAssignment

User = get_user_model()


@pytest.mark.django_db
class TestDepartmentModel:
    def test_create_department(self):
        dept = Department.objects.create(code="finance", name="Finance")
        assert dept.code == "finance"
        assert dept.name == "Finance"
        assert dept.is_active is True

    def test_department_unique_code(self):
        Department.objects.create(code="support", name="Support")
        with pytest.raises(Exception):  # IntegrityError
            Department.objects.create(code="support", name="Support 2")


@pytest.mark.django_db
class TestProjectModel:
    def test_create_project(self):
        proj = Project.objects.create(code="parkpe", name="Parkpe")
        assert proj.code == "parkpe"
        assert proj.name == "Parkpe"
        assert proj.is_active is True


@pytest.mark.django_db
class TestHubRoleModel:
    def test_create_hub_role(self):
        dept = Department.objects.create(code="finance", name="Finance")
        proj = Project.objects.create(code="parkpe", name="Parkpe")
        role = HubRole.objects.create(
            department=dept,
            project=proj,
            code="finance_manager",
            name="Finance Manager",
        )
        assert role.department == dept
        assert role.project == proj
        assert role.code == "finance_manager"

    def test_hub_role_unique_per_dept_project(self):
        dept = Department.objects.create(code="ops", name="Operations")
        proj = Project.objects.create(code="payswap", name="Payswap")
        HubRole.objects.create(department=dept, project=proj, code="viewer", name="Viewer")
        with pytest.raises(Exception):
            HubRole.objects.create(department=dept, project=proj, code="viewer", name="Viewer 2")


@pytest.mark.django_db
class TestUserHubAssignmentModel:
    def test_create_assignment(self):
        user = User.objects.create_user(username="u001", password="test", role_code="employee")
        dept = Department.objects.create(code="support", name="Support")
        proj = Project.objects.create(code="parkpe", name="Parkpe")
        role = HubRole.objects.create(
            department=dept,
            project=proj,
            code="support_agent",
            name="Support Agent",
        )
        assignment = UserHubAssignment.objects.create(
            user=user,
            department=dept,
            project=proj,
            designation="Executive",
        )
        assignment.roles.add(role)
        assert assignment.user == user
        assert assignment.department == dept
        assert assignment.project == proj
        assert list(assignment.roles.all()) == [role]

    def test_assignment_unique_user_dept_project(self):
        user = User.objects.create_user(username="u002", password="test", role_code="employee")
        dept = Department.objects.create(code="sales", name="Sales")
        proj = Project.objects.create(code="payswap", name="Payswap")
        UserHubAssignment.objects.create(user=user, department=dept, project=proj)
        with pytest.raises(Exception):
            UserHubAssignment.objects.create(user=user, department=dept, project=proj)
