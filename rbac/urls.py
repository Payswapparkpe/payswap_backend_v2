"""
Hub RBAC API URLs.
Mounted at /api/hub/ (JWT or session auth; Super Admin or Hub permission required).
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from rbac.views import (
    DepartmentViewSet,
    ProjectViewSet,
    HubRoleViewSet,
    UserHubAssignmentViewSet,
)

router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="hub-department")
router.register(r"projects", ProjectViewSet, basename="hub-project")
router.register(r"hub-roles", HubRoleViewSet, basename="hub-role")
router.register(r"assignments", UserHubAssignmentViewSet, basename="hub-assignment")

urlpatterns = [
    path("", include(router.urls)),
]
