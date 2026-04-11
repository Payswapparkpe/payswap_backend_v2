"""
Django admin for Hub RBAC.
Super Admin can manage departments, projects, roles, and assignments from admin as fallback.
"""
from django.contrib import admin

from rbac.models import Department, Project, HubRole, UserHubAssignment


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("name",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("name",)


@admin.register(HubRole)
class HubRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "department", "project", "is_active", "created_at")
    list_filter = ("is_active", "department", "project")
    search_fields = ("name", "code")
    filter_horizontal = ("permissions",)
    ordering = ("department", "project", "name")


@admin.register(UserHubAssignment)
class UserHubAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "project", "designation", "is_active", "created_at", "created_by")
    list_filter = ("is_active", "department", "project")
    search_fields = ("user__username", "designation")
    filter_horizontal = ("roles",)
    raw_id_fields = ("user", "created_by")
    ordering = ("-created_at",)
