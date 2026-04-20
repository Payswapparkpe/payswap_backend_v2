"""
Hub RBAC UI for Payswap Hub — Super Admin only.
Departments, Projects, Hub Roles (dept+project wise), Sub Admin Assignments.
"""
from collections import defaultdict
from django.shortcuts import redirect
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from portal.utils.staff_utils import is_super_admin
from portal.models import LogEntry
from portal.utils.ip_utils import get_client_ip, get_user_agent
from rbac.models import Department, Project, HubRole, UserHubAssignment
from rbac.utils import get_user_hub_permissions


def _style_form_fields(form):
    for name, field in form.fields.items():
        widget = field.widget
        base_classes = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
        if widget.__class__.__name__ == "CheckboxInput":
            widget.attrs["class"] = "h-4 w-4 rounded border-gray-300 text-indigo-600"
            continue
        if widget.__class__.__name__ in {"Select", "SelectMultiple"}:
            widget.attrs["class"] = base_classes
        elif widget.__class__.__name__ == "Textarea":
            widget.attrs["class"] = base_classes
            widget.attrs.setdefault("rows", 3)
        else:
            widget.attrs["class"] = base_classes
        if name == "code":
            widget.attrs.setdefault("placeholder", "lowercase-code")
        if name == "name":
            widget.attrs.setdefault("placeholder", "Display name")
    return form


