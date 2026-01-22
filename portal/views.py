"""
Portal Views - All views for user management, authentication, dashboards
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView
from django.contrib import messages
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.db import transaction
from portal.models import User, Profile, KYC, Wallet, WalletTransaction, Role
from portal.forms import (
    SignUpForm, SignInForm, MFASetupForm, MFAVerifyForm,
    ProfileCreateForm, UserCreateForm, KYCSubmitForm,
    PermissionAssignForm, RoleChangeForm
)
from portal.utils.mfa_utils import (
    generate_totp_secret, generate_totp_uri, generate_qr_code,
    verify_totp, store_otp_in_cache, verify_otp_from_cache
)
from portal.utils.user_utils import is_mfa_required_role
from portal.permissions import CanCreateUser, CanManageKYC, CanManagePermissions
from portal.utils.logging_helper import get_logger
from portal.tasks.logging_tasks import log_user_action_task, log_security_event_task
from portal.utils.role_utils import (
    assign_permission_to_user, revoke_permission_from_user,
    change_user_role, assign_permission_to_role, revoke_permission_from_role
)

logger = get_logger('portal.views')


class LandingPageView(TemplateView):
    """Landing page view"""
    template_name = 'portal/landing.html'


class SignInView(View):
    """Sign in view"""
    template_name = 'portal/auth/signin.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        form = SignInForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = SignInForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=username, password=password)
            if user:
                if not user.is_active:
                    log_security_event_task.delay(
                        event_type='failed_login',
                        message='Login attempt with inactive account',
                        user_id=user.id,
                        severity='medium',
                        extra_data={'reason': 'inactive_account'}
                    )
                    messages.error(request, 'Your account is inactive.')
                    return render(request, self.template_name, {'form': form})
                
                if not user.email_verified:
                    log_security_event_task.delay(
                        event_type='failed_login',
                        message='Login attempt with unverified email',
                        user_id=user.id,
                        severity='low',
                        extra_data={'reason': 'email_not_verified'}
                    )
                    messages.error(request, 'Please verify your email before signing in.')
                    return render(request, self.template_name, {'form': form})
                
                # Check if MFA is required
                if user.requires_mfa():
                    if not user.mfa_configured:
                        # Store user ID in session for MFA setup
                        request.session['mfa_setup_user_id'] = user.id
                        messages.info(request, 'MFA setup is required for your role.')
                        return redirect('/mfa/setup/')
                    else:
                        # Store user ID in session for MFA verification
                        request.session['mfa_verify_user_id'] = user.id
                        return redirect('/mfa/verify/')
                else:
                    # No MFA required, login directly
                    login(request, user)
                    log_user_action_task.delay(
                        action='login',
                        user_id=user.id,
                        status='success'
                    )
                    return redirect('/dashboard/')
            else:
                log_security_event_task.delay(
                    event_type='failed_login',
                    message='Invalid credentials',
                    severity='medium',
                    extra_data={'username': username}
                )
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
        
        return render(request, self.template_name, {'form': form})


class SignUpView(View):
    """Sign up view for self-onboarding (Customer/Retailer)"""
    template_name = 'portal/auth/signup.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        form = SignUpForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create profile first
                    profile = Profile.objects.create(
                        name=form.cleaned_data.get('email', '').split('@')[0],
                        type='individual',
                        phone=form.cleaned_data.get('phone'),
                        email=form.cleaned_data.get('email'),
                    )
                    
                    # Create user (username will be auto-generated)
                    user = User.objects.create_user(
                        first_name=form.cleaned_data.get('first_name'),
                        email=form.cleaned_data.get('email'),
                        password=form.cleaned_data['password1'],
                        role_code=form.cleaned_data['role_code'],
                        profile=profile,
                        phone=form.cleaned_data.get('phone'),
                        email_verified=False,  # Will be verified via email
                    )
                    
                    # Create wallet
                    Wallet.objects.create(user=user)
                    
                    log_user_action_task.delay(
                        action='signup',
                        user_id=user.id,
                        resource='user',
                        resource_id=str(user.id),
                        status='success',
                        extra_data={'role': form.cleaned_data['role_code']}
                    )
                    
                    messages.success(request, 'Account created successfully! Please verify your email.')
                    return redirect('/signin/')
            except Exception as e:
                messages.error(request, f'Error creating account: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
        
        return render(request, self.template_name, {'form': form})


class MFASetupView(View):
    """MFA setup view"""
    template_name = 'portal/auth/mfa_setup.html'
    
    def get(self, request):
        user_id = request.session.get('mfa_setup_user_id')
        if not user_id:
            messages.error(request, 'Invalid session. Please sign in again.')
            return redirect('/signin/')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('/signin/')
        
        form = MFASetupForm()
        context = {
            'form': form,
            'user': user,
        }
        
        # If authenticator method, generate QR code
        if request.GET.get('method') == 'authenticator':
            secret = generate_totp_secret()
            uri = generate_totp_uri(secret, user.email)
            qr_code = generate_qr_code(uri)
            context['qr_code'] = qr_code
            context['totp_secret'] = secret
            request.session['mfa_setup_secret'] = secret
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        user_id = request.session.get('mfa_setup_user_id')
        if not user_id:
            messages.error(request, 'Invalid session.')
            return redirect('/signin/')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('/signin/')
        
        form = MFASetupForm(request.POST)
        if form.is_valid():
            mfa_method = form.cleaned_data['mfa_method']
            
            if mfa_method == 'otp':
                phone = form.cleaned_data['phone']
                # Store phone for OTP
                user.phone = phone
                user.mfa_method = 'otp'
                user.mfa_configured = True
                user.mfa_enabled = True
                user.save()
                
                # Send OTP via Kaleyra service
                from portal.services.otp_service import OTPService
                otp_service = OTPService()
                success, message = otp_service.send_otp(phone)
                if success:
                    messages.success(request, 'MFA configured successfully. OTP sent to your phone.')
                    del request.session['mfa_setup_user_id']
                    login(request, user)
                    return redirect('/dashboard/')
                else:
                    messages.error(request, f'Failed to send OTP: {message}')
                    return render(request, self.template_name, {'form': form, 'user': user})
            
            elif mfa_method == 'authenticator':
                secret = request.session.get('mfa_setup_secret')
                if not secret:
                    messages.error(request, 'Please refresh the page and try again.')
                    return redirect('/mfa/setup/?method=authenticator')
                
                totp_code = form.cleaned_data.get('totp_code')
                if not totp_code or not verify_totp(secret, totp_code):
                    messages.error(request, 'Invalid verification code.')
                    return redirect('/mfa/setup/?method=authenticator')
                
                # Save TOTP secret
                user.set_encrypted_totp_secret(secret)
                user.mfa_method = 'authenticator'
                user.mfa_configured = True
                user.mfa_enabled = True
                user.save()
                
                messages.success(request, 'MFA configured successfully with Authenticator.')
                del request.session['mfa_setup_user_id']
                del request.session['mfa_setup_secret']
                login(request, user)
                return redirect('/dashboard/')
        
        messages.error(request, 'Please correct the errors below.')
        return render(request, self.template_name, {'form': form, 'user': user})


class MFAVerifyView(View):
    """MFA verification view"""
    template_name = 'portal/auth/mfa_verify.html'
    
    def get(self, request):
        user_id = request.session.get('mfa_verify_user_id')
        if not user_id:
            messages.error(request, 'Invalid session. Please sign in again.')
            return redirect('/signin/')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('/signin/')
        
        form = MFAVerifyForm()
        return render(request, self.template_name, {'form': form, 'user': user})
    
    def post(self, request):
        user_id = request.session.get('mfa_verify_user_id')
        if not user_id:
            messages.error(request, 'Invalid session.')
            return redirect('/signin/')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('/signin/')
        
        form = MFAVerifyForm(request.POST)
        if form.is_valid():
            mfa_code = form.cleaned_data['mfa_code']
            verified = False
            
            if user.mfa_method == 'otp':
                # Verify OTP from cache using service
                from portal.services.otp_service import OTPService
                otp_service = OTPService()
                verified = otp_service.verify_otp(user.phone, mfa_code)
            elif user.mfa_method == 'authenticator':
                # Verify TOTP
                secret = user.get_encrypted_totp_secret()
                if secret:
                    verified = verify_totp(secret, mfa_code)
            
            if verified:
                del request.session['mfa_verify_user_id']
                login(request, user)
                return redirect('/dashboard/')
            else:
                messages.error(request, 'Invalid verification code.')
        else:
            messages.error(request, 'Please enter a valid code.')
        
        return render(request, self.template_name, {'form': form, 'user': user})


@login_required
def sign_out_view(request):
    """Sign out view"""
    logout(request)
    messages.success(request, 'You have been signed out successfully.')
    return redirect('/')


class DashboardView(TemplateView):
    """Dashboard view - redirects to role-specific dashboard"""
    template_name = 'portal/dashboard/base.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        user = request.user
        role_code = user.role_code.lower() if hasattr(user, 'role_code') else 'customer'
        
        # Redirect to role-specific dashboard
        dashboard_map = {
            'admin': 'admin',
            'employee': 'employee',
            'super': 'super',
            'distributor': 'distributor',
            'retailer': 'retailer',
            'customer': 'customer',
            'vendor': 'vendor',
        }
        
        dashboard_name = dashboard_map.get(role_code, 'customer')
        return redirect(f'/dashboard/{dashboard_name}/')


class AdminDashboardView(TemplateView):
    """Admin dashboard"""
    template_name = 'portal/dashboard/admin.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['pending_kyc'] = KYC.objects.filter(status='pending').count()
        context['total_wallets'] = Wallet.objects.count()
        context['active_profiles'] = Profile.objects.filter(status='active').count()
        return context


class EmployeeDashboardView(TemplateView):
    """Employee dashboard"""
    template_name = 'portal/dashboard/employee.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class SuperDashboardView(TemplateView):
    """Super dashboard"""
    template_name = 'portal/dashboard/super.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class DistributorDashboardView(TemplateView):
    """Distributor dashboard"""
    template_name = 'portal/dashboard/distributor.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class RetailerDashboardView(TemplateView):
    """Retailer dashboard"""
    template_name = 'portal/dashboard/retailer.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class CustomerDashboardView(TemplateView):
    """Customer dashboard"""
    template_name = 'portal/dashboard/customer.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class VendorDashboardView(TemplateView):
    """Vendor dashboard"""
    template_name = 'portal/dashboard/vendor.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class ProfileCreateView(CreateView):
    """Profile creation view"""
    model = Profile
    form_class = ProfileCreateForm
    template_name = 'portal/profile/create.html'
    success_url = '/dashboard/'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Profile created successfully!')
        return super().form_valid(form)


class UserListView(ListView):
    """User list view"""
    model = User
    template_name = 'portal/users/list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class UserCreateView(CreateView):
    """User creation view (Admin only)"""
    model = User
    form_class = UserCreateForm
    template_name = 'portal/users/create.html'
    success_url = '/users/'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not CanCreateUser().has_permission(self.request, self):
            messages.error(self.request, 'You do not have permission to create users.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profiles'] = Profile.objects.filter(status='active')
        return context
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Create user using create_user (username auto-generated)
                user = User.objects.create_user(
                    first_name=form.cleaned_data.get('first_name'),
                    email=form.cleaned_data.get('email'),
                    password=form.cleaned_data['password1'],
                    role_code=form.cleaned_data['role_code'],
                    profile=form.cleaned_data.get('profile'),
                    phone=form.cleaned_data.get('phone'),
                    username=form.cleaned_data.get('username') or None,  # Auto-generated if not provided
                    created_by=self.request.user,
                )
                
                # Create wallet
                Wallet.objects.get_or_create(user=user)
                
                messages.success(self.request, f'User {user.username} created successfully!')
        except Exception as e:
            messages.error(self.request, f'Error creating user: {str(e)}')
            return self.form_invalid(form)
        
        return redirect(self.success_url)


class UserDetailView(DetailView):
    """User detail view"""
    model = User
    template_name = 'portal/users/detail.html'
    context_object_name = 'user_detail'
    pk_url_kwarg = 'user_id'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class KYCSubmitView(View):
    """KYC submission view"""
    template_name = 'portal/kyc/submit.html'
    success_url = '/dashboard/'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        form = KYCSubmitForm()
        return render(request, self.template_name, {'form': form})
    
    def form_valid(self, form):
        # Create KYC instance
        kyc = KYC.objects.create(
            user=self.request.user,
            document_type=form.cleaned_data['document_type'],
            document_number=form.cleaned_data['document_number'],
            status='submitted'
        )
        
        # Handle file uploads and store in S3
        files = self.request.FILES.getlist('document_files')
        if files:
            from portal.services.storage_service import StorageService
            storage = StorageService()
            document_urls = []
            for file in files:
                url = storage.upload_kyc_document(
                    self.request.user.id,
                    form.cleaned_data['document_type'],
                    file
                )
                document_urls.append(url)
            kyc.document_files = document_urls
            kyc.save()
        
        # Update user KYC status
        self.request.user.kyc_status = 'submitted'
        self.request.user.save()
        
        messages.success(self.request, 'KYC submitted successfully! It will be reviewed soon.')
        return redirect(self.success_url)


class WalletView(TemplateView):
    """Wallet view"""
    template_name = 'portal/wallet/view.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wallet, created = Wallet.objects.get_or_create(user=self.request.user)
        context['wallet'] = wallet
        context['recent_transactions'] = WalletTransaction.objects.filter(
            wallet=wallet
        ).order_by('-created_at')[:5]
        return context


class WalletTransactionView(ListView):
    """Wallet transaction history view"""
    model = WalletTransaction
    template_name = 'portal/wallet/transactions.html'
    context_object_name = 'transactions'
    paginate_by = 20
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        context['wallet'] = wallet
        return context


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
        from django.contrib.auth.models import Permission
        from portal.utils.role_utils import get_user_permissions
        
        users = User.objects.filter(is_active=True).select_related('role')
        permissions = Permission.objects.all().select_related('content_type')
        roles = Role.objects.all().prefetch_related('default_permissions')
        
        # Get user permissions for display
        user_permissions_map = {}
        for user in users:
            user_permissions_map[user.id] = get_user_permissions(user)
        
        context = {
            'users': users,
            'permissions': permissions,
            'roles': roles,
            'user_permissions_map': user_permissions_map,
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
                        extra_data={
                            'target_user': user.username,
                            'new_role': role_code
                        }
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


# HTTP method views
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
                extra_data={
                    'target_user': user.username,
                    'new_role': role_code
                }
            )
            return JsonResponse({'success': True, 'message': 'Role changed'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'errors': form.errors})
