"""
Portal user management views.
"""
from datetime import datetime

from django import forms
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views import View
from django.views.generic import ListView, DetailView, CreateView
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.urls import reverse, NoReverseMatch

from portal.models import User, Profile, Wallet
from portal.forms import UserCreateForm
from portal.permissions import CanCreateUser
from portal.utils.permission_utils import user_has_permission


class UserListView(ListView):
    """User list view"""
    model = User
    template_name = 'portal/users/list.html'
    context_object_name = 'users'
    paginate_by = 20

    ADMIN_TAB_ROLES = {'super_admin', 'admin', 'employee'}
    PAYSWAP_TAB_ROLES = {'retailer', 'distributor', 'super_distributor'}
    FLEET_TAB_ROLES = {'fleet_admin', 'fleet_manager', 'fleet_operator', 'fleet_dispatcher'}
    PARKING_TAB_ROLES = {'parking_owner', 'parking_manager', 'parking_attendant'}
    PARKPE_TAB_ROLES = {
        'customer',
        *FLEET_TAB_ROLES,
        *PARKING_TAB_ROLES,
    }

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def _tab_role_codes(self, tab):
        if tab == 'admin':
            return self.ADMIN_TAB_ROLES
        if tab == 'payswap':
            return self.PAYSWAP_TAB_ROLES
        if tab == 'fleet':
            return self.FLEET_TAB_ROLES
        if tab == 'parking':
            return self.PARKING_TAB_ROLES
        if tab == 'parkpe':
            return self.PARKPE_TAB_ROLES
        return None

    def _parse_date(self, raw):
        if not raw:
            return None
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            return None

    def _apply_common_filters(self, qs, q, from_date, to_date):
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(email__icontains=q)
                | Q(profile__phone__icontains=q)
                | Q(profile__first_name__icontains=q)
                | Q(profile__last_name__icontains=q)
            )
        if from_date:
            qs = qs.filter(date_joined__date__gte=from_date)
        if to_date:
            qs = qs.filter(date_joined__date__lte=to_date)
        return qs

    def get_queryset(self):
        tab = (self.request.GET.get('tab') or 'all').strip().lower()
        if tab not in {'all', 'admin', 'payswap', 'parkpe', 'fleet', 'parking'}:
            tab = 'all'
        q = (self.request.GET.get('q') or '').strip()
        from_date = self._parse_date(self.request.GET.get('from_date'))
        to_date = self._parse_date(self.request.GET.get('to_date'))

        qs = User.objects.select_related('profile', 'role').order_by('-date_joined')
        qs = self._apply_common_filters(qs, q, from_date, to_date)

        role_codes = self._tab_role_codes(tab)
        if role_codes:
            qs = qs.filter(role_code__in=role_codes)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab = (self.request.GET.get('tab') or 'all').strip().lower()
        if tab not in {'all', 'admin', 'payswap', 'parkpe', 'fleet', 'parking'}:
            tab = 'all'
        q = (self.request.GET.get('q') or '').strip()
        from_date_raw = self.request.GET.get('from_date') or ''
        to_date_raw = self.request.GET.get('to_date') or ''
        from_date = self._parse_date(from_date_raw)
        to_date = self._parse_date(to_date_raw)

        base_qs = User.objects.all()
        filtered_no_tab = self._apply_common_filters(base_qs, q, from_date, to_date)
        tab_counts = {
            'all': filtered_no_tab.count(),
            'admin': filtered_no_tab.filter(role_code__in=self.ADMIN_TAB_ROLES).count(),
            'payswap': filtered_no_tab.filter(role_code__in=self.PAYSWAP_TAB_ROLES).count(),
            'fleet': filtered_no_tab.filter(role_code__in=self.FLEET_TAB_ROLES).count(),
            'parking': filtered_no_tab.filter(role_code__in=self.PARKING_TAB_ROLES).count(),
            'parkpe': filtered_no_tab.filter(role_code__in=self.PARKPE_TAB_ROLES).count(),
        }

        users = context.get('users') or []
        for user_item in users:
            rc = (user_item.role_code or '').lower()
            if rc in self.PAYSWAP_TAB_ROLES:
                user_item.platform_label = 'Payswap'
            elif rc in self.PARKPE_TAB_ROLES:
                if rc.startswith('fleet_'):
                    user_item.platform_label = 'ParkPe Fleet'
                elif rc.startswith('parking_'):
                    user_item.platform_label = 'ParkPe Parking'
                else:
                    user_item.platform_label = 'ParkPe'
            else:
                user_item.platform_label = 'Admin'

        params = self.request.GET.copy()
        if 'page' in params:
            params.pop('page')
        context['active_tab'] = tab
        context['search_query'] = q
        context['from_date'] = from_date_raw
        context['to_date'] = to_date_raw
        context['tab_counts'] = tab_counts
        context['query_string'] = params.urlencode()
        try:
            reverse('user_edit', kwargs={'user_id': 1})
            context['has_user_edit_route'] = True
        except NoReverseMatch:
            context['has_user_edit_route'] = False
        try:
            reverse('user_delete', kwargs={'user_id': 1})
            context['has_user_delete_route'] = True
        except NoReverseMatch:
            context['has_user_delete_route'] = False
        try:
            reverse('hub_rbac_assignment_create')
            context['has_hub_assignment_create_route'] = True
        except NoReverseMatch:
            context['has_hub_assignment_create_route'] = False
        return context