def _super_admin_required(view_func):
    """Decorator: only Super Admin (is_superuser or role_code super_admin)."""
    def wrapped(request, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            return redirect("/signin/?next=" + request.get_full_path())
        if not is_super_admin(request.user):
            messages.error(request, "Access denied. Super Admin only.")
            return redirect("/dashboard/")
        return view_func(request, *args, **kwargs)
    return wrapped


class SuperAdminRequiredMixin:
    """Mixin: require Super Admin for Hub RBAC management."""

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not is_super_admin(request.user):
            messages.error(request, "Access denied. Super Admin only.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)


class HubRbacDashboardView(SuperAdminRequiredMixin, TemplateView):
    """Hub RBAC overview — links to Departments, Projects, Roles, Sub Admin Assignments."""
    template_name = "portal/hub_rbac/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["department_count"] = Department.objects.filter(is_active=True).count()
        ctx["project_count"] = Project.objects.filter(is_active=True).count()
        ctx["hubrole_count"] = HubRole.objects.filter(is_active=True).count()
        active_assignments = UserHubAssignment.objects.filter(is_active=True)
        ctx["assignment_count"] = active_assignments.count()
        ctx["inactive_assignment_count"] = UserHubAssignment.objects.filter(is_active=False).count()
        ctx["orphan_assignment_count"] = active_assignments.filter(
            Q(department__is_active=False) | Q(project__is_active=False)
        ).distinct().count()
        ctx["unscoped_assignment_count"] = active_assignments.filter(roles__isnull=True).distinct().count()
        ctx["high_risk_role_count"] = HubRole.objects.filter(
            Q(permissions__codename__startswith="delete_")
            | Q(permissions__codename="change_user")
            | Q(permissions__codename="change_group")
            | Q(permissions__codename="change_permission"),
            is_active=True,
        ).distinct().count()
        ctx.update(self._permission_preview_context())
        return ctx

    def _permission_preview_context(self):
        User = get_user_model()
        users = User.objects.filter(is_active=True).order_by("username")[:200]
        selected_user_id = (self.request.GET.get("preview_user_id") or "").strip()

        preview = {
            "preview_users": users,
            "preview_user": None,
            "preview_permissions_grouped": [],
            "preview_assignment_rows": [],
            "preview_permission_count": 0,
        }
        if not selected_user_id.isdigit():
            return preview

        user = users.filter(pk=int(selected_user_id)).first() or User.objects.filter(pk=int(selected_user_id)).first()
        if not user:
            return preview

        preview["preview_user"] = user
        assignments = (
            UserHubAssignment.objects.filter(user=user, is_active=True)
            .select_related("department", "project")
            .prefetch_related("roles")
            .order_by("department__name", "project__name")
        )
        preview["preview_assignment_rows"] = list(assignments)

        perm_set = get_user_hub_permissions(user)
        if perm_set is None:
            preview["preview_permissions_grouped"] = [{"app_label": "all", "permissions": ["Super Admin - full access"]}]
            preview["preview_permission_count"] = 1
            return preview

        grouped = defaultdict(list)
        for perm in sorted(perm_set):
            app_label = perm.split(".", 1)[0] if "." in perm else "other"
            grouped[app_label].append(perm)
        preview["preview_permissions_grouped"] = [
            {"app_label": label, "permissions": perms}
            for label, perms in sorted(grouped.items())
        ]
        preview["preview_permission_count"] = len(perm_set)
        return preview


def _log_hub_rbac_action(request, action, target, extra_data=None):
    try:
        LogEntry.objects.create(
            log_level="INFO",
            category="security",
            message=f"Hub RBAC action: {action}",
            module_name="portal.views.hub_rbac_views",
            url=request.path,
            user=request.user if request.user.is_authenticated else None,
            client_ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            extra_data={
                "action": action,
                "target": target,
                **(extra_data or {}),
            },
        )
    except Exception:
        # Avoid blocking RBAC actions if audit log fails.
        return


# ---------- Departments ----------
class DepartmentListView(SuperAdminRequiredMixin, ListView):
    model = Department
    template_name = "portal/hub_rbac/department_list.html"
    context_object_name = "departments"
    ordering = ["name"]
    paginate_by = 25

    def get_queryset(self):
        qs = Department.objects.all().order_by("name")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        return qs


class DepartmentCreateView(SuperAdminRequiredMixin, CreateView):
    model = Department
    template_name = "portal/hub_rbac/department_form.html"
    fields = ("code", "name", "description", "is_active")
    success_url = reverse_lazy("hub_rbac_department_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        return _style_form_fields(form)

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        response = super().form_valid(form)
        _log_hub_rbac_action(
            self.request,
            action="department.create",
            target=f"department:{self.object.code}",
            extra_data={"department_id": self.object.id, "is_active": self.object.is_active},
        )
        messages.success(self.request, "Department created.")
        return response


class DepartmentUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Department
    template_name = "portal/hub_rbac/department_form.html"
    fields = ("code", "name", "description", "is_active")
    context_object_name = "department"
    success_url = reverse_lazy("hub_rbac_department_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        return _style_form_fields(form)

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        response = super().form_valid(form)
        _log_hub_rbac_action(
            self.request,
            action="department.update",
            target=f"department:{self.object.code}",
            extra_data={"department_id": self.object.id, "is_active": self.object.is_active},
        )
        messages.success(self.request, "Department updated.")
        return response


# ---------- Projects ----------
class ProjectListView(SuperAdminRequiredMixin, ListView):
    model = Project
    template_name = "portal/hub_rbac/project_list.html"
    context_object_name = "projects"
    ordering = ["name"]
    paginate_by = 25

    def get_queryset(self):
        qs = Project.objects.all().order_by("name")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        return qs


class ProjectCreateView(SuperAdminRequiredMixin, CreateView):
    model = Project
    template_name = "portal/hub_rbac/project_form.html"
    fields = ("code", "name", "description", "is_active")
    success_url = reverse_lazy("hub_rbac_project_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        return _style_form_fields(form)

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        response = super().form_valid(form)
        _log_hub_rbac_action(
            self.request,
            action="project.create",
            target=f"project:{self.object.code}",
            extra_data={"project_id": self.object.id, "is_active": self.object.is_active},
        )
        messages.success(self.request, "Project created.")
        return response


class ProjectUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Project
    template_name = "portal/hub_rbac/project_form.html"
    fields = ("code", "name", "description", "is_active")
    context_object_name = "project"
    success_url = reverse_lazy("hub_rbac_project_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        return _style_form_fields(form)

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        response = super().form_valid(form)
        _log_hub_rbac_action(
            self.request,
            action="project.update",
            target=f"project:{self.object.code}",
            extra_data={"project_id": self.object.id, "is_active": self.object.is_active},
        )
        messages.success(self.request, "Project updated.")
        return response


# ---------- Hub Roles ----------
class HubRoleListView(SuperAdminRequiredMixin, ListView):
    model = HubRole
    template_name = "portal/hub_rbac/hubrole_list.html"
    context_object_name = "roles"
    ordering = ["department", "project", "name"]
    paginate_by = 25

    def get_queryset(self):
        qs = HubRole.objects.select_related("department", "project").prefetch_related("permissions").order_by("department__name", "project__name", "name")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        return qs


class HubRoleCreateView(SuperAdminRequiredMixin, CreateView):
    model = HubRole
    template_name = "portal/hub_rbac/hubrole_form.html"
    fields = ("department", "project", "name", "code", "description", "is_active")
    success_url = reverse_lazy("hub_rbac_hubrole_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["department"].queryset = Department.objects.filter(is_active=True).order_by("name")
        form.fields["project"].queryset = Project.objects.filter(is_active=True).order_by("name")
        return _style_form_fields(form)

    def _permission_groups(self):
        grouped = {}
        action_order = ["view", "add", "change", "delete", "others"]
        for perm in Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename"):
            label = perm.content_type.app_label
            app_bucket = grouped.setdefault(
                label,
                {
                    "view": [],
                    "add": [],
                    "change": [],
                    "delete": [],
                    "others": [],
                },
            )
            codename = (perm.codename or "").lower()
            if codename.startswith("view_"):
                app_bucket["view"].append(perm)
            elif codename.startswith("add_"):
                app_bucket["add"].append(perm)
            elif codename.startswith("change_"):
                app_bucket["change"].append(perm)
            elif codename.startswith("delete_"):
                app_bucket["delete"].append(perm)
            else:
                app_bucket["others"].append(perm)

        output = []
        for label, buckets in grouped.items():
            action_groups = [
                {"action": action, "permissions": buckets[action]}
                for action in action_order
                if buckets[action]
            ]
            output.append({"app_label": label, "action_groups": action_groups})
        return output

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["all_permissions"] = Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename")
        ctx["permission_groups"] = self._permission_groups()
        ctx["assigned_ids"] = set()
        return ctx

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        response = super().form_valid(form)
        perm_ids = self.request.POST.getlist("permissions")
        if perm_ids:
            self.object.permissions.set(Permission.objects.filter(pk__in=perm_ids))
        _log_hub_rbac_action(
            self.request,
            action="hubrole.create",
            target=f"hubrole:{self.object.code}",
            extra_data={
                "hubrole_id": self.object.id,
                "department": self.object.department.code,
                "project": self.object.project.code,
                "permission_count": self.object.permissions.count(),
            },
        )
        messages.success(self.request, "Hub Role created.")
        return response


class HubRoleUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = HubRole
    template_name = "portal/hub_rbac/hubrole_form.html"
    fields = ("department", "project", "name", "code", "description", "is_active")
    context_object_name = "hubrole"
    success_url = reverse_lazy("hub_rbac_hubrole_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["department"].queryset = Department.objects.order_by("name")
        form.fields["project"].queryset = Project.objects.order_by("name")
        return _style_form_fields(form)

    def _permission_groups(self):
        grouped = {}
        action_order = ["view", "add", "change", "delete", "others"]
        for perm in Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename"):
            label = perm.content_type.app_label
            app_bucket = grouped.setdefault(
                label,
                {
                    "view": [],
                    "add": [],
                    "change": [],
                    "delete": [],
                    "others": [],
                },
            )
            codename = (perm.codename or "").lower()
            if codename.startswith("view_"):
                app_bucket["view"].append(perm)
            elif codename.startswith("add_"):
                app_bucket["add"].append(perm)
            elif codename.startswith("change_"):
                app_bucket["change"].append(perm)
            elif codename.startswith("delete_"):
                app_bucket["delete"].append(perm)
            else:
                app_bucket["others"].append(perm)

        output = []
        for label, buckets in grouped.items():
            action_groups = [
                {"action": action, "permissions": buckets[action]}
                for action in action_order
                if buckets[action]
            ]
            output.append({"app_label": label, "action_groups": action_groups})
        return output

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["all_permissions"] = Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename")
        ctx["permission_groups"] = self._permission_groups()
        ctx["assigned_ids"] = set(self.object.permissions.values_list("pk", flat=True))
        return ctx

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        response = super().form_valid(form)
        perm_ids = self.request.POST.getlist("permissions")
        self.object.permissions.set(Permission.objects.filter(pk__in=perm_ids))
        _log_hub_rbac_action(
            self.request,
            action="hubrole.update",
            target=f"hubrole:{self.object.code}",
            extra_data={
                "hubrole_id": self.object.id,
                "department": self.object.department.code,
                "project": self.object.project.code,
                "permission_count": self.object.permissions.count(),
            },
        )
        messages.success(self.request, "Hub Role updated.")
        return response


# ---------- Sub Admin Assignments ----------
class UserHubAssignmentListView(SuperAdminRequiredMixin, ListView):
    model = UserHubAssignment
    template_name = "portal/hub_rbac/assignment_list.html"
    context_object_name = "assignments"
    ordering = ["-created_at"]
    paginate_by = 25

    def get_queryset(self):
        qs = (
            UserHubAssignment.objects
            .select_related("user", "department", "project", "created_by")
            .prefetch_related("roles")
            .order_by("-created_at")
        )
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(user__username__icontains=q)
                | Q(user__email__icontains=q)
                | Q(designation__icontains=q)
            )
        return qs


class UserHubAssignmentCreateView(SuperAdminRequiredMixin, CreateView):
    model = UserHubAssignment
    template_name = "portal/hub_rbac/assignment_form.html"
    fields = ("user", "department", "project", "designation", "is_active")
    success_url = reverse_lazy("hub_rbac_assignment_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        User = get_user_model()
        form.fields["user"].queryset = User.objects.filter(is_active=True).order_by("username")
        form.fields["department"].queryset = Department.objects.filter(is_active=True).order_by("name")
        form.fields["project"].queryset = Project.objects.filter(is_active=True).order_by("name")
        return _style_form_fields(form)

    def get_initial(self):
        initial = super().get_initial()
        user_id = (self.request.GET.get("user_id") or "").strip()
        if user_id.isdigit():
            initial["user"] = int(user_id)
        return initial

    def _selected_department_project(self, form):
        department = None
        project = None
        if form.is_bound:
            dept_id = (self.request.POST.get("department") or "").strip()
            proj_id = (self.request.POST.get("project") or "").strip()
            if dept_id.isdigit():
                department = Department.objects.filter(pk=int(dept_id)).first()
            if proj_id.isdigit():
                project = Project.objects.filter(pk=int(proj_id)).first()
        else:
            department = form.initial.get("department") or form.instance.department
            project = form.initial.get("project") or form.instance.project
        return department, project

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx.get("form")
        department, project = self._selected_department_project(form)
        hub_roles = HubRole.objects.none()
        if department and project:
            hub_roles = HubRole.objects.filter(
                department=department,
                project=project,
                is_active=True,
            ).select_related("department", "project").order_by("name")
        ctx["hub_roles"] = hub_roles
        ctx["filtered_roles"] = list(hub_roles)
        ctx["assigned_role_ids"] = set()
        return ctx

    def form_valid(self, form):
        duplicate_qs = UserHubAssignment.objects.filter(
            user=form.cleaned_data["user"],
            department=form.cleaned_data["department"],
            project=form.cleaned_data["project"],
        )
        if duplicate_qs.exists():
            form.add_error(
                None,
                "This user is already assigned to the selected department and project.",
            )
            return self.form_invalid(form)

        role_ids = self.request.POST.getlist("roles")
        valid_roles = HubRole.objects.filter(
            pk__in=role_ids,
            department=form.cleaned_data["department"],
            project=form.cleaned_data["project"],
            is_active=True,
        )
        if role_ids and valid_roles.count() != len(set(role_ids)):
            form.add_error(
                None,
                "Selected roles must belong to the same department and project, and be active.",
            )
            return self.form_invalid(form)

        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        if role_ids:
            self.object.roles.set(valid_roles)
        _log_hub_rbac_action(
            self.request,
            action="assignment.create",
            target=f"assignment:{self.object.id}",
            extra_data={
                "user_id": self.object.user_id,
                "department": self.object.department.code,
                "project": self.object.project.code,
                "role_codes": list(self.object.roles.values_list("code", flat=True)),
            },
        )
        messages.success(self.request, "Sub Admin assignment created.")
        return response


class UserHubAssignmentUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = UserHubAssignment
    template_name = "portal/hub_rbac/assignment_form.html"
    fields = ("user", "department", "project", "designation", "is_active")
    context_object_name = "assignment"
    success_url = reverse_lazy("hub_rbac_assignment_list")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        User = get_user_model()
        form.fields["user"].queryset = User.objects.filter(is_active=True).order_by("username")
        form.fields["department"].queryset = Department.objects.order_by("name")
        form.fields["project"].queryset = Project.objects.order_by("name")
        return _style_form_fields(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["hub_roles"] = HubRole.objects.filter(
            department=self.object.department,
            project=self.object.project,
            is_active=True,
        ).order_by("name")
        ctx["assigned_role_ids"] = set(self.object.roles.values_list("pk", flat=True))
        return ctx

    def form_valid(self, form):
        duplicate_qs = UserHubAssignment.objects.filter(
            user=form.cleaned_data["user"],
            department=form.cleaned_data["department"],
            project=form.cleaned_data["project"],
        ).exclude(pk=self.object.pk)
        if duplicate_qs.exists():
            form.add_error(
                None,
                "This user is already assigned to the selected department and project.",
            )
            return self.form_invalid(form)

        role_ids = self.request.POST.getlist("roles")
        valid_roles = HubRole.objects.filter(
            pk__in=role_ids,
            department=form.cleaned_data["department"],
            project=form.cleaned_data["project"],
            is_active=True,
        )
        if role_ids and valid_roles.count() != len(set(role_ids)):
            form.add_error(
                None,
                "Selected roles must belong to the same department and project, and be active.",
            )
            return self.form_invalid(form)

        old_role_codes = list(self.object.roles.values_list("code", flat=True))
        response = super().form_valid(form)
        self.object.roles.set(valid_roles)
        new_role_codes = list(self.object.roles.values_list("code", flat=True))
        _log_hub_rbac_action(
            self.request,
            action="assignment.update",
            target=f"assignment:{self.object.id}",
            extra_data={
                "user_id": self.object.user_id,
                "department": self.object.department.code,
                "project": self.object.project.code,
                "old_role_codes": old_role_codes,
                "new_role_codes": new_role_codes,
                "is_active": self.object.is_active,
            },
        )
        messages.success(self.request, "Sub Admin assignment updated.")
        return response


@method_decorator(login_required, name="dispatch")
class HubRoleOptionsView(SuperAdminRequiredMixin, TemplateView):
    """
    JSON endpoint for assignment form dependent role options.
    """

    def get(self, request, *args, **kwargs):
        department_id = (request.GET.get("department_id") or "").strip()
        project_id = (request.GET.get("project_id") or "").strip()
        if not (department_id.isdigit() and project_id.isdigit()):
            return JsonResponse({"roles": [], "meta": {"total": 0}}, status=200)

        roles = (
            HubRole.objects.filter(
                department_id=int(department_id),
                project_id=int(project_id),
                is_active=True,
            )
            .annotate(permission_count=Count("permissions", distinct=True))
            .order_by("name")
            .values("id", "name", "code", "permission_count")
        )
        payload = []
        for row in roles:
            payload.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "code": row["code"],
                    "permission_count": row["permission_count"],
                }
            )
        return JsonResponse({"roles": payload, "meta": {"total": len(payload)}}, status=200)
