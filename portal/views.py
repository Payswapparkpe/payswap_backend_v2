"""
Portal Views - All views for user management, authentication, dashboards
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.views.decorators.http import require_http_methods
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from core.config import payswap_config
from portal.models import (
    User, Profile, KYC, Wallet, WalletTransaction, Role,
    ParkPeServiceConfig, ParkPePaymentGatewayConfig,
)
from portal.forms import (
    SignUpForm, SignInForm, MFASetupForm, MFAVerifyForm,
    ProfileCreateForm, UserCreateForm, KYCSubmitForm,
    PermissionAssignForm, RoleChangeForm,
    ForgotPasswordForm, PasswordResetForm, PasswordChangeForm, ProfileUpdateForm
)
from portal.utils.mfa_utils import (
    generate_totp_secret, generate_totp_uri, generate_qr_code,
    verify_totp, store_otp_in_cache, verify_otp_from_cache
)
from portal.utils.user_utils import is_mfa_required_role
from portal.permissions import CanCreateUser, CanManageKYC, CanManagePermissions
from portal.utils.logging_helper import get_logger
from portal.tasks.logging_tasks import log_user_action_task, log_security_event_task
from portal.utils.ip_utils import get_client_ip, get_user_agent, get_session_id
from portal.tasks.write_logs_task import write_logs_task
from portal.utils.user_utils import generate_username, get_role_prefix
from portal.services.otp_service import OTPService
from portal.tasks.otp_dual_delivery_task import send_otp_dual_delivery_task
from django.core.cache import cache
import uuid
from portal.utils.role_utils import (
    assign_permission_to_user, revoke_permission_from_user,
    change_user_role, assign_permission_to_role, revoke_permission_from_role
)

logger = get_logger('portal.views')


class LandingPageView(TemplateView):
    """Landing page view"""
    template_name = 'portal/landing.html'


class SignInView(View):
    """Multi-step sign in view with IP logging, rate limiting, and account lockout"""
    template_name = 'portal/auth/signin.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        
        # Check login step from session
        login_step = request.session.get('login_step', 1)
        
        # Step 1: Credentials form
        if login_step == 1:
            form = SignInForm()
            return render(request, self.template_name, {'form': form, 'step': 1})
        
        # Step 2: MFA verification (if reached)
        elif login_step == 2:
            user_id = request.session.get('login_user_id')
            if not user_id:
                return redirect('/signin/')
            try:
                user = User.objects.get(id=user_id)
                if user.requires_mfa() and user.mfa_configured:
                    return redirect('/mfa/verify/')
            except User.DoesNotExist:
                pass
        
        # Reset to step 1
        request.session['login_step'] = 1
        form = SignInForm()
        return render(request, self.template_name, {'form': form, 'step': 1})
    
    def post(self, request):
        # Extract IP and context
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        request_id = get_request_id(request)
        response_id = generate_response_id()
        
        form = SignInForm(request.POST)
        login_step = request.session.get('login_step', 1)
        
        # Step 1: Credentials Entry
        if login_step == 1:
            if form.is_valid():
                username = form.cleaned_data['username']
                password = form.cleaned_data['password']
                
                # Rate limiting: 5 attempts per 15 minutes per IP
                rate_limit_key = f"login_attempts:{client_ip}"
                attempts = cache.get(rate_limit_key, 0)
                
                if attempts >= 5:
                    write_logs_task.delay(
                        log_level='WARNING',
                        message=f'Login rate limit exceeded for IP {client_ip}',
                        module_name='portal.views.SignInView',
                        url=request.path,
                        request_id=request_id,
                        response_id=response_id,
                        user_id=None,
                        extra_data={'action': 'login_rate_limit', 'ip': client_ip},
                        client_ip=client_ip,
                        user_agent=user_agent,
                        session_id=session_id
                    )
                    messages.error(request, 'Too many login attempts. Please try again in 15 minutes.')
                    return render(request, self.template_name, {'form': form, 'step': 1})
                
                # Authenticate user
                user = authenticate(request, username=username, password=password)
                
                if user:
                    # Check if account is locked
                    if user.is_account_locked():
                        write_logs_task.delay(
                            log_level='WARNING',
                            message=f'Login attempt with locked account: {user.username}',
                            module_name='portal.views.SignInView',
                            url=request.path,
                            request_id=request_id,
                            response_id=response_id,
                            user_id=user.id,
                            extra_data={'action': 'login_locked_account', 'ip': client_ip},
                            client_ip=client_ip,
                            user_agent=user_agent,
                            session_id=session_id
                        )
                        messages.error(request, 'Your account is temporarily locked due to multiple failed login attempts. Please try again later.')
                        return render(request, self.template_name, {'form': form, 'step': 1})
                    
                    # Reset failed attempts on successful authentication
                    user.reset_failed_attempts()
                    
                    # Step 2: Account Verification
                    if not user.is_active:
                        write_logs_task.delay(
                            log_level='WARNING',
                            message=f'Login attempt with inactive account: {user.username}',
                            module_name='portal.views.SignInView',
                            url=request.path,
                            request_id=request_id,
                            response_id=response_id,
                            user_id=user.id,
                            extra_data={'action': 'login_inactive', 'ip': client_ip},
                            client_ip=client_ip,
                            user_agent=user_agent,
                            session_id=session_id
                        )
                        messages.error(request, 'Your account is inactive.')
                        return render(request, self.template_name, {'form': form, 'step': 1})
                    
                    if not user.email_verified:
                        write_logs_task.delay(
                            log_level='WARNING',
                            message=f'Login attempt with unverified email: {user.username}',
                            module_name='portal.views.SignInView',
                            url=request.path,
                            request_id=request_id,
                            response_id=response_id,
                            user_id=user.id,
                            extra_data={'action': 'login_unverified_email', 'ip': client_ip},
                            client_ip=client_ip,
                            user_agent=user_agent,
                            session_id=session_id
                        )
                        messages.error(request, 'Please verify your email before signing in.')
                        return render(request, self.template_name, {'form': form, 'step': 1})
                    
                    # Step 3: Profile Completion Check
                    if hasattr(user, 'profile') and user.profile.profile_completion_required:
                        # Store user ID and proceed to login (middleware will redirect)
                        request.session['login_user_id'] = user.id
                        request.session['login_step'] = 2
                        login(request, user)
                        
                        write_logs_task.delay(
                            log_level='INFO',
                            message=f'User logged in, profile completion required: {user.username}',
                            module_name='portal.views.SignInView',
                            url=request.path,
                            request_id=request_id,
                            response_id=response_id,
                            user_id=user.id,
                            extra_data={'action': 'login_profile_completion_required', 'ip': client_ip},
                            client_ip=client_ip,
                            user_agent=user_agent,
                            session_id=session_id
                        )
                        
                        # Update login tracking
                        user.last_login_ip = client_ip
                        user.last_login_user_agent = user_agent
                        user.login_count += 1
                        user.save(update_fields=['last_login_ip', 'last_login_user_agent', 'login_count'])
                        
                        messages.info(request, 'Please complete your profile to continue.')
                        return redirect('/profile/complete/')
                    
                    # Step 4: MFA Check
                    if user.requires_mfa():
                        if not user.mfa_configured:
                            # Store user ID in session for MFA setup
                            request.session['mfa_setup_user_id'] = user.id
                            request.session['login_user_id'] = user.id
                            request.session['login_step'] = 2
                            
                            write_logs_task.delay(
                                log_level='INFO',
                                message=f'MFA setup required for user: {user.username}',
                                module_name='portal.views.SignInView',
                                url=request.path,
                                request_id=request_id,
                                response_id=response_id,
                                user_id=user.id,
                                extra_data={'action': 'mfa_setup_required', 'ip': client_ip},
                                client_ip=client_ip,
                                user_agent=user_agent,
                                session_id=session_id
                            )
                            
                            messages.info(request, 'MFA setup is required for your role.')
                            return redirect('/mfa/setup/')
                        else:
                            # Store user ID in session for MFA verification
                            request.session['mfa_verify_user_id'] = user.id
                            request.session['login_user_id'] = user.id
                            request.session['login_step'] = 2
                            
                            write_logs_task.delay(
                                log_level='INFO',
                                message=f'MFA verification required for user: {user.username}',
                                module_name='portal.views.SignInView',
                                url=request.path,
                                request_id=request_id,
                                response_id=response_id,
                                user_id=user.id,
                                extra_data={'action': 'mfa_verification_required', 'ip': client_ip},
                                client_ip=client_ip,
                                user_agent=user_agent,
                                session_id=session_id
                            )
                            
                            return redirect('/mfa/verify/')
                    
                    # Step 5: Complete Login
                    login(request, user)
                    
                    # Update login tracking
                    user.last_login_ip = client_ip
                    user.last_login_user_agent = user_agent
                    user.login_count += 1
                    user.save(update_fields=['last_login_ip', 'last_login_user_agent', 'login_count'])
                    
                    # Clear login step from session
                    request.session.pop('login_step', None)
                    request.session.pop('login_user_id', None)
                    
                    # Log successful login
                    write_logs_task.delay(
                        log_level='INFO',
                        message=f'User logged in successfully: {user.username}',
                        module_name='portal.views.SignInView',
                        url=request.path,
                        request_id=request_id,
                        response_id=response_id,
                        user_id=user.id,
                        extra_data={
                            'action': 'login_success',
                            'ip': client_ip,
                            'role': user.role_code
                        },
                        client_ip=client_ip,
                        user_agent=user_agent,
                        session_id=session_id
                    )
                    
                    log_user_action_task.delay(
                        action='login',
                        user_id=user.id,
                        status='success',
                        request_id=request_id
                    )
                    
                    return redirect('/dashboard/')
                else:
                    # Invalid credentials - increment failed attempts for username if found
                    try:
                        user = User.objects.get(username=username)
                        was_locked = user.increment_failed_attempts()
                        
                        if was_locked:
                            write_logs_task.delay(
                                log_level='WARNING',
                                message=f'Account locked due to failed login attempts: {username}',
                                module_name='portal.views.SignInView',
                                url=request.path,
                                request_id=request_id,
                                response_id=response_id,
                                user_id=user.id,
                                extra_data={
                                    'action': 'account_locked',
                                    'ip': client_ip,
                                    'failed_attempts': user.failed_login_attempts
                                },
                                client_ip=client_ip,
                                user_agent=user_agent,
                                session_id=session_id
                            )
                    except User.DoesNotExist:
                        pass
                    
                    # Increment rate limit
                    cache.set(rate_limit_key, attempts + 1, timeout=900)  # 15 minutes
                    
                    write_logs_task.delay(
                        log_level='WARNING',
                        message=f'Invalid login credentials for username: {username}',
                        module_name='portal.views.SignInView',
                        url=request.path,
                        request_id=request_id,
                        response_id=response_id,
                        user_id=None,
                        extra_data={
                            'action': 'login_failed',
                            'ip': client_ip,
                            'username': username
                        },
                        client_ip=client_ip,
                        user_agent=user_agent,
                        session_id=session_id
                    )
                    
                    messages.error(request, 'Invalid username or password.')
            else:
                messages.error(request, 'Please correct the errors below.')
        
        return render(request, self.template_name, {'form': form, 'step': login_step})


class SignUpView(View):
    """Multi-step sign up view with OTP dual delivery (email + SMS)"""
    template_name = 'portal/auth/signup.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        
        # Check signup step from session
        signup_step = request.session.get('signup_step', 1)
        
        # Step 1: Basic information form
        if signup_step == 1:
            form = SignUpForm()
            return render(request, self.template_name, {'form': form, 'step': 1})
        
        # Step 2: OTP verification
        elif signup_step == 2:
            from portal.forms import OTPVerifyForm
            otp_form = OTPVerifyForm()
            signup_data = request.session.get('signup_data', {})
            return render(request, self.template_name, {
                'otp_form': otp_form,
                'step': 2,
                'email': signup_data.get('email', ''),
                'phone': signup_data.get('phone', '')
            })
        
        # Reset to step 1
        request.session['signup_step'] = 1
        form = SignUpForm()
        return render(request, self.template_name, {'form': form, 'step': 1})
    
    def post(self, request):
        # Extract IP and context
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        request_id = get_request_id(request)
        response_id = generate_response_id()
        
        signup_step = request.session.get('signup_step', 1)
        
        # Step 1: Basic Information
        if signup_step == 1:
            form = SignUpForm(request.POST)
            if form.is_valid():
                # Store form data in session
                request.session['signup_data'] = {
                    'first_name': form.cleaned_data['first_name'],
                    'email': form.cleaned_data['email'],
                    'phone': form.cleaned_data['phone'],
                    'password1': form.cleaned_data['password1'],
                    'role_code': form.cleaned_data['role_code']
                }
                request.session['signup_step'] = 2
                
                # Log signup attempt
                write_logs_task.delay(
                    log_level='INFO',
                    message=f'Signup step 1 completed: {form.cleaned_data["email"]}',
                    module_name='portal.views.SignUpView',
                    url=request.path,
                    request_id=request_id,
                    response_id=response_id,
                    user_id=None,
                    extra_data={
                        'action': 'signup_step1',
                        'email': form.cleaned_data['email'][:2] + '***',
                        'phone': form.cleaned_data['phone'][:4] + '****',
                        'role': form.cleaned_data['role_code']
                    },
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                
                # Generate and send OTP to both email and SMS
                otp_service = OTPService()
                otp_code = otp_service.generate_otp()
                
                # Store OTP in cache for both email and phone
                from portal.utils.mfa_utils import store_otp_in_cache
                from portal.utils.phone_utils import normalize_phone_number
                
                normalized_phone = normalize_phone_number(form.cleaned_data['phone'])
                store_otp_in_cache(normalized_phone, otp_code, 300)  # 5 minutes
                store_otp_in_cache(form.cleaned_data['email'], otp_code, 300)  # Also store by email
                
                # Send OTP to both channels simultaneously
                send_otp_dual_delivery_task.delay(
                    otp_code=otp_code,
                    email=form.cleaned_data['email'],
                    phone_number=normalized_phone,
                    user_id=None,
                    context={'signup': True},
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                
                # Store OTP in session for verification
                request.session['signup_otp'] = otp_code
                request.session['signup_otp_expires'] = timezone.now().timestamp() + 300
                
                write_logs_task.delay(
                    log_level='INFO',
                    message=f'OTP sent to email and SMS for signup',
                    module_name='portal.views.SignUpView',
                    url=request.path,
                    request_id=request_id,
                    response_id=response_id,
                    user_id=None,
                    extra_data={
                        'action': 'otp_sent_dual',
                        'email': form.cleaned_data['email'][:2] + '***',
                        'phone': normalized_phone[:4] + '****'
                    },
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                
                messages.info(request, 'Verification code sent to your email and mobile number. Please check both.')
                return redirect('/signup/otp/')
            else:
                messages.error(request, 'Please correct the errors below.')
                return render(request, self.template_name, {'form': form, 'step': 1})
        
        # Step 2: OTP Verification
        elif signup_step == 2:
            from portal.forms import OTPVerifyForm
            from portal.utils.phone_utils import normalize_phone_number
            from portal.utils.mfa_utils import verify_otp_from_cache
            
            otp_form = OTPVerifyForm(request.POST)
            signup_data = request.session.get('signup_data', {})
            
            if otp_form.is_valid():
                otp_code = otp_form.cleaned_data['otp_code']
                email = signup_data.get('email')
                phone = signup_data.get('phone')
                
                # Verify OTP from either email or phone
                normalized_phone = normalize_phone_number(phone)
                otp_valid = (
                    verify_otp_from_cache(normalized_phone, otp_code) or
                    verify_otp_from_cache(email, otp_code)
                )
                
                if otp_valid:
                    # Step 3: Create Account
                    try:
                        with transaction.atomic():
                            # Create user
                            user = User.objects.create_user(
                                password=signup_data['password1'],
                                role_code=signup_data['role_code'],
                            )
                            
                            # Create profile
                            profile = Profile.objects.create(
                                user=user,
                                first_name=signup_data['first_name'],
                                email=email,
                                phone=normalized_phone,
                                type='individual',
                                email_verified=True,  # Verified via OTP
                                phone_verified=True,  # Verified via OTP
                                profile_completion_required=False  # User provided all data
                            )
                            
                            # Update user email_verified status
                            user.email_verified = True
                            user.save()
                            
                            # Create wallet
                            Wallet.objects.create(user=user)
                            
                            # Clear signup session data
                            request.session.pop('signup_step', None)
                            request.session.pop('signup_data', None)
                            request.session.pop('signup_otp', None)
                            request.session.pop('signup_otp_expires', None)
                            
                            # Log successful signup
                            write_logs_task.delay(
                                log_level='INFO',
                                message=f'User signed up successfully: {user.username}',
                                module_name='portal.views.SignUpView',
                                url=request.path,
                                request_id=request_id,
                                response_id=response_id,
                                user_id=user.id,
                                extra_data={
                                    'action': 'signup_success',
                                    'role': signup_data['role_code'],
                                    'ip': client_ip
                                },
                                client_ip=client_ip,
                                user_agent=user_agent,
                                session_id=session_id
                            )
                            
                            log_user_action_task.delay(
                                action='signup',
                                user_id=user.id,
                                resource='user',
                                resource_id=str(user.id),
                                status='success',
                                extra_data={'role': signup_data['role_code']},
                                request_id=request_id
                            )
                            
                            messages.success(request, 'Account created successfully! Please sign in.')
                            return redirect('/signin/')
                    except Exception as e:
                        write_logs_task.delay(
                            log_level='ERROR',
                            message=f'Error creating account: {str(e)}',
                            module_name='portal.views.SignUpView',
                            url=request.path,
                            request_id=request_id,
                            response_id=response_id,
                            user_id=None,
                            extra_data={'action': 'signup_error', 'error': str(e)},
                            client_ip=client_ip,
                            user_agent=user_agent,
                            session_id=session_id
                        )
                        messages.error(request, f'Error creating account: {str(e)}')
                else:
                    write_logs_task.delay(
                        log_level='WARNING',
                        message=f'Invalid OTP during signup',
                        module_name='portal.views.SignUpView',
                        url=request.path,
                        request_id=request_id,
                        response_id=response_id,
                        user_id=None,
                        extra_data={'action': 'otp_verification_failed', 'ip': client_ip},
                        client_ip=client_ip,
                        user_agent=user_agent,
                        session_id=session_id
                    )
                    messages.error(request, 'Invalid verification code. Please try again.')
            
            return render(request, self.template_name, {
                'otp_form': otp_form,
                'step': 2,
                'email': email,
                'phone': phone
            })
        
        return redirect('/signup/')


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
                
                # Send OTP via unified notification service
                from portal.services.otp_service import OTPService
                otp_service = OTPService()
                success, message = otp_service.send_otp(phone, user_id=user.id, async_send=True)
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
            
            # Get method from form or use user's configured method
            method = request.POST.get('method', user.mfa_method)
            
            if method == 'otp' or user.mfa_method == 'otp':
                # Verify OTP from cache using service
                from portal.services.otp_service import OTPService
                otp_service = OTPService()
                verified = otp_service.verify_otp(user.phone, mfa_code)
            elif method == 'authenticator' or user.mfa_method == 'authenticator':
                # Verify TOTP
                secret = user.get_encrypted_totp_secret()
                if secret:
                    verified = verify_totp(secret, mfa_code)
                else:
                    verified = False
            
            if verified:
                del request.session['mfa_verify_user_id']
                login(request, user)
                return redirect('/dashboard/')
            else:
                messages.error(request, 'Invalid verification code.')
        else:
            messages.error(request, 'Please enter a valid code.')
        
        return render(request, self.template_name, {'form': form, 'user': user})


@require_http_methods(["POST"])
def resend_otp_view(request):
    """Resend OTP view"""
    from django.http import JsonResponse
    from portal.services.otp_service import OTPService
    
    user_id = request.session.get('mfa_verify_user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'Invalid session. Please sign in again.'}, status=400)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)
    
    if not user.phone:
        return JsonResponse({'success': False, 'message': 'Phone number not found.'}, status=400)
    
    # Send OTP via unified notification service
    otp_service = OTPService()
    success, message = otp_service.send_otp(user.phone, user_id=user.id, async_send=True)
    
    if success:
        log_user_action_task.delay(
            action='resend_otp',
            user_id=user.id,
            status='success'
        )
        return JsonResponse({'success': True, 'message': 'OTP has been resent to your mobile number.'})
    else:
        log_security_event_task.delay(
            event_type='otp_resend_failed',
            message=f'Failed to resend OTP: {message}',
            user_id=user.id,
            severity='low'
        )
        return JsonResponse({'success': False, 'message': message}, status=400)


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


class ParkPeAppManagementView(TemplateView):
    """ParkPe App Management: Voucher Management & Payment Gateway Management cards."""
    template_name = 'portal/parkpe/app_management.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        if not request.user.is_staff and getattr(request.user, 'role_code', None) not in ('super', 'admin'):
            raise Http404
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['service_configs'] = ParkPeServiceConfig.objects.all().order_by('service_code')
        context['gateway_configs'] = ParkPePaymentGatewayConfig.objects.all().order_by('gateway', 'service_code')
        from django.urls import reverse
        context['admin_service_config_url'] = reverse('admin:portal_parkpeserviceconfig_changelist')
        context['admin_gateway_config_url'] = reverse('admin:portal_parkpepaymentgatewayconfig_changelist')
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
        # Profiles are now OneToOne with User, so no need to list them
        return context
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Create user first (username will be auto-generated)
                username = form.cleaned_data.get('username') or None
                user = User.objects.create_user(
                    username=username,
                    password=form.cleaned_data['password1'],
                    role_code=form.cleaned_data['role_code'],
                    created_by=self.request.user,
                )
                
                # Create profile (mandatory, OneToOne with user)
                profile = Profile.objects.create(
                    user=user,
                    first_name=form.cleaned_data.get('first_name'),
                    email=form.cleaned_data.get('email'),
                    phone=form.cleaned_data.get('phone'),
                    type='individual',
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


class ForgotPasswordView(View):
    """Forgot password view - request password reset"""
    template_name = 'portal/auth/forgot_password.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        form = ForgotPasswordForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                profile = Profile.objects.get(email=email)
                user = profile.user
                
                if not user.is_active:
                    messages.error(request, 'This account is inactive. Please contact support.')
                    return render(request, self.template_name, {'form': form})
                
                # Generate password reset token
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Create reset URL
                reset_url = request.build_absolute_uri(f'/password/reset/{uid}/{token}/')
                
                # Send password reset email via unified notification service
                try:
                    from portal.services.notification_service_v2 import NotificationServiceV2
                    notification_service = NotificationServiceV2()
                    result = notification_service.send_email(
                        to_email=email,
                        subject='Password Reset Request - Payswap',
                        template_name='portal/emails/password_reset.html',
                        context={
                            'user': user,
                            'reset_url': reset_url,
                            'expiry_hours': 1
                        },
                        user_id=user.id,
                        async_send=True
                    )
                except Exception as e:
                    logger.error(f'Failed to send password reset email: {str(e)}')
                    # Continue anyway - don't reveal if email exists
                
                log_security_event_task.delay(
                    event_type='password_reset_requested',
                    message='Password reset requested',
                    user_id=user.id,
                    severity='low',
                    extra_data={'email': email}
                )
                
                # Always show success message (security: don't reveal if email exists)
                messages.success(request, 'If an account exists with this email, a password reset link has been sent.')
                return redirect('/signin/')
            except Profile.DoesNotExist:
                # Don't reveal if email exists
                messages.success(request, 'If an account exists with this email, a password reset link has been sent.')
                return redirect('/signin/')
        
        return render(request, self.template_name, {'form': form})


class PasswordResetView(View):
    """Password reset view with token and IP logging"""
    template_name = 'portal/auth/password_reset.html'
    
    def get(self, request, uidb64, token):
        # Extract IP and context
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        request_id = get_request_id(request)
        response_id = generate_response_id()
        
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        
        if user is None or not default_token_generator.check_token(user, token):
            write_logs_task.delay(
                log_level='WARNING',
                message=f'Invalid or expired password reset link accessed',
                module_name='portal.views.PasswordResetView',
                url=request.path,
                request_id=request_id,
                response_id=response_id,
                user_id=None,
                extra_data={'action': 'password_reset_invalid_token', 'ip': client_ip},
                client_ip=client_ip,
                user_agent=user_agent,
                session_id=session_id
            )
            messages.error(request, 'Invalid or expired password reset link.')
            return redirect('/forgot-password/')
        
        form = PasswordResetForm()
        return render(request, self.template_name, {
            'form': form,
            'uidb64': uidb64,
            'token': token,
            'validlink': True
        })
    
    def post(self, request, uidb64, token):
        # Extract IP and context
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        request_id = get_request_id(request)
        response_id = generate_response_id()
        
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        
        if user is None or not default_token_generator.check_token(user, token):
            write_logs_task.delay(
                log_level='WARNING',
                message=f'Invalid password reset token in POST',
                module_name='portal.views.PasswordResetView',
                url=request.path,
                request_id=request_id,
                response_id=response_id,
                user_id=None,
                extra_data={'action': 'password_reset_invalid_token_post', 'ip': client_ip},
                client_ip=client_ip,
                user_agent=user_agent,
                session_id=session_id
            )
            messages.error(request, 'Invalid or expired password reset link.')
            return redirect('/forgot-password/')
        
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            # Set new password
            user.set_password(form.cleaned_data['password1'])
            user.save()
            
            # Update profile last_password_change
            if hasattr(user, 'profile') and user.profile:
                user.profile.last_password_change = timezone.now()
                user.profile.save()
            
            write_logs_task.delay(
                log_level='INFO',
                message=f'Password reset completed: {user.username}',
                module_name='portal.views.PasswordResetView',
                url=request.path,
                request_id=request_id,
                response_id=response_id,
                user_id=user.id,
                extra_data={'action': 'password_reset_completed', 'ip': client_ip},
                client_ip=client_ip,
                user_agent=user_agent,
                session_id=session_id
            )
            
            log_security_event_task.delay(
                event_type='password_reset_completed',
                message='Password reset completed',
                user_id=user.id,
                severity='medium',
                request_id=request_id
            )
            
            messages.success(request, 'Your password has been reset successfully. Please sign in with your new password.')
            return redirect('/signin/')
        
        return render(request, self.template_name, {
            'form': form,
            'uidb64': uidb64,
            'token': token,
            'validlink': True
        })


class PasswordChangeView(View):
    """Password change view for logged-in users"""
    template_name = 'portal/auth/password_change.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        form = PasswordChangeForm(user=request.user)
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        # Extract IP and context
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        request_id = get_request_id(request)
        response_id = generate_response_id()
        
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            # Change password
            request.user.set_password(form.cleaned_data['new_password1'])
            request.user.save()
            
            # Update profile last_password_change
            if hasattr(request.user, 'profile') and request.user.profile:
                request.user.profile.last_password_change = timezone.now()
                request.user.profile.save()
            
            write_logs_task.delay(
                log_level='INFO',
                message=f'Password changed: {request.user.username}',
                module_name='portal.views.PasswordChangeView',
                url=request.path,
                request_id=request_id,
                response_id=response_id,
                user_id=request.user.id,
                extra_data={'action': 'password_changed', 'ip': client_ip},
                client_ip=client_ip,
                user_agent=user_agent,
                session_id=session_id
            )
            
            log_user_action_task.delay(
                action='password_change',
                user_id=request.user.id,
                resource='user',
                resource_id=str(request.user.id),
                status='success',
                request_id=request_id
            )
            
            messages.success(request, 'Your password has been changed successfully.')
            return redirect('/profile/')
        
        return render(request, self.template_name, {'form': form})


class ProfileView(DetailView):
    """Profile view for logged-in users"""
    model = Profile
    template_name = 'portal/profile/view.html'
    context_object_name = 'profile'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_object(self):
        """Get current user's profile"""
        if not hasattr(self.request.user, 'profile'):
            messages.error(self.request, 'Profile not found. Please create your profile.')
            return redirect('/profile/create/')
        return self.request.user.profile