class UserCreateView(CreateView):
    """User creation view (Admin only)"""
    model = User
    form_class = UserCreateForm
    template_name = 'portal/users/create.html'
    success_url = '/users/'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not CanCreateUser().has_permission(self.request, self):
            messages.error(self.request, 'You do not have permission to create users.')
            return redirect('/dashboard/')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if 'instance' in kwargs:
            kwargs.pop('instance')
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                username = form.cleaned_data.get('username') or None
                role_code = form.cleaned_data['role_code']
                user = User.objects.create_user(
                    username=username,
                    password=form.cleaned_data['password1'],
                    role_code=role_code,
                    created_by=self.request.user,
                )
                business_role_codes = {
                    'super_distributor',
                    'distributor',
                    'retailer',
                    'fleet_admin',
                    'fleet_manager',
                    'parking_owner',
                    'parking_manager',
                }
                profile_type = 'business' if role_code in business_role_codes else 'individual'
                Profile.objects.create(
                    user=user,
                    first_name=form.cleaned_data.get('first_name'),
                    email=form.cleaned_data.get('email'),
                    phone=form.cleaned_data.get('phone'),
                    type=profile_type,
                    created_by=self.request.user,
                )
                Wallet.objects.get_or_create(user=user)
                if role_code.startswith('parking_'):
                    try:
                        from portal.models.parking import ParkingOperator, ParkingLocation
                        location = ParkingLocation.objects.order_by('id').first()
                        if location:
                            parking_role_map = {
                                'parking_owner': ParkingOperator.ROLE_OWNER,
                                'parking_manager': ParkingOperator.ROLE_MANAGER,
                                'parking_attendant': ParkingOperator.ROLE_ATTENDANT,
                            }
                            ParkingOperator.objects.get_or_create(
                                user=user,
                                location=location,
                                defaults={
                                    'role': parking_role_map.get(role_code, ParkingOperator.ROLE_ATTENDANT),
                                    'is_active': True,
                                    'notes': 'Auto-linked during user creation.',
                                },
                            )
                    except Exception:
                        pass
                assignment_url = reverse('hub_rbac_assignment_create') + f'?user_id={user.pk}'
                messages.success(
                    self.request,
                    f'User {user.username} created successfully! Next: map Hub assignment and roles.'
                )
        except Exception as e:
            messages.error(self.request, f'Error creating user: {str(e)}')
            return self.form_invalid(form)
        return redirect(assignment_url)


