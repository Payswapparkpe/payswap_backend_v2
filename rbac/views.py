"""
ViewSets for Hub RBAC API.
Super Admin bypasses all; Sub Admin needs permission per action (permission_map).
"""
from rest_framework import viewsets, status
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
    }

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return UserHubAssignmentListSerializer
        return UserHubAssignmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
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
