"""
Enterprise RBAC models for Payswap Hub.
Department, Project, HubRole (department+project scoped), UserHubAssignment (Sub Admin).
Uses Django's built-in Permission model for role permissions.
"""
from django.conf import settings
from django.db import models


class Department(models.Model):
    """Organizational department (e.g. Finance, Support, Operations, Sales)."""

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rbac_department"
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Project(models.Model):
    """Project / product (e.g. Parkpe, Payswap)."""

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rbac_project"
        verbose_name = "Project"
        verbose_name_plural = "Projects"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class HubRole(models.Model):
    """
    Role scoped to a Department and Project.
    Permissions are Django's built-in Permission (content_type + codename).
    """

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="hub_roles",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="hub_roles",
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=80, db_index=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    permissions = models.ManyToManyField(
        "auth.Permission",
        blank=True,
        related_name="hub_roles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rbac_hubrole"
        verbose_name = "Hub Role"
        verbose_name_plural = "Hub Roles"
        ordering = ["department", "project", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "project", "code"],
                name="rbac_hubrole_dept_proj_code_unique",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code}) [{self.department.code}/{self.project.code}]"


class UserHubAssignment(models.Model):
    """
    Sub Admin assignment: user + department + project + roles + designation.
    One record per (user, department, project); multiple roles per assignment.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hub_assignments",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="user_assignments",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="user_assignments",
    )
    designation = models.CharField(
        max_length=100,
        blank=True,
        help_text="E.g. Manager, Executive, Head",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Optional: auto-deactivate after this datetime. Leave blank for permanent access.",
    )
    roles = models.ManyToManyField(
        HubRole,
        blank=True,
        related_name="user_assignments",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_hub_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rbac_userhubassignment"
        verbose_name = "User Hub Assignment"
        verbose_name_plural = "User Hub Assignments"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "department", "project"],
                name="rbac_assignment_user_dept_proj_unique",
            )
        ]

    def __str__(self):
        return f"{self.user} | {self.department.code}/{self.project.code} | {self.designation or '—'}"
