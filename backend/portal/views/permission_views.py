"""
Portal permission and role management views.
"""
from collections import OrderedDict

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import Permission
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views import View
from django.http import JsonResponse
from django.urls import reverse

from portal.models import User, Role
from portal.forms import PermissionAssignForm, RoleChangeForm
from portal.permissions import CanManagePermissions
from portal.utils.role_utils import (
    assign_permission_to_user,
    revoke_permission_from_user,
    change_user_role,
    assign_permission_to_role,
    revoke_permission_from_role,
    get_user_permissions,
)
from portal.tasks.logging_tasks import log_user_action_task


def _permissions_by_category(permission_list):
    """Group permission list by app_label then by model. Returns OrderedDict[app_label, OrderedDict[model, list]]."""
    by_app = OrderedDict()
    for perm in sorted(permission_list, key=lambda p: (p.content_type.app_label, p.content_type.model, p.codename)):
        app = perm.content_type.app_label
        model = perm.content_type.model
        if app not in by_app:
            by_app[app] = OrderedDict()
        if model not in by_app[app]:
            by_app[app][model] = []
        by_app[app][model].append(perm)
    return by_app


class PermissionManageView(View):
    """Permission management view"""
    template_name = 'portal/permissions/manage.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not CanManagePermissions().has_permission(self.request, self):
            messages.error(self.request, 'You do not have permission to manage permissions.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        users = User.objects.filter(is_active=True).select_related('role')
        permissions = Permission.objects.all().select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'
        )
        roles = Role.objects.all().prefetch_related('default_permissions')
        permissions_by_app = OrderedDict()
        for perm in permissions:
            app = perm.content_type.app_label
            if app not in permissions_by_app:
                permissions_by_app[app] = []
            permissions_by_app[app].append(perm)
        user_permissions_map = {}
        for user in users:
            user_permissions_map[user.id] = get_user_permissions(user)
        context = {
            'users': users,
            'permissions': permissions,
            'permissions_by_app': permissions_by_app,
            'roles': roles,
            'user_permissions_map': user_permissions_map,
            'stats': {
                'total_users': users.count(),
                'total_roles': roles.count(),
                'total_permissions': permissions.count(),
            },
        }
        return render(request, self.template_name, context)

    def post(self, request):
        action = request.POST.get('action')
        if action == 'assign_permission':
            form = PermissionAssignForm(request.POST)
            if form.is_valid():
                user = form.cleaned_data['user_id']
                permission = form.cleaned_data['permission_id']
                try:
                    assign_permission_to_user(user, permission)
                    log_user_action_task.delay(
                        action='assign_permission',
                        user_id=request.user.id,
                        resource='user',
                        resource_id=str(user.id),
                        status='success',
                        extra_data={
                            'target_user': user.username,
                            'permission': f"{permission.content_type.app_label}.{permission.codename}"
                        }
                    )
                    messages.success(request, f'Permission assigned to {user.username}')
                except Exception as e:
                    messages.error(request, f'Error assigning permission: {str(e)}')
        elif action == 'revoke_permission':
            user_id = request.POST.get('user_id')
            permission_id = request.POST.get('permission_id')
            try:
                user = User.objects.get(id=user_id)
                permission = Permission.objects.get(id=permission_id)
                revoke_permission_from_user(user, permission)
                log_user_action_task.delay(
                    action='revoke_permission',
                    user_id=request.user.id,
                    resource='user',
                    resource_id=str(user.id),
                    status='success',
                    extra_data={
                        'target_user': user.username,
                        'permission': f"{permission.content_type.app_label}.{permission.codename}"
                    }
                )
                messages.success(request, f'Permission revoked from {user.username}')
            except Exception as e:
                messages.error(request, f'Error revoking permission: {str(e)}')
        elif action == 'change_role':
            form = RoleChangeForm(request.POST)
            if form.is_valid():
                user = form.cleaned_data['user_id']
                role_code = form.cleaned_data['role_code']
                try:
                    change_user_role(user, role_code)
                    log_user_action_task.delay(
                        action='change_role',
                        user_id=request.user.id,
                        resource='user',
                        resource_id=str(user.id),
                        status='success',
                        extra_data={'target_user': user.username, 'new_role': role_code}
                    )
                    messages.success(request, f'Role changed for {user.username} to {role_code}')
                except Exception as e:
                    messages.error(request, f'Error changing role: {str(e)}')
        elif action == 'assign_role_permission':
            role_id = request.POST.get('role_id')
            permission_id = request.POST.get('permission_id')
            try:
                role = Role.objects.get(id=role_id)
                permission = Permission.objects.get(id=permission_id)
                assign_permission_to_role(role, permission)
                log_user_action_task.delay(
                    action='assign_role_permission',
                    user_id=request.user.id,
                    resource='role',
                    resource_id=str(role.id),
                    status='success',
                    extra_data={
                        'role': role.code,
                        'permission': f"{permission.content_type.app_label}.{permission.codename}"
                    }
                )
                messages.success(request, f'Permission assigned to role {role.name}')
            except Exception as e:
                messages.error(request, f'Error assigning permission to role: {str(e)}')
        elif action == 'revoke_role_permission':
            role_id = request.POST.get('role_id')
            permission_id = request.POST.get('permission_id')
            try:
                role = Role.objects.get(id=role_id)
                permission = Permission.objects.get(id=permission_id)
                revoke_permission_from_role(role, permission)
                log_user_action_task.delay(
                    action='revoke_role_permission',
                    user_id=request.user.id,
                    resource='role',
                    resource_id=str(role.id),
                    status='success',
                    extra_data={
                        'role': role.code,
                        'permission': f"{permission.content_type.app_label}.{permission.codename}"
                    }
                )
                messages.success(request, f'Permission revoked from role {role.name}')
            except Exception as e:
                messages.error(request, f'Error revoking permission from role: {str(e)}')
        return redirect('/permissions/')