class ProfileUpdateView(UpdateView):
    """Profile update view"""
    model = Profile
    form_class = ProfileUpdateForm
    template_name = 'portal/profile/update.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_object(self):
        """Get current user's profile"""
        if not hasattr(self.request.user, 'profile'):
            messages.error(self.request, 'Profile not found. Please create your profile.')
            return redirect('/profile/create/')
        return self.request.user.profile
    
    def form_valid(self, form):
        form.instance.last_updated_by = self.request.user
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return '/profile/'


class SettingsView(TemplateView):
    """Settings view for logged-in users"""
    template_name = 'portal/settings.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.request.user.profile if hasattr(self.request.user, 'profile') else None
        context['user'] = self.request.user
        return context


class ProfileCompletionView(View):
    """Profile completion view for social signup users"""
    template_name = 'portal/profile/complete.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        # Check if profile completion is actually required
        if not hasattr(request.user, 'profile') or not request.user.profile:
            messages.error(request, 'Profile not found.')
            return redirect('/profile/create/')
        
        if not request.user.profile.profile_completion_required:
            messages.info(request, 'Your profile is already complete.')
            return redirect('/dashboard/')
        
        from portal.forms import ProfileCompletionForm
        form = ProfileCompletionForm()
        form.user = request.user  # Attach user for validation
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        from portal.forms import ProfileCompletionForm
        
        form = ProfileCompletionForm(request.POST)
        form.user = request.user  # Attach user for validation
        
        if form.is_valid():
            # Extract IP and session info
            client_ip = get_client_ip(request)
            user_agent = get_user_agent(request)
            session_id = get_session_id(request)
            request_id = str(uuid.uuid4())
            response_id = str(uuid.uuid4())
            
            try:
                with transaction.atomic():
                    profile = request.user.profile
                    
                    # Update required fields
                    profile.phone = form.cleaned_data['phone']
                    profile.address_line_1 = form.cleaned_data['address_line_1']
                    profile.address_line_2 = form.cleaned_data.get('address_line_2', '')
                    profile.city = form.cleaned_data['city']
                    profile.state = form.cleaned_data['state']
                    profile.pincode = form.cleaned_data['pincode']
                    
                    if form.cleaned_data.get('date_of_birth'):
                        profile.date_of_birth = form.cleaned_data['date_of_birth']
                    
                    # Mark profile as complete
                    profile.profile_completion_required = False
                    profile.phone_verified = True  # Auto-verify phone after completion
                    profile.save()
                    
                    # Log profile completion
                    write_logs_task.delay(
                        log_level='INFO',
                        message=f'Profile completed by user {request.user.username}',
                        module_name='portal.views.ProfileCompletionView',
                        url=request.path,
                        request_id=request_id,
                        response_id=response_id,
                        user_id=request.user.id,
                        extra_data={
                            'action': 'profile_completed',
                            'profile_id': profile.id
                        },
                        client_ip=client_ip,
                        user_agent=user_agent,
                        session_id=session_id
                    )
                    
                    log_user_action_task.delay(
                        action='complete_profile',
                        user_id=request.user.id,
                        resource='profile',
                        resource_id=str(profile.id),
                        status='success',
                        request_id=request_id
                    )
                
                messages.success(request, 'Profile completed successfully! You can now access all features.')
                return redirect('/dashboard/')
                
            except Exception as e:
                write_logs_task.delay(
                    log_level='ERROR',
                    message=f'Error completing profile: {str(e)}',
                    module_name='portal.views.ProfileCompletionView',
                    url=request.path,
                    request_id=request_id,
                    response_id=response_id,
                    user_id=request.user.id,
                    extra_data={'action': 'profile_completion_error', 'error': str(e)},
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                messages.error(request, 'An error occurred while completing your profile. Please try again.')
        
        return render(request, self.template_name, {'form': form})


def social_callback_view(request):
    """
    Handle social authentication callback
    Creates user with role=customer if new, links account if existing
    """
    from allauth.socialaccount.models import SocialAccount
    from allauth.socialaccount import app_settings
    
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    session_id = get_session_id(request)
    request_id = str(uuid.uuid4())
    response_id = str(uuid.uuid4())
    
    # Log social auth attempt
    write_logs_task.delay(
        log_level='INFO',
        message=f'Social authentication callback received',
        module_name='portal.views.social_callback_view',
        url=request.path,
        request_id=request_id,
        response_id=response_id,
        user_id=None,
        extra_data={
            'action': 'social_auth_callback',
            'provider': request.GET.get('provider', 'unknown')
        },
        client_ip=client_ip,
        user_agent=user_agent,
        session_id=session_id
    )
    
    # Get social account from allauth
    try:
        social_account = SocialAccount.objects.get(
            provider=request.GET.get('provider', ''),
            uid=request.GET.get('uid', '')
        )
    except SocialAccount.DoesNotExist:
        # New social signup - handle in allauth adapter
        # Redirect to allauth's signup flow
        from allauth.account.views import SignupView
        return SignupView.as_view()(request)
    
    # If we reach here, social account exists
    # Check if user exists
    if social_account.user:
        # Existing user - proceed to login
        user = social_account.user
        login(request, user)
        
        # Update login tracking
        user.last_login_ip = client_ip
        user.last_login_user_agent = user_agent
        user.login_count += 1
        user.reset_failed_attempts()
        user.save(update_fields=['last_login_ip', 'last_login_user_agent', 'login_count', 'failed_login_attempts'])
        
        # Log successful login
        write_logs_task.delay(
            log_level='INFO',
            message=f'Social login successful for user {user.username}',
            module_name='portal.views.social_callback_view',
            url=request.path,
            request_id=request_id,
            response_id=response_id,
            user_id=user.id,
            extra_data={
                'action': 'social_login_success',
                'provider': social_account.provider
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        
        # Check profile completion
        if hasattr(user, 'profile') and user.profile.profile_completion_required:
            messages.info(request, 'Please complete your profile to continue.')
            return redirect('/profile/complete/')
        
        # Redirect to dashboard
        return redirect('/dashboard/')
    
    return redirect('/signin/')


# ---------------------------------------------------------------------------
# API Management (Registry + Logs) - Admin only
# ---------------------------------------------------------------------------

def _is_api_registry_admin(user):
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role_code", "").lower() in ("admin", "super")


class APIRegistryListView(ListView):
    """List all APIs in the registry with status toggle. Admin/Super only."""
    template_name = "portal/api_registry/list.html"
    context_object_name = "apis"
    paginate_by = 25

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_api_registry_admin(request.user):
            messages.error(request, "Access denied. Admin or Super role required.")
            return redirect("/dashboard/admin/")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        from api_management.models import APIRegistry
        qs = APIRegistry.objects.select_related("service_category").order_by("version", "module_name", "api_name")
        version = self.request.GET.get("version")
        status_filter = self.request.GET.get("status")
        if version:
            qs = qs.filter(version=version)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class APIRegistryToggleView(View):
    """POST to toggle API status ON/OFF. Admin/Super only."""

    @method_decorator(login_required)
    @method_decorator(require_http_methods(["POST"]))
    def dispatch(self, request, *args, **kwargs):
        if not _is_api_registry_admin(request.user):
            return JsonResponse({"success": False, "message": "Access denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        from api_management.models import APIRegistry
        api = get_object_or_404(APIRegistry, pk=pk)
        api.status = APIRegistry.STATUS_OFF if api.status == APIRegistry.STATUS_ON else APIRegistry.STATUS_ON
        api.updated_by = request.user
        api.save()
        messages.success(request, f"API {api.api_name} is now {api.status}.")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True, "status": api.status})
        return redirect("api_registry_list")


class APILogListView(ListView):
    """List API logs with filters. Admin/Super only."""
    template_name = "portal/api_registry/log_list.html"
    context_object_name = "logs"
    paginate_by = 50

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_api_registry_admin(request.user):
            messages.error(request, "Access denied. Admin or Super role required.")
            return redirect("/dashboard/admin/")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        from api_management.models import APILog
        qs = APILog.objects.select_related("api_registry", "user").order_by("-created_at")
        status_code = self.request.GET.get("status_code")
        request_id = self.request.GET.get("request_id")
        if status_code:
            qs = qs.filter(status_code=status_code)
        if request_id:
            qs = qs.filter(request_id__icontains=request_id)
        return qs


# SocialSignupAdapter is now in portal/adapters.py
