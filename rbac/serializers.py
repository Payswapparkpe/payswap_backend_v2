"""
Serializers for Hub RBAC API.
"""
import re
from django.contrib.auth.models import Permission
from rest_framework import serializers

from rbac.models import Department, Project, HubRole, UserHubAssignment


def _validate_slug_code(value, field_name="code"):
    """Validate slug-style code: lowercase alphanumeric and underscores."""
    if not value or not value.strip():
        raise serializers.ValidationError({field_name: "This field may not be blank."})
    if not re.match(r"^[a-z0-9_]+$", value.lower()):
        raise serializers.ValidationError(
            {field_name: "Use only lowercase letters, numbers, and underscores."}
        )
    return value.strip().lower()


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "code", "name", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_code(self, value):
        return _validate_slug_code(value, "code")


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ("id", "code", "name", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_code(self, value):
        return _validate_slug_code(value, "code")


class HubRoleSerializer(serializers.ModelSerializer):
    """Permissions as list of permission IDs (Django auth.Permission pk)."""

    permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = HubRole
        fields = (
            "id",
            "department",
            "project",
            "name",
            "code",
            "description",
            "is_active",
            "permissions",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_code(self, value):
        return _validate_slug_code(value, "code")

    def validate(self, attrs):
        department = attrs.get("department") or (self.instance.department if self.instance else None)
        project = attrs.get("project") or (self.instance.project if self.instance else None)
        code = attrs.get("code") or (self.instance.code if self.instance else None)
        if department and project and code:
            qs = HubRole.objects.filter(department=department, project=project, code=code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"code": "A role with this code already exists for this department and project."}
                )
        return attrs


class UserHubAssignmentSerializer(serializers.ModelSerializer):
    """Create/update Sub Admin assignment. Roles as list of HubRole IDs."""

    roles = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=HubRole.objects.filter(is_active=True),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = UserHubAssignment
        fields = (
            "id",
            "user",
            "department",
            "project",
            "designation",
            "is_active",
            "roles",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def validate_roles(self, value):
        if not value and not self.partial:
            raise serializers.ValidationError("At least one role is required when creating an assignment.")
        return value

    def validate(self, attrs):
        department = attrs.get("department") or (self.instance.department if self.instance else None)
        project = attrs.get("project") or (self.instance.project if self.instance else None)
        roles = attrs.get("roles")
        if roles is None and self.instance:
            roles = list(self.instance.roles.all())
        if department and project and roles is not None:
            for role in roles:
                if role.department_id != department.id or role.project_id != project.id:
                    raise serializers.ValidationError(
                        {"roles": f"Role '{role.code}' does not belong to the selected department and project."}
                    )
        return attrs

    def create(self, validated_data):
        roles = validated_data.pop("roles", [])
        request = self.context.get("request")
        if request and request.user:
            validated_data["created_by"] = request.user
        obj = super().create(validated_data)
        if roles:
            obj.roles.set(roles)
        return obj

    def update(self, instance, validated_data):
        roles = validated_data.pop("roles", None)
        obj = super().update(instance, validated_data)
        if roles is not None:
            obj.roles.set(roles)
        return obj


class HubRoleMinimalSerializer(serializers.ModelSerializer):
    """Minimal role for nested read (no permissions list)."""

    class Meta:
        model = HubRole
        fields = ("id", "code", "name", "department", "project")


class UserHubAssignmentListSerializer(serializers.ModelSerializer):
    """List/detail with nested department, project, and roles (read-only)."""

    department = DepartmentSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)
    roles = HubRoleMinimalSerializer(many=True, read_only=True)

    class Meta:
        model = UserHubAssignment
        fields = (
            "id",
            "user",
            "department",
            "project",
            "designation",
            "is_active",
            "roles",
            "created_by",
            "created_at",
            "updated_at",
        )