class PermissionManageUserView(View):
    """Manage user permissions with category-wise checkboxes."""
    template_name = 'portal/permissions/manage_bulk.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not CanManagePermissions().has_permission(self.request, self):
            messages.error(self.request, 'You do not have permission to manage permissions.')
            return redirect('/permissions/')
        return super().dispatch(*args, **kwargs)

    def get(self, request, user_id):
        target_user = User.objects.filter(id=user_id, is_active=True).select_related('role').first()
        if not target_user:
            messages.error(request, 'User not found.')
            return redirect('/permissions/')
        all_permissions = list(
            Permission.objects.all().select_related('content_type').order_by(
                'content_type__app_label', 'content_type__model', 'codename'
            )
        )
        assigned_ids = {p.id for p in get_user_permissions(target_user)}
        assigned = [p for p in all_permissions if p.id in assigned_ids]
        unassigned = [p for p in all_permissions if p.id not in assigned_ids]
        context = {
            'target_user': target_user,
            'target_type': 'user',
            'target_display': target_user.username,
            'assigned_by_category': _permissions_by_category(assigned),
            'unassigned_by_category': _permissions_by_category(unassigned),
            'assigned_count': len(assigned),
            'unassigned_count': len(unassigned),
            'post_url': reverse('permissions_manage_user', kwargs={'user_id': target_user.id}),
            'back_url': reverse('permissions'),
        }
        return render(request, self.template_name, context)

    def post(self, request, user_id):
        target_user = User.objects.filter(id=user_id, is_active=True).first()
        if not target_user:
            messages.error(request, 'User not found.')
            return redirect('/permissions/')
        action = request.POST.get('action')
        permission_ids = request.POST.getlist('permission_ids')
        if action == 'bulk_assign' and permission_ids:
            for pid in permission_ids:
                try:
                    perm = Permission.objects.get(id=int(pid))
                    assign_permission_to_user(target_user, perm)
                except (Permission.DoesNotExist, ValueError):
                    continue
            messages.success(request, f'Assigned {len(permission_ids)} permission(s) to {target_user.username}.')
        elif action == 'bulk_revoke' and permission_ids:
            for pid in permission_ids:
                try:
                    perm = Permission.objects.get(id=int(pid))
                    revoke_permission_from_user(target_user, perm)
                except (Permission.DoesNotExist, ValueError):
                    continue
            messages.success(request, f'Revoked {len(permission_ids)} permission(s) from {target_user.username}.')
        return redirect('permissions_manage_user', user_id=user_id)


