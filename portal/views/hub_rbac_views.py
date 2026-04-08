"""
Hub RBAC UI for Payswap Hub — Super Admin only.
Departments, Projects, Hub Roles (dept+project wise), Sub Admin Assignments.
"""
from django.shortcuts import redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.models import Permission
from portal.utils.staff_utils import is_super_admin
from rbac.models import Department, Project, HubRole, UserHubAssignment


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
        ctx["assignment_count"] = UserHubAssignment.objects.filter(is_active=True).count()
        return ctx


# ---------- Departments ----------
class DepartmentListView(SuperAdminRequiredMixin, ListView):
    model = Department
    template_name = "portal/hub_rbac/department_list.html"
    context_object_name = "departments"
    ordering = ["name"]

    def get_queryset(self):
        return Department.objects.all().order_by("name")


class DepartmentCreateView(SuperAdminRequiredMixin, CreateView):
    model = Department
    template_name = "portal/hub_rbac/department_form.html"
    fields = ("code", "name", "description", "is_active")
    success_url = reverse_lazy("hub_rbac_department_list")

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        messages.success(self.request, "Department created.")
        return super().form_valid(form)


class DepartmentUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Department
    template_name = "portal/hub_rbac/department_form.html"
    fields = ("code", "name", "description", "is_active")
    context_object_name = "department"
    success_url = reverse_lazy("hub_rbac_department_list")

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        messages.success(self.request, "Department updated.")
        return super().form_valid(form)


# ---------- Projects ----------
class ProjectListView(SuperAdminRequiredMixin, ListView):
    model = Project
    template_name = "portal/hub_rbac/project_list.html"
    context_object_name = "projects"
    ordering = ["name"]


class ProjectCreateView(SuperAdminRequiredMixin, CreateView):
    model = Project
    template_name = "portal/hub_rbac/project_form.html"
    fields = ("code", "name", "description", "is_active")
    success_url = reverse_lazy("hub_rbac_project_list")

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        messages.success(self.request, "Project created.")
        return super().form_valid(form)


class ProjectUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Project
    template_name = "portal/hub_rbac/project_form.html"
    fields = ("code", "name", "description", "is_active")
    context_object_name = "project"
    success_url = reverse_lazy("hub_rbac_project_list")

    def form_valid(self, form):
        form.instance.code = (form.cleaned_data.get("code") or "").strip().lower()
        messages.success(self.request, "Project updated.")
        return super().form_valid(form)


# ---------- Hub Roles ----------
class HubRoleListView(SuperAdminRequiredMixin, ListView):
    model = HubRole
    template_name = "portal/hub_rbac/hubrole_list.html"
    context_object_name = "roles"
    ordering = ["department", "project", "name"]

    def get_queryset(self):
        return HubRole.objects.select_related("department", "project").prefetch_related("permissions").order_by("department__name", "project__name", "name")


class HubRoleCreateView(SuperAdminRequiredMixin, CreateView):
    model = HubRole
    template_name = "portal/hub_rbac/hubrole_form.html"
    fields = ("department", "project", "name", "code", "description", "is_active")
    success_url = reverse_lazy("hub_rbac_hubrole_list")

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
        messages.success(self.request, "Hub Role created.")
        return response


class HubRoleUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = HubRole
    template_name = "portal/hub_rbac/hubrole_form.html"
    fields = ("department", "project", "name", "code", "description", "is_active")
    context_object_name = "hubrole"
    success_url = reverse_lazy("hub_rbac_hubrole_list")

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
        messages.success(self.request, "Hub Role updated.")
        return response


# ---------- Sub Admin Assignments ----------
class UserHubAssignmentListView(SuperAdminRequiredMixin, ListView):
    model = UserHubAssignment
    template_name = "portal/hub_rbac/assignment_list.html"
    context_object_name = "assignments"
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            UserHubAssignment.objects
            .select_related("user", "department", "project", "created_by")
            .prefetch_related("roles")
            .order_by("-created_at")
        )


class UserHubAssignmentCreateView(SuperAdminRequiredMixin, CreateView):
    model = UserHubAssignment
    template_name = "portal/hub_rbac/assignment_form.html"
    fields = ("user", "department", "project", "designation", "is_active")
    success_url = reverse_lazy("hub_rbac_assignment_list")

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
        messages.success(self.request, "Sub Admin assignment created.")
        return response


class UserHubAssignmentUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = UserHubAssignment
    template_name = "portal/hub_rbac/assignment_form.html"
    fields = ("user", "department", "project", "designation", "is_active")
    context_object_name = "assignment"
    success_url = reverse_lazy("hub_rbac_assignment_list")

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

        response = super().form_valid(form)
        self.object.roles.set(valid_roles)
        messages.success(self.request, "Sub Admin assignment updated.")
        return response
