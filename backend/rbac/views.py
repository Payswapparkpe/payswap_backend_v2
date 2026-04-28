"""
ViewSets for Hub RBAC API.
Super Admin bypasses all checks and sees all rows.
Sub Admin: permission checked per action via permission_map;
  querysets are scoped to only the departments/projects the user is assigned to,
  preventing IDOR exposure of other tenants' data.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rbac.models import Department, Project, HubRole, UserHubAssignment
from rbac.serializers import (
    DepartmentSerializer,
    ProjectSerializer,
    HubRoleSerializer,
    UserHubAssignmentSerializer,
    UserHubAssignmentListSerializer,
)
from rbac.permissions import IsSuperAdminOrHasHubPermission
from rbac.utils import is_super_admin, get_user_hub_permissions


def _user_allowed_dept_ids(user) -> list:
    """Return list of Department PKs the user is actively assigned to, or None for Super Admin."""
    if is_super_admin(user):
        return None
    return list(
        UserHubAssignment.objects.filter(user=user, is_active=True)
        .values_list("department_id", flat=True)
        .distinct()
    )


def _user_allowed_project_ids(user) -> list:
    """Return list of Project PKs the user is actively assigned to, or None for Super Admin."""
    if is_super_admin(user):
        return None
    return list(
        UserHubAssignment.objects.filter(user=user, is_active=True)
        .values_list("project_id", flat=True)
        .distinct()
    )


class HubPermissionMixin:
    """Mixin to require Hub permission per action via permission_map."""

    permission_classes = [IsAuthenticated, IsSuperAdminOrHasHubPermission]


class DepartmentViewSet(HubPermissionMixin, viewsets.ModelViewSet):
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    permission_map = {
        "list": "rbac.view_department",
        "retrieve": "rbac.view_department",
        "create": "rbac.add_department",
        "update": "rbac.change_department",
        "partial_update": "rbac.change_department",
        "destroy": "rbac.delete_department",
    }

    def get_queryset(self):
        qs = super().get_queryset()
        allowed = _user_allowed_dept_ids(self.request.user)
        if allowed is not None:
            qs = qs.filter(pk__in=allowed)
        if self.request.query_params.get("is_active") is not None:
            qs = qs.filter(is_active=self.request.query_params.get("is_active").lower() == "true")
        return qs


class ProjectViewSet(HubPermissionMixin, viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by("name")
    serializer_class = ProjectSerializer
    permission_map = {
        "list": "rbac.view_project",
        "retrieve": "rbac.view_project",
        "create": "rbac.add_project",
        "update": "rbac.change_project",
        "partial_update": "rbac.change_project",
        "destroy": "rbac.delete_project",
    }

    def get_queryset(self):
        qs = super().get_queryset()
        allowed = _user_allowed_project_ids(self.request.user)
        if allowed is not None:
            qs = qs.filter(pk__in=allowed)
        if self.request.query_params.get("is_active") is not None:
            qs = qs.filter(is_active=self.request.query_params.get("is_active").lower() == "true")
        return qs


class HubRoleViewSet(HubPermissionMixin, viewsets.ModelViewSet):
    queryset = HubRole.objects.all().select_related("department", "project").prefetch_related("permissions").order_by("department", "project", "name")
    serializer_class = HubRoleSerializer
    permission_map = {
        "list": "rbac.view_hubrole",
        "retrieve": "rbac.view_hubrole",
        "create": "rbac.add_hubrole",
        "update": "rbac.change_hubrole",
        "partial_update": "rbac.change_hubrole",
        "destroy": "rbac.delete_hubrole",
    }

    def get_queryset(self):
        qs = super().get_queryset()
        allowed_depts = _user_allowed_dept_ids(self.request.user)
        allowed_projs = _user_allowed_project_ids(self.request.user)
        if allowed_depts is not None:
            qs = qs.filter(department_id__in=allowed_depts)
        if allowed_projs is not None:
            qs = qs.filter(project_id__in=allowed_projs)
        dept = self.request.query_params.get("department")
        proj = self.request.query_params.get("project")
        if dept:
            qs = qs.filter(department_id=dept)
        if proj:
            qs = qs.filter(project_id=proj)
        if self.request.query_params.get("is_active") is not None:
            qs = qs.filter(is_active=self.request.query_params.get("is_active").lower() == "true")
        return qs


class UserHubAssignmentViewSet(HubPermissionMixin, viewsets.ModelViewSet):
    queryset = (
        UserHubAssignment.objects.all()
        .select_related("user", "department", "project", "created_by")
        .prefetch_related("roles")
        .order_by("-created_at")
    )
    permission_map = {
        "list": "rbac.view_userhubassignment",
        "retrieve": "rbac.view_userhubassignment",
        "create": "rbac.add_userhubassignment",
        "update": "rbac.change_userhubassignment",
        "partial_update": "rbac.change_userhubassignment",
        "destroy": "rbac.delete_userhubassignment",
        "my_permissions": None,
    }

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return UserHubAssignmentListSerializer
        return UserHubAssignmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        allowed_depts = _user_allowed_dept_ids(self.request.user)
        allowed_projs = _user_allowed_project_ids(self.request.user)
        if allowed_depts is not None:
            qs = qs.filter(department_id__in=allowed_depts)
        if allowed_projs is not None:
            qs = qs.filter(project_id__in=allowed_projs)
        user_id = self.request.query_params.get("user")
        dept = self.request.query_params.get("department")
        proj = self.request.query_params.get("project")
        if user_id:
            qs = qs.filter(user_id=user_id)
        if dept:
            qs = qs.filter(department_id=dept)
        if proj:
            qs = qs.filter(project_id=proj)
        if self.request.query_params.get("is_active") is not None:
            qs = qs.filter(is_active=self.request.query_params.get("is_active").lower() == "true")
        return qs

    @action(detail=False, methods=["get"], url_path="my-permissions", permission_classes=[IsAuthenticated])
    def my_permissions(self, request):
        """
        GET /api/hub/assignments/my-permissions/
        Returns the requesting user's active Hub assignments and effective permission set.
        Available to any authenticated user (not just Super Admin).
        """
        user = request.user
        assignments = (
            UserHubAssignment.objects.filter(user=user, is_active=True)
            .select_related("department", "project")
            .prefetch_related("roles__permissions")
            .order_by("department__name", "project__name")
        )
        perm_set = get_user_hub_permissions(user)
        is_super = perm_set is None
        assignment_data = []
        for a in assignments:
            assignment_data.append({
                "id": a.id,
                "department": {"id": a.department_id, "code": a.department.code, "name": a.department.name},
                "project": {"id": a.project_id, "code": a.project.code, "name": a.project.name},
                "designation": a.designation,
                "roles": [{"id": r.id, "code": r.code, "name": r.name} for r in a.roles.filter(is_active=True)],
            })
        return Response({
            "is_super_admin": is_super,
            "assignments": assignment_data,
            "permissions": sorted(perm_set) if perm_set is not None else ["*"],
            "permission_count": len(perm_set) if perm_set is not None else None,
        })