class PermissionManageRoleView(View):
    """Manage role permissions with category-wise checkboxes."""
    template_name = 'portal/permissions/manage_bulk.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not CanManagePermissions().has_permission(self.request, self):
            messages.error(self.request, 'You do not have permission to manage permissions.')
            return redirect('/permissions/')
        return super().dispatch(*args, **kwargs)

    def get(self, request, role_id):
        target_role = Role.objects.filter(id=role_id).prefetch_related('default_permissions').first()
        if not target_role:
            messages.error(request, 'Role not found.')
            return redirect('/permissions/')
        all_permissions = list(
            Permission.objects.all().select_related('content_type').order_by(
                'content_type__app_label', 'content_type__model', 'codename'
            )
        )
        assigned_ids = {p.id for p in target_role.default_permissions.all()}
        assigned = [p for p in all_permissions if p.id in assigned_ids]
        unassigned = [p for p in all_permissions if p.id not in assigned_ids]
        context = {
            'target_role': target_role,
            'target_type': 'role',
            'target_display': target_role.name,
            'assigned_by_category': _permissions_by_category(assigned),
            'unassigned_by_category': _permissions_by_category(unassigned),
            'assigned_count': len(assigned),
            'unassigned_count': len(unassigned),
            'post_url': reverse('permissions_manage_role', kwargs={'role_id': target_role.id}),
            'back_url': reverse('permissions'),
        }
        return render(request, self.template_name, context)

    def post(self, request, role_id):
        target_role = Role.objects.filter(id=role_id).first()
        if not target_role:
            messages.error(request, 'Role not found.')
            return redirect('/permissions/')
        action = request.POST.get('action')
        permission_ids = request.POST.getlist('permission_ids')
        if action == 'bulk_assign' and permission_ids:
            for pid in permission_ids:
                try:
                    perm = Permission.objects.get(id=int(pid))
                    assign_permission_to_role(target_role, perm)
                except (Permission.DoesNotExist, ValueError):
                    continue
            messages.success(request, f'Assigned {len(permission_ids)} permission(s) to role {target_role.name}.')
        elif action == 'bulk_revoke' and permission_ids:
            for pid in permission_ids:
                try:
                    perm = Permission.objects.get(id=int(pid))
                    revoke_permission_from_role(target_role, perm)
                except (Permission.DoesNotExist, ValueError):
                    continue
            messages.success(request, f'Revoked {len(permission_ids)} permission(s) from role {target_role.name}.')
        return redirect('permissions_manage_role', role_id=role_id)


@require_http_methods(["POST"])
@login_required
def assign_permission_view(request):
    """Assign permission to user"""
    if not CanManagePermissions().has_permission(request, None):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    form = PermissionAssignForm(request.POST)
    if form.is_valid():
        try:
            user = form.cleaned_data['user_id']
            permission = form.cleaned_data['permission_id']
            assign_permission_to_user(user, permission)
            log_user_action_task.delay(
                action='assign_permission',
                user_id=request.user.id,
                resource='user',
                resource_id=str(user.id),
                status='success',
                extra_data={
                    'target_user': user.username,
                    'permission': f"{permission.content_type.app_label}.{permission.codename}"
                }
            )
            return JsonResponse({'success': True, 'message': 'Permission assigned'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'errors': form.errors})


@require_http_methods(["POST"])
@login_required
def revoke_permission_view(request):
    """Revoke permission from user"""
    if not CanManagePermissions().has_permission(request, None):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    try:
        user_id = request.POST.get('user_id')
        permission_id = request.POST.get('permission_id')
        user = User.objects.get(id=user_id)
        permission = Permission.objects.get(id=permission_id)
        revoke_permission_from_user(user, permission)
        log_user_action_task.delay(
            action='revoke_permission',
            user_id=request.user.id,
            resource='user',
            resource_id=str(user.id),
            status='success',
            extra_data={
                'target_user': user.username,
                'permission': f"{permission.content_type.app_label}.{permission.codename}"
            }
        )
        return JsonResponse({'success': True, 'message': 'Permission revoked'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def change_role_view(request):
    """Change user role"""
    if not CanManagePermissions().has_permission(request, None):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    form = RoleChangeForm(request.POST)
    if form.is_valid():
        try:
            user = form.cleaned_data['user_id']
            role_code = form.cleaned_data['role_code']
            change_user_role(user, role_code)
            log_user_action_task.delay(
                action='change_role',
                user_id=request.user.id,
                resource='user',
                resource_id=str(user.id),
                status='success',
                extra_data={'target_user': user.username, 'new_role': role_code}
            )
            return JsonResponse({'success': True, 'message': 'Role changed'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'errors': form.errors})