class UserDetailView(DetailView):
    """User detail view"""
    model = User
    template_name = 'portal/users/detail.html'
    context_object_name = 'user_detail'
    pk_url_kwarg = 'user_id'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class UserEditForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    role_code = forms.ChoiceField(choices=User.ROLE_CHOICES, required=True)
    is_active = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError('Username is required.')
        qs = User.objects.filter(username=username)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This username is already in use.')
        return username

    def clean_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip()
        if not phone:
            return phone
        qs = Profile.objects.filter(phone=phone)
        if self.instance:
            qs = qs.exclude(user=self.instance)
        if qs.exists():
            raise forms.ValidationError('This mobile number is already in use.')
        return phone

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not email:
            return email
        qs = Profile.objects.filter(email=email)
        if self.instance:
            qs = qs.exclude(user=self.instance)
        if qs.exists():
            raise forms.ValidationError('This email is already in use.')
        return email


class UserEditView(View):
    template_name = 'portal/users/edit.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not user_has_permission(request.user, 'portal.change_user'):
            messages.error(request, 'You do not have permission to edit users.')
            return redirect('user_list')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, user_id):
        user_obj = get_object_or_404(User.objects.select_related('profile'), pk=user_id)
        profile = getattr(user_obj, 'profile', None)
        initial = {
            'username': user_obj.username,
            'first_name': getattr(profile, 'first_name', '') or '',
            'last_name': getattr(profile, 'last_name', '') or '',
            'email': getattr(profile, 'email', '') or (user_obj.email or ''),
            'phone': getattr(profile, 'phone', '') or '',
            'role_code': user_obj.role_code,
            'is_active': user_obj.is_active,
        }
        form = UserEditForm(initial=initial, instance=user_obj)
        return render(request, self.template_name, {'form': form, 'user_obj': user_obj})

    def post(self, request, user_id):
        user_obj = get_object_or_404(User.objects.select_related('profile'), pk=user_id)
        form = UserEditForm(request.POST, instance=user_obj)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'user_obj': user_obj})
        with transaction.atomic():
            user_obj.username = form.cleaned_data['username']
            user_obj.role_code = form.cleaned_data['role_code']
            user_obj.is_active = form.cleaned_data['is_active']
            user_obj.save(update_fields=['username', 'role_code', 'is_active', 'updated_at'])

            profile, _ = Profile.objects.get_or_create(user=user_obj)
            profile.first_name = form.cleaned_data.get('first_name') or ''
            profile.last_name = form.cleaned_data.get('last_name') or ''
            profile.email = form.cleaned_data.get('email') or ''
            profile.phone = form.cleaned_data.get('phone') or ''
            profile.save()
        messages.success(request, f'User {user_obj.username} updated successfully.')
        return redirect('user_detail', user_id=user_obj.pk)


class UserDeleteView(View):
    template_name = 'portal/users/delete.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not user_has_permission(request.user, 'portal.delete_user'):
            messages.error(request, 'You do not have permission to delete users.')
            return redirect('user_list')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, user_id):
        user_obj = get_object_or_404(User, pk=user_id)
        is_super_admin = (
            getattr(request.user, 'role_code', '') == 'super_admin'
            or getattr(request.user, 'is_superuser', False)
        )
        return render(
            request,
            self.template_name,
            {
                'user_obj': user_obj,
                'can_permanent_delete': is_super_admin,
            },
        )

    def post(self, request, user_id):
        user_obj = get_object_or_404(User, pk=user_id)
        if user_obj.pk == request.user.pk:
            messages.error(request, 'You cannot delete your own account.')
            return redirect('user_list')
        action = (request.POST.get('action') or 'deactivate').strip().lower()
        is_super_admin = (
            getattr(request.user, 'role_code', '') == 'super_admin'
            or getattr(request.user, 'is_superuser', False)
        )
        if action == 'permanent':
            if not is_super_admin:
                messages.error(request, 'Only Super Admin can permanently delete users.')
                return redirect('user_detail', user_id=user_obj.pk)
            try:
                username = user_obj.username
                user_obj.delete()
                messages.success(request, f'User {username} has been permanently deleted.')
            except (ProtectedError, IntegrityError):
                messages.error(
                    request,
                    'Permanent delete blocked because this user is referenced by other records. '
                    'Please deactivate instead.',
                )
                return redirect('user_detail', user_id=user_obj.pk)
            return redirect('user_list')

        user_obj.is_active = False
        user_obj.save(update_fields=['is_active', 'updated_at'])
        messages.success(request, f'User {user_obj.username} has been deactivated.')
        return redirect('user_list')
