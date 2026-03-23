"""
Portal Views - All views for user management, authentication, dashboards
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, logout, authenticate, get_backends
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.hashers import make_password, check_password
from django.core.signing import Signer
import json
import time
from urllib.parse import quote
from django.contrib.auth.tokens import default_token_generator
from django.views.decorators.http import require_http_methods
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.db import transaction, models
from django.db.models import Q
from django.utils import timezone
from django.core.mail import send_mail
from django.templatetags.static import static
from core.config import payswap_config
from decimal import Decimal
from portal.models import (
    User, Profile, KYC, Wallet, WalletTransaction, Role, LogEntry, CashfreeAPILog,
    Department, Agent, Ticket, TicketNote, TicketAttachment, TicketAssignmentHistory,
    Service, ApiVendor, VendorApi, GiftVoucherBrand, GiftVoucher, GiftVoucherTransaction, BulkVoucherIssuanceBatch,
    VoucherClient, ResellerPartner, APIKey, APIKeyUsageLog,
    Vehicle, ConnectThread, ConnectMessage, ConnectCallLog, ConnectReport,
)
from portal.forms import (
    SignUpForm, SignInForm, MFASetupForm, MFAVerifyForm,
    SetPinForm, UnlockPinForm,
    ProfileCreateForm, UserCreateForm, KYCSubmitForm,
    PermissionAssignForm, RoleChangeForm,
    ForgotPasswordForm, PasswordResetForm, PasswordChangeForm, ProfileUpdateForm,
    BrandOnboardingStep1Form, BrandOnboardingStep2Form, BrandOnboardingStep3Form,
    BrandOnboardingStep4Form, BrandOnboardingStep5Form, BrandOnboardingReviewForm,
    BrandOnboardingAdminApprovalForm, BrandAdminOnboardingForm,
)
from portal.utils.mfa_utils import (
    generate_totp_secret, generate_totp_uri, generate_qr_code,
    verify_totp, store_otp_in_cache, verify_otp_from_cache
)
from portal.utils.user_utils import is_mfa_required_role
from portal.permissions import (
    CanCreateUser, CanManageKYC, CanManagePermissions,
    CanAccessVoucherX, CanManageVoucherXBrands, CanIssueVouchers, CanReviewBrandOnboarding
)
import logging
from portal.utils.logging_helper import get_logger
from portal.utils.logging_utils import get_request_id, generate_response_id

# Console logger for voucher flow (shows in runserver terminal; SecureLogger goes to task/file)
voucher_console_log = logging.getLogger('portal.voucher')
from portal.tasks.logging_tasks import log_user_action_task, log_security_event_task
from portal.utils.ip_utils import get_client_ip, get_user_agent, get_session_id
from portal.tasks.write_logs_task import write_logs_task
import traceback
from portal.utils.voucher_logging import log_voucher_operation
from portal.utils.user_utils import generate_username, get_role_prefix
from portal.services.otp_service import OTPService
from portal.tasks.otp_dual_delivery_task import send_otp_dual_delivery_task
from django.core.cache import cache
import uuid
from portal.utils.role_utils import (
    assign_permission_to_user, revoke_permission_from_user,
    change_user_role, assign_permission_to_role, revoke_permission_from_role,
    get_user_permissions,
)
from portal.decorators import log_view_action, log_form_submission
from portal.utils.pin_audit import (
    log_pin_set,
    log_pin_unlock_success,
    log_pin_unlock_failure,
    log_pin_lockout,
    log_forced_otp_reauth,
)
from portal.utils.session_lock import (
    get_user_from_lock_cookie,
    LOCK_IDENTITY_COOKIE_NAME,
    PIN_UNLOCK_WINDOW_SECONDS,
)

logger = get_logger('portal.views')

# Session lock / PIN unlock (secondary only; OTP/2FA is primary)
LOCK_IDENTITY_COOKIE_MAX_AGE = 24 * 3600  # 24 hours (seconds)
PIN_MAX_ATTEMPTS = 5
PIN_LOCK_DURATION_MINUTES = 30
PIN_UNLOCK_PAGE_TIMEOUT_SECONDS = 30 * 60  # 30 min on unlock screen; then redirect to signin
LOCK_STARTED_AT_COOKIE_NAME = 'lock_started_at'


class LandingPageView(TemplateView):
    """Landing page view"""
    template_name = 'portal/landing.html'


class SignInView(View):
    """Multi-step sign in view with IP logging, rate limiting, and account lockout"""
    template_name = 'portal/auth/signin.html'
    
    @method_decorator(log_view_action(action='view_signin', resource='auth'))
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        
        # Check if user wants to clear MFA session (from back button)
        if request.GET.get('clear_mfa') == '1' or request.META.get('HTTP_X_CLEAR_MFA_SESSION'):
            # Clear all MFA-related session variables
            request.session.pop('mfa_verify_user_id', None)
            request.session.pop('mfa_setup_user_id', None)
            request.session.pop('login_step', None)
            request.session.pop('login_user_id', None)
            messages.info(request, 'Please sign in again.')
        
        # Check login step from session
        login_step = request.session.get('login_step', 1)
        
        # Step 1: Credentials form (PIN unlock is shown only via middleware redirect, not from signin)
        if login_step == 1:
            form = SignInForm()
            return render(request, self.template_name, {'form': form, 'step': 1})
        
        # Step 2: MFA verification (if reached)
        elif login_step == 2:
            user_id = request.session.get('login_user_id')
            mfa_verify_user_id = request.session.get('mfa_verify_user_id')
            if not user_id:
                # Clear invalid session state
                request.session.pop('login_step', None)
                request.session.pop('mfa_verify_user_id', None)
                return redirect('/signin/')
            try:
                user = User.objects.get(id=user_id)
                # Only redirect to MFA verify if both conditions are met:
                # 1. User requires MFA and has it configured
                # 2. The mfa_verify_user_id is set in session (from login flow)
                if user.requires_mfa() and user.mfa_configured and mfa_verify_user_id:
                    # Double-check that mfa_verify_user_id matches login_user_id
                    if mfa_verify_user_id == user_id:
                        return redirect('/mfa/verify/')
                    else:
                        # Mismatch - clear and reset
                        request.session.pop('login_step', None)
                        request.session.pop('mfa_verify_user_id', None)
                        request.session.pop('login_user_id', None)
                else:
                    # Clear invalid session state
                    request.session.pop('login_step', None)
                    request.session.pop('mfa_verify_user_id', None)
                    request.session.pop('login_user_id', None)
            except User.DoesNotExist:
                # Clear invalid session state
                request.session.pop('login_step', None)
                request.session.pop('mfa_verify_user_id', None)
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
            if not form.is_valid():
                # Log form errors for debugging
                logger.warning(f'Signin form validation failed: {form.errors}')
                messages.error(request, 'Please correct the errors below.')
                return render(request, self.template_name, {'form': form, 'step': 1})
            
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
            # Try username first, then email if username fails
            user = authenticate(request, username=username, password=password)
            
            # If authentication failed and input looks like email, try email authentication
            if not user and '@' in username:
                try:
                    # Try to find user by email in User model or Profile model (User, Profile from top-level import)
                    email_user = User.objects.filter(email=username).first()
                    if not email_user:
                        # Try finding by profile email
                        profile = Profile.objects.filter(email=username).first()
                        if profile:
                            email_user = profile.user
                    if email_user:
                        user = authenticate(request, username=email_user.username, password=password)
                except Exception:
                    pass
            
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
                    
                    # Step 5: Complete Login (full OTP/2FA auth)
                    login(request, user)
                    
                    # Update login tracking and session-lock identity for PIN re-unlock
                    user.last_login_ip = client_ip
                    user.last_login_user_agent = user_agent
                    user.login_count += 1
                    user.last_full_auth_at = timezone.now()  # PIN unlock allowed within window
                    user.save(update_fields=['last_login_ip', 'last_login_user_agent', 'login_count', 'last_full_auth_at'])
                    
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
                    
                    response = redirect('/dashboard/')
                    _set_lock_identity_cookie(response, user.id)
                    return response
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
    
    def get_user(self, request):
        """Get user from session or authenticated user"""
        # If user is already logged in, use that user
        if request.user.is_authenticated:
            return request.user
        
        # Otherwise, try to get from session (for first-time setup during login)
        user_id = request.session.get('mfa_setup_user_id')
        if user_id:
            try:
                return User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        return None
    
    def get(self, request):
        user = self.get_user(request)
        if not user:
            messages.error(request, 'Invalid session. Please sign in again.')
            return redirect('/signin/')
        
        # Check action: remove_mfa or setup
        action = request.GET.get('action', 'setup')
        
        # If MFA is already configured and user wants to manage it
        if user.mfa_configured and action == 'remove':
            # Check if OTP verification is done for removal
            if not request.session.get('mfa_remove_verified'):
                # Show OTP verification form for removal
                # If OTP method, send OTP automatically
                otp_sent = False
                if user.mfa_method == 'otp':
                    phone = user.phone
                    if phone:
                        from portal.services.otp_service import OTPService
                        otp_service = OTPService()
                        success, message = otp_service.send_otp(phone, user_id=user.id, async_send=True)
                        if success:
                            otp_sent = True
                            messages.info(request, 'OTP sent to your phone. Please enter it to verify.')
                        else:
                            messages.warning(request, f'Failed to send OTP: {message}')
                
                context = {
                    'user': user,
                    'mfa_configured': True,
                    'mfa_method': user.mfa_method,
                    'action': 'remove_verify',
                    'show_remove_verification': True,
                    'otp_sent': otp_sent,
                }
                return render(request, self.template_name, context)
            else:
                # OTP verified, show remove confirmation
                context = {
                    'user': user,
                    'mfa_configured': True,
                    'mfa_method': user.mfa_method,
                    'action': 'remove_confirm',
                    'show_remove_confirmation': True,
                }
                return render(request, self.template_name, context)
        
        # If MFA is already configured, show status (for management)
        if user.mfa_configured and (action == 'setup' or action == 'manage' or not action or action == ''):
            context = {
                'user': user,
                'mfa_configured': True,
                'mfa_method': user.mfa_method,
                'action': 'manage',
                'show_status': True,
            }
            return render(request, self.template_name, context)
        
        # New MFA setup (MFA not configured)
        form = MFASetupForm()
        
        # Use existing secret from session if available, otherwise generate new one
        # This ensures QR code stays the same until MFA is successfully configured
        secret = request.session.get('mfa_setup_secret')
        if not secret:
            secret = generate_totp_secret()
            request.session['mfa_setup_secret'] = secret
        
        # Generate QR code with the same secret (static until MFA is configured)
        uri = generate_totp_uri(secret, user.email or user.username)
        qr_code = generate_qr_code(uri)
        
        context = {
            'form': form,
            'user': user,
            'qr_code': qr_code,
            'totp_secret': secret,  # For debugging if needed
            'mfa_configured': False,
            'mfa_method': None,
            'action': 'setup',
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        user = self.get_user(request)
        if not user:
            messages.error(request, 'Invalid session.')
            return redirect('/signin/')
        
        # Handle MFA removal verification
        action = request.POST.get('action', 'setup')
        
        if action == 'verify_remove':
            # Verify OTP for MFA removal
            verification_code = request.POST.get('verification_code', '').strip()
            
            if not verification_code:
                messages.error(request, 'Please enter the verification code.')
                context = {
                    'user': user,
                    'mfa_configured': True,
                    'mfa_method': user.mfa_method,
                    'action': 'remove_verify',
                    'show_remove_verification': True,
                }
                return render(request, self.template_name, context)
            
            # Verify based on MFA method
            verified = False
            if user.mfa_method == 'authenticator':
                secret = user.get_encrypted_totp_secret()
                if secret:
                    verified = verify_totp(secret, verification_code)
            elif user.mfa_method == 'otp':
                from portal.services.otp_service import OTPService
                otp_service = OTPService()
                phone = user.phone
                if phone:
                    verified, _ = otp_service.verify_otp(phone, verification_code)
            
            if verified:
                # Mark as verified in session
                request.session['mfa_remove_verified'] = True
                messages.success(request, 'Verification successful. You can now remove MFA.')
                return redirect('/mfa/setup/?action=remove')
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
                context = {
                    'user': user,
                    'mfa_configured': True,
                    'mfa_method': user.mfa_method,
                    'action': 'remove_verify',
                    'show_remove_verification': True,
                }
                return render(request, self.template_name, context)
        
        elif action == 'confirm_remove':
            # Confirm MFA removal (after OTP verification)
            if not request.session.get('mfa_remove_verified'):
                messages.error(request, 'Please verify your identity first.')
                return redirect('/mfa/setup/?action=remove')
            
            # Remove MFA
            user.mfa_method = None
            user.mfa_configured = False
            user.mfa_enabled = False
            user.set_encrypted_totp_secret(None)  # Clear TOTP secret
            user.save()
            
            # Clear session
            request.session.pop('mfa_remove_verified', None)
            if 'mfa_setup_secret' in request.session:
                del request.session['mfa_setup_secret']
            
            messages.success(request, 'MFA has been removed from your account.')
            return redirect('/mfa/setup/')
        
        # Handle new MFA setup
        form = MFASetupForm(request.POST)
        
        # Debug logging
        from portal.tasks.write_logs_task import write_logs_task
        from portal.utils.logging_utils import get_request_id, generate_response_id
        from portal.utils.ip_utils import get_client_ip, get_user_agent, get_session_id
        
        request_id = get_request_id(request)
        response_id = generate_response_id()
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        
        write_logs_task.delay(
            log_level='INFO',
            message=f'MFA Setup POST - User: {user.username}, Form valid: {form.is_valid()}, Data: {request.POST.dict()}',
            module_name='portal.views.MFASetupView',
            url=request.path,
            request_id=request_id,
            response_id=response_id,
            user_id=user.id,
            extra_data={
                'action': 'mfa_setup_post',
                'form_valid': form.is_valid(),
                'form_errors': form.errors if not form.is_valid() else None,
                'mfa_method': request.POST.get('mfa_method'),
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        
        if form.is_valid():
            mfa_method = form.cleaned_data['mfa_method']
            
            if mfa_method == 'otp':
                phone = form.cleaned_data['phone']
                # Store phone for OTP in profile
                if hasattr(user, 'profile') and user.profile:
                    user.profile.phone = phone
                    user.profile.save()
                user.mfa_method = 'otp'
                user.mfa_configured = True
                user.mfa_enabled = True
                user.save()
                
                # Send OTP via unified notification service
                from portal.services.otp_service import OTPService
                otp_service = OTPService()
                # Allow re-configuration if user explicitly wants to change (after removal)
                success, message = otp_service.send_otp(phone, user_id=user.id, async_send=True)
                if success:
                    messages.success(request, 'MFA configured successfully. OTP sent to your phone.')
                    # Clear session if it exists (for first-time setup)
                    if 'mfa_setup_user_id' in request.session:
                        del request.session['mfa_setup_user_id']
                    if 'mfa_remove_verified' in request.session:
                        del request.session['mfa_remove_verified']
                    # Only login if not already logged in
                    if not request.user.is_authenticated:
                        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                        return redirect('/dashboard/')
                    else:
                        # Already logged in, redirect to MFA setup to show status
                        return redirect('/mfa/setup/')
                else:
                    messages.error(request, f'Failed to send OTP: {message}')
                    # Generate QR code for context
                    secret = request.session.get('mfa_setup_secret')
                    if secret:
                        uri = generate_totp_uri(secret, user.email or user.username)
                        qr_code = generate_qr_code(uri)
                    else:
                        qr_code = None
                    return render(request, self.template_name, {
                        'form': form, 
                        'user': user,
                        'qr_code': qr_code,
                        'totp_secret': secret,
                        'mfa_configured': user.mfa_configured,
                        'mfa_method': user.mfa_method,
                        'action': 'setup',
                    })
            
            elif mfa_method == 'authenticator':
                secret = request.session.get('mfa_setup_secret')
                if not secret:
                    messages.error(request, 'Please refresh the page and try again.')
                    # Generate new secret and QR code
                    secret = generate_totp_secret()
                    request.session['mfa_setup_secret'] = secret
                    uri = generate_totp_uri(secret, user.email or user.username)
                    qr_code = generate_qr_code(uri)
                    return render(request, self.template_name, {
                        'form': form,
                        'user': user,
                        'qr_code': qr_code,
                        'totp_secret': secret,
                        'mfa_configured': user.mfa_configured,
                        'mfa_method': user.mfa_method,
                        'action': 'setup',
                    })
                
                totp_code = form.cleaned_data.get('totp_code', '').strip()
                
                # Debug logging
                write_logs_task.delay(
                    log_level='INFO',
                    message=f'MFA Authenticator Setup - User: {user.username}, Code length: {len(totp_code)}, Secret exists: {bool(secret)}',
                    module_name='portal.views.MFASetupView',
                    url=request.path,
                    request_id=request_id,
                    response_id=response_id,
                    user_id=user.id,
                    extra_data={
                        'action': 'mfa_authenticator_setup',
                        'code_length': len(totp_code),
                        'has_secret': bool(secret),
                    },
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                
                if not totp_code:
                    messages.error(request, 'Please enter the verification code from your authenticator app.')
                    # Keep existing QR code
                    uri = generate_totp_uri(secret, user.email or user.username)
                    qr_code = generate_qr_code(uri)
                    return render(request, self.template_name, {
                        'form': form,
                        'user': user,
                        'qr_code': qr_code,
                        'totp_secret': secret,
                        'mfa_configured': user.mfa_configured,
                        'mfa_method': user.mfa_method,
                        'action': 'setup',
                    })
                
                # Verify TOTP code
                is_valid = verify_totp(secret, totp_code)
                
                write_logs_task.delay(
                    log_level='INFO',
                    message=f'MFA Authenticator Verification - User: {user.username}, Valid: {is_valid}',
                    module_name='portal.views.MFASetupView',
                    url=request.path,
                    request_id=request_id,
                    response_id=response_id,
                    user_id=user.id,
                    extra_data={
                        'action': 'mfa_authenticator_verify',
                        'is_valid': is_valid,
                    },
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                
                if not is_valid:
                    messages.error(request, 'Invalid verification code. Please check your authenticator app and try again.')
                    # Keep existing QR code with same secret (don't regenerate - user already scanned it)
                    # Reuse the same secret from session
                    uri = generate_totp_uri(secret, user.email or user.username)
                    qr_code = generate_qr_code(uri)
                    return render(request, self.template_name, {
                        'form': form,
                        'user': user,
                        'qr_code': qr_code,
                        'totp_secret': secret,
                        'mfa_configured': user.mfa_configured,
                        'mfa_method': user.mfa_method,
                        'action': 'setup',
                    })
                
                # Allow re-configuration if user explicitly wants to change (after removal)
                # Save TOTP secret
                user.set_encrypted_totp_secret(secret)
                user.mfa_method = 'authenticator'
                user.mfa_configured = True
                user.mfa_enabled = True
                user.save()
                
                messages.success(request, 'MFA configured successfully with Authenticator.')
                # Clear session secret after successful setup
                if 'mfa_setup_secret' in request.session:
                    del request.session['mfa_setup_secret']
                if 'mfa_setup_user_id' in request.session:
                    del request.session['mfa_setup_user_id']
                if 'mfa_remove_verified' in request.session:
                    del request.session['mfa_remove_verified']
                # Only login if not already logged in (user was loaded from DB, so pass backend)
                if not request.user.is_authenticated:
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect('/dashboard/')
                else:
                    # Already logged in, redirect to MFA setup to show status
                    return redirect('/mfa/setup/')
        
        # Form is invalid - show errors
        messages.error(request, 'Please correct the errors below.')
        # Use existing secret from session (don't regenerate - keep QR code static)
        secret = request.session.get('mfa_setup_secret')
        if not secret:
            secret = generate_totp_secret()
            request.session['mfa_setup_secret'] = secret
        
        uri = generate_totp_uri(secret, user.email or user.username)
        qr_code = generate_qr_code(uri)
        
        return render(request, self.template_name, {
            'form': form,
            'user': user,
            'qr_code': qr_code,
            'totp_secret': secret,
            'mfa_configured': user.mfa_configured,
            'mfa_method': user.mfa_method,
            'action': 'setup',
        })


class MFAVerifyView(View):
    """MFA verification view"""
    template_name = 'portal/auth/mfa_verify.html'
    
    def get(self, request):
        # Check if user is already authenticated
        if request.user.is_authenticated:
            # If user is already logged in and MFA is configured, redirect to dashboard
            if request.user.mfa_configured:
                return redirect('/dashboard/')
            # If MFA is not configured but required, redirect to setup
            if request.user.requires_mfa() and not request.user.mfa_configured:
                return redirect('/mfa/setup/')
            # Otherwise, go to dashboard
            return redirect('/dashboard/')
        
        # User is not authenticated - check session for MFA verification
        user_id = request.session.get('mfa_verify_user_id')
        if not user_id:
            messages.error(request, 'Invalid session. Please sign in again.')
            return redirect('/signin/')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            # Clear invalid session
            request.session.pop('mfa_verify_user_id', None)
            request.session.pop('login_step', None)
            request.session.pop('login_user_id', None)
            return redirect('/signin/')
        
        # Additional validation: ensure user still requires MFA and has it configured
        if not user.requires_mfa() or not user.mfa_configured:
            # Clear session and redirect to signin
            request.session.pop('mfa_verify_user_id', None)
            request.session.pop('login_step', None)
            request.session.pop('login_user_id', None)
            messages.error(request, 'MFA verification is not required for your account.')
            return redirect('/signin/')
        
        # Do NOT send OTP on page load. OTP is sent only when user clicks the OTP tab (via resend-otp).
        form = MFAVerifyForm()
        return render(request, self.template_name, {'form': form, 'user': user})
    
    def post(self, request):
        # Check if user is already authenticated
        if request.user.is_authenticated:
            # If already logged in, redirect to dashboard
            return redirect('/dashboard/')
        
        # User is not authenticated - check session for MFA verification
        user_id = request.session.get('mfa_verify_user_id')
        if not user_id:
            # Clear all related session variables
            request.session.pop('mfa_verify_user_id', None)
            request.session.pop('login_step', None)
            request.session.pop('login_user_id', None)
            messages.error(request, 'Invalid session. Please sign in again.')
            return redirect('/signin/')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            # Clear all related session variables
            request.session.pop('mfa_verify_user_id', None)
            request.session.pop('login_step', None)
            request.session.pop('login_user_id', None)
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
                # Get phone from profile
                phone_number = None
                if hasattr(user, 'profile') and user.profile:
                    phone_number = user.profile.phone
                elif hasattr(user, 'phone'):
                    phone_number = user.phone
                
                if phone_number:
                    verified, _ = otp_service.verify_otp(phone_number, mfa_code)
                else:
                    verified = False
            elif method == 'authenticator' or user.mfa_method == 'authenticator':
                # Verify TOTP
                secret = user.get_encrypted_totp_secret()
                if secret:
                    verified = verify_totp(secret, mfa_code)
                else:
                    verified = False
            
            if verified:
                del request.session['mfa_verify_user_id']
                backends = get_backends()
                if backends:
                    user.backend = f'{backends[0].__module__}.{backends[0].__class__.__name__}'
                else:
                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                # Session lock: allow PIN re-unlock within window
                user.last_full_auth_at = timezone.now()
                user.save(update_fields=['last_full_auth_at'])
                response = redirect('/dashboard/')
                _set_lock_identity_cookie(response, user.id)
                return response
            else:
                messages.error(request, 'Invalid verification code.')
        else:
            messages.error(request, 'Please enter a valid code.')
        
        return render(request, self.template_name, {'form': form, 'user': user})


# ---------------------------------------------------------------------------
# Session lock / PIN unlock (secondary re-unlock; OTP/2FA is primary auth)
# ---------------------------------------------------------------------------

def _set_lock_identity_cookie(response, user_id):
    """Set signed cookie with user id for PIN unlock flow after session expiry."""
    signer = Signer()
    value = signer.sign(json.dumps({'user_id': user_id}))
    response.set_cookie(
        LOCK_IDENTITY_COOKIE_NAME,
        value,
        max_age=LOCK_IDENTITY_COOKIE_MAX_AGE,
        httponly=True,
        secure=not payswap_config.DEBUG,
        samesite='Lax',
    )


def _clear_lock_identity_cookie(response):
    """Clear lock identity cookie (e.g. on full logout)."""
    response.delete_cookie(LOCK_IDENTITY_COOKIE_NAME, path='/')
    response.delete_cookie(LOCK_STARTED_AT_COOKIE_NAME, path='/')


class SetPinView(LoginRequiredMixin, View):
    """
    Set 4-digit PIN for session re-unlock after expiry.
    User must be fully authenticated via OTP/2FA (LoginRequiredMixin).
    PIN is hashed with make_password(); never stored or logged in plaintext.
    """
    template_name = 'portal/auth/set_pin.html'
    login_url = '/signin/'

    def get(self, request):
        form = SetPinForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = SetPinForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        pin = form.cleaned_data['pin']
        user = request.user
        user.pin_hash = make_password(pin, salt=None)
        user.pin_set_at = timezone.now()
        user.pin_failed_attempts = 0
        user.pin_locked_until = None
        user.save(update_fields=['pin_hash', 'pin_set_at', 'pin_failed_attempts', 'pin_locked_until'])
        log_pin_set(user.id, client_ip=get_client_ip(request))
        messages.success(request, 'PIN set. You can use it to unlock after session expiry.')
        return redirect(request.GET.get('next') or '/dashboard/')


class UnlockWithPinView(View):
    """
    Re-unlock with 4-digit PIN after session expiry (no OTP/2FA).
    Identity comes from signed lock_identity cookie. PIN must exist,
    pin_locked_until must be null/expired, last_full_auth_at within window.
    """
    template_name = 'portal/auth/unlock_with_pin.html'

    def get(self, request):
        user = get_user_from_lock_cookie(request)
        if not user:
            messages.error(request, 'Session expired. Please sign in again.')
            return redirect('/signin/')
        if not user.pin_hash:
            log_forced_otp_reauth(user.id, 'no_pin_set', client_ip=get_client_ip(request))
            messages.info(request, 'Please sign in with OTP/2FA.')
            return redirect('/signin/')
        now = timezone.now()
        if user.pin_locked_until and user.pin_locked_until > now:
            log_forced_otp_reauth(user.id, 'pin_locked', client_ip=get_client_ip(request))
            messages.error(request, 'PIN unlock is temporarily locked. Please sign in with OTP/2FA.')
            return redirect('/signin/')
        if not user.last_full_auth_at:
            log_forced_otp_reauth(user.id, 'no_full_auth', client_ip=get_client_ip(request))
            messages.info(request, 'Please sign in with OTP/2FA.')
            return redirect('/signin/')
        window_end = user.last_full_auth_at + timezone.timedelta(seconds=PIN_UNLOCK_WINDOW_SECONDS)
        if now > window_end:
            log_forced_otp_reauth(user.id, 'full_auth_window_expired', client_ip=get_client_ip(request))
            messages.info(request, 'Session window expired. Please sign in with OTP/2FA.')
            return redirect('/signin/')
        # 30-min timer: reset only when this is a new lock (new_lock=1); otherwise use existing cookie
        next_url = request.GET.get('next', '/dashboard/')
        new_lock = request.GET.get('new_lock') == '1'
        if new_lock:
            lock_started_at = int(time.time())
            resp = redirect(reverse('unlock_with_pin') + '?next=' + quote(next_url))
            resp.set_cookie(
                LOCK_STARTED_AT_COOKIE_NAME,
                str(lock_started_at),
                max_age=PIN_UNLOCK_PAGE_TIMEOUT_SECONDS,
                path='/',
                httponly=True,
                secure=not payswap_config.DEBUG,
                samesite='Lax',
            )
            return resp
        raw_started = request.COOKIES.get(LOCK_STARTED_AT_COOKIE_NAME)
        lock_started_at = int(time.time())
        if raw_started:
            try:
                lock_started_at = int(raw_started)
            except (ValueError, TypeError):
                lock_started_at = int(time.time())
        elapsed = int(time.time()) - lock_started_at
        if elapsed >= PIN_UNLOCK_PAGE_TIMEOUT_SECONDS:
            response = redirect('/signin/')
            messages.info(request, 'Unlock time expired. Please sign in again.')
            _clear_lock_identity_cookie(response)
            return response
        remaining_seconds = max(0, PIN_UNLOCK_PAGE_TIMEOUT_SECONDS - elapsed)
        form = UnlockPinForm()
        greeting_name = (getattr(user, 'profile', None) and getattr(user.profile, 'first_name', None)) or getattr(user, 'first_name', None) or 'there'
        response = render(request, self.template_name, {
            'form': form, 'next_url': next_url, 'greeting_name': greeting_name,
            'remaining_seconds': remaining_seconds,
            'pin_unlock_timeout_seconds': PIN_UNLOCK_PAGE_TIMEOUT_SECONDS,
        })
        if not raw_started:
            response.set_cookie(
                LOCK_STARTED_AT_COOKIE_NAME,
                str(lock_started_at),
                max_age=PIN_UNLOCK_PAGE_TIMEOUT_SECONDS,
                path='/',
                httponly=True,
                secure=not payswap_config.DEBUG,
                samesite='Lax',
            )
        return response

    def post(self, request):
        user = get_user_from_lock_cookie(request)
        client_ip = get_client_ip(request)
        if not user:
            messages.error(request, 'Session expired. Please sign in again.')
            return redirect('/signin/')
        if not user.pin_hash:
            log_forced_otp_reauth(user.id, 'no_pin_set', client_ip=client_ip)
            return redirect('/signin/')
        now = timezone.now()
        if user.pin_locked_until and user.pin_locked_until > now:
            log_forced_otp_reauth(user.id, 'pin_locked', client_ip=client_ip)
            messages.error(request, 'PIN unlock is temporarily locked. Please sign in with OTP/2FA.')
            return redirect('/signin/')
        if not user.last_full_auth_at:
            return redirect('/signin/')
        window_end = user.last_full_auth_at + timezone.timedelta(seconds=PIN_UNLOCK_WINDOW_SECONDS)
        if now > window_end:
            log_forced_otp_reauth(user.id, 'full_auth_window_expired', client_ip=client_ip)
            return redirect('/signin/')
        # 30-min page timer: reject if unlock screen time expired
        raw_started = request.COOKIES.get(LOCK_STARTED_AT_COOKIE_NAME)
        if raw_started:
            try:
                lock_started_at = int(raw_started)
                if (int(time.time()) - lock_started_at) >= PIN_UNLOCK_PAGE_TIMEOUT_SECONDS:
                    response = redirect('/signin/')
                    messages.info(request, 'Unlock time expired. Please sign in again.')
                    _clear_lock_identity_cookie(response)
                    return response
            except (ValueError, TypeError):
                pass
        form = UnlockPinForm(request.POST)
        if not form.is_valid():
            next_url = request.GET.get('next', '/dashboard/')
            greeting_name = (getattr(user, 'profile', None) and getattr(user.profile, 'first_name', None)) or getattr(user, 'first_name', None) or 'there'
            raw_started = request.COOKIES.get(LOCK_STARTED_AT_COOKIE_NAME)
            lock_started_at = int(time.time())
            if raw_started:
                try:
                    lock_started_at = int(raw_started)
                except (ValueError, TypeError):
                    pass
            remaining_seconds = max(0, PIN_UNLOCK_PAGE_TIMEOUT_SECONDS - (int(time.time()) - lock_started_at))
            return render(request, self.template_name, {
                'form': form, 'next_url': next_url, 'greeting_name': greeting_name,
                'remaining_seconds': remaining_seconds,
                'pin_unlock_timeout_seconds': PIN_UNLOCK_PAGE_TIMEOUT_SECONDS,
            })
        pin = form.cleaned_data['pin']
        if check_password(pin, user.pin_hash):
            user.pin_failed_attempts = 0
            user.save(update_fields=['pin_failed_attempts'])
            log_pin_unlock_success(user.id, client_ip=client_ip)
            backends = get_backends()
            user.backend = f'{backends[0].__module__}.{backends[0].__class__.__name__}' if backends else 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            next_url = request.GET.get('next', '/dashboard/')
            resp = redirect(next_url)
            resp.delete_cookie(LOCK_STARTED_AT_COOKIE_NAME, path='/')
            return resp
        user.pin_failed_attempts = (user.pin_failed_attempts or 0) + 1
        if user.pin_failed_attempts >= PIN_MAX_ATTEMPTS:
            user.pin_locked_until = now + timezone.timedelta(minutes=PIN_LOCK_DURATION_MINUTES)
            user.save(update_fields=['pin_failed_attempts', 'pin_locked_until'])
            log_pin_lockout(user.id, client_ip=client_ip)
            log_forced_otp_reauth(user.id, 'pin_lockout', client_ip=client_ip)
            messages.error(request, 'Too many wrong PINs. PIN unlock is locked. Please sign in with OTP/2FA.')
            return redirect('/signin/')
        user.save(update_fields=['pin_failed_attempts'])
        log_pin_unlock_failure(user.id, client_ip=client_ip)
        messages.error(request, 'Incorrect PIN.')
        next_url = request.GET.get('next', '/dashboard/')
        greeting_name = (getattr(user, 'profile', None) and getattr(user.profile, 'first_name', None)) or getattr(user, 'first_name', None) or 'there'
        raw_started = request.COOKIES.get(LOCK_STARTED_AT_COOKIE_NAME)
        lock_started_at = int(time.time())
        if raw_started:
            try:
                lock_started_at = int(raw_started)
            except (ValueError, TypeError):
                pass
        remaining_seconds = max(0, PIN_UNLOCK_PAGE_TIMEOUT_SECONDS - (int(time.time()) - lock_started_at))
        return render(request, self.template_name, {
            'form': form, 'next_url': next_url, 'greeting_name': greeting_name,
            'remaining_seconds': remaining_seconds,
            'pin_unlock_timeout_seconds': PIN_UNLOCK_PAGE_TIMEOUT_SECONDS,
        })


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
    
    # Get phone from profile (same user as ParkPe – ensure Profile has correct mobile in Django admin)
    phone_number = None
    if hasattr(user, 'profile') and user.profile:
        phone_number = (user.profile.phone or "").strip()
    if not phone_number and hasattr(user, 'phone'):
        phone_number = (user.phone or "").strip()
    
    if not phone_number:
        return JsonResponse({'success': False, 'message': 'Phone number not found. Add mobile in Profile (Django admin).'}, status=400)
    
    # Normalize to 91XXXXXXXXXX so Portal uses same format as ParkPe (OTP delivery is same gateway)
    try:
        from portal.utils.validators import normalize_phone_number
        normalized = normalize_phone_number(phone_number)
        phone_number = normalized.lstrip('+') if normalized.startswith('+') else normalized
    except ValueError as e:
        return JsonResponse({'success': False, 'message': f'Invalid phone in profile: {str(e)}. Update in Django admin.'}, status=400)
    
    # Send OTP via same gateway as ParkPe (Kaleyra)
    otp_service = OTPService()
    success, message = otp_service.send_otp(phone_number, user_id=user.id, async_send=True)
    
    if success:
        # Clear the OTP sent flag so it can be sent again
        request.session.pop(f'mfa_otp_sent_{user.id}', None)
        
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
    """Sign out view; clear session and lock-identity cookie."""
    logout(request)
    messages.success(request, 'You have been signed out successfully.')
    response = redirect('/')
    _clear_lock_identity_cookie(response)
    return response


@login_required
def lock_screen_view(request):
    """Lock screen: clear session but keep lock_identity cookie so user can unlock with PIN. Timer restarts (30 min) each time."""
    next_path = request.GET.get('next') or request.path or '/dashboard/'
    logout(request)
    return redirect(f'/auth/unlock-with-pin/?next={quote(next_path)}&new_lock=1')


def unlock_expired_view(request):
    """Clear lock cookies and redirect to signin when 30-min unlock timer expires (called by JS)."""
    response = redirect('/signin/')
    _clear_lock_identity_cookie(response)
    messages.info(request, 'Unlock time expired. Please sign in again.')
    return response


class EmployeeDashboardView(TemplateView):
    """Employee dashboard"""
    template_name = 'portal/dashboard/employee.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class SuperDashboardView(TemplateView):
    """Super dashboard - same stats and quick actions as Admin for system-wide access"""
    template_name = 'portal/dashboard/super.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['pending_kyc'] = KYC.objects.filter(status='pending').count()
        context['total_wallets'] = Wallet.objects.count()
        context['active_profiles'] = Profile.objects.filter(status='active').count()
        # Partner stats (same as Admin)
        try:
            from portal.models import ResellerPartner, ResellerPartnerTransaction
            from django.db.models import Sum, Q
            from django.utils import timezone
            from datetime import timedelta
            partners = ResellerPartner.objects.all()
            context['total_partners'] = partners.count()
            context['active_partners'] = partners.filter(status='ACTIVE', onboarding_status='APPROVED').count()
            context['pending_partner_onboarding'] = partners.filter(onboarding_status='PENDING').count()
            last_30d = timezone.now() - timedelta(days=30)
            financial_summary = ResellerPartnerTransaction.objects.filter(
                transaction_date__gte=last_30d,
                status='COMPLETED'
            ).aggregate(
                total_revenue=Sum('amount', filter=Q(transaction_type='REVENUE')),
                total_commission=Sum('commission_amount', filter=Q(transaction_type='COMMISSION'))
            )
            context['partner_revenue_30d'] = financial_summary.get('total_revenue') or 0
            context['partner_commission_30d'] = financial_summary.get('total_commission') or 0
            context['recent_partners'] = partners.select_related('wallet').order_by('-created_at')[:5]
        except Exception as e:
            logger.error(f'Error loading partner stats for super dashboard: {str(e)}')
            context['total_partners'] = 0
            context['active_partners'] = 0
            context['pending_partner_onboarding'] = 0
            context['partner_revenue_30d'] = 0
            context['partner_commission_30d'] = 0
            context['recent_partners'] = []
        return context


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
    
    def get_form_kwargs(self):
        """Override to remove 'instance' for regular Form (not ModelForm)"""
        kwargs = super().get_form_kwargs()
        # UserCreateForm is a regular Form, not ModelForm, so remove 'instance'
        if 'instance' in kwargs:
            kwargs.pop('instance')
        return kwargs
    
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


class KYCListView(ListView):
    """View to list all KYC submissions"""
    model = KYC
    template_name = 'portal/kyc/list.html'
    context_object_name = 'kycs'
    paginate_by = 20
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        # Check permission
        if not self.request.user.has_perm('portal.view_kyc'):
            messages.error(self.request, 'You do not have permission to view KYC submissions.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        queryset = KYC.objects.select_related('user', 'verified_by').all()
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by document type
        document_type = self.request.GET.get('document_type')
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(user__username__icontains=search) |
                models.Q(document_number__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        context['total_kycs'] = KYC.objects.count()
        context['pending_kycs'] = KYC.objects.filter(status='pending').count()
        context['submitted_kycs'] = KYC.objects.filter(status='submitted').count()
        context['approved_kycs'] = KYC.objects.filter(status='approved').count()
        context['rejected_kycs'] = KYC.objects.filter(status='rejected').count()
        
        # Filter options
        context['status_choices'] = KYC.STATUS_CHOICES
        context['document_type_choices'] = KYC.DOCUMENT_TYPE_CHOICES
        
        return context


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
        from collections import OrderedDict
        from portal.utils.role_utils import get_user_permissions

        users = User.objects.filter(is_active=True).select_related('role')
        permissions = Permission.objects.all().select_related('content_type').order_by('content_type__app_label', 'content_type__model', 'codename')
        roles = Role.objects.all().prefetch_related('default_permissions')

        # Group permissions by app_label for systematic dropdowns
        permissions_by_app = OrderedDict()
        for perm in permissions:
            app = perm.content_type.app_label
            if app not in permissions_by_app:
                permissions_by_app[app] = []
            permissions_by_app[app].append(perm)

        # Get user permissions for display
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


def _permissions_by_category(permission_list):
    """Group permission list by app_label (category) then by model (type). Returns OrderedDict[app_label, OrderedDict[model, list]]."""
    from collections import OrderedDict
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


class PermissionManageUserView(View):
    """New screen: manage user permissions with category-wise checkboxes and bulk assign/revoke."""
    template_name = 'portal/permissions/manage_bulk.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not CanManagePermissions().has_permission(self.request, self):
            messages.error(self.request, 'You do not have permission to manage permissions.')
            return redirect('/permissions/')
        return super().dispatch(*args, **kwargs)

    def get(self, request, user_id):
        from django.contrib.auth.models import Permission

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
        from django.contrib.auth.models import Permission

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
    """New screen: manage role permissions with category-wise checkboxes and bulk assign/revoke."""
    template_name = 'portal/permissions/manage_bulk.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not CanManagePermissions().has_permission(self.request, self):
            messages.error(self.request, 'You do not have permission to manage permissions.')
            return redirect('/permissions/')
        return super().dispatch(*args, **kwargs)

    def get(self, request, role_id):
        from django.contrib.auth.models import Permission

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
        from django.contrib.auth.models import Permission

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
        # Existing user - proceed to login (pass backend when multiple backends are configured)
        user = social_account.user
        if not getattr(user, 'backend', None):
            user.backend = 'allauth.account.auth_backends.AuthenticationBackend'
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


# SocialSignupAdapter is now in portal/adapters.py


class TicketListView(ListView):
    """Ticket list view with filtering"""
    model = Ticket
    template_name = 'portal/tickets/list.html'
    context_object_name = 'tickets'
    paginate_by = 20
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        """Filter tickets based on user role"""
        queryset = Ticket.objects.select_related(
            'created_by', 'assigned_to', 'department'
        ).all()
        user = self.request.user
        
        # Super Admin and Admin can see all tickets
        if user.role_code in ['super_admin', 'admin']:
            pass  # Show all
        # Department Manager can see all tickets in their department
        elif user.role_code == 'employee':
            try:
                agent = user.agent_profile
                if agent and agent.department:
                    queryset = queryset.filter(department=agent.department)
            except (Agent.DoesNotExist, AttributeError):
                queryset = queryset.none()
        # Support Agent can see tickets assigned to them or in their department
        elif user.role_code == 'employee':
            try:
                agent = user.agent_profile
                if agent and agent.department:
                    queryset = queryset.filter(
                        models.Q(assigned_to=user) | 
                        models.Q(department=agent.department)
                    )
                else:
                    queryset = queryset.filter(assigned_to=user)
            except (Agent.DoesNotExist, AttributeError):
                queryset = queryset.filter(assigned_to=user)
        # Business users can only see their own tickets
        else:
            queryset = queryset.filter(created_by=user)
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        department_id = self.request.GET.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(ticket_id__icontains=search) |
                models.Q(subject__icontains=search) |
                models.Q(description__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Ticket.STATUS_CHOICES
        context['priority_choices'] = Ticket.PRIORITY_CHOICES
        context['departments'] = Department.objects.filter(is_active=True)
        
        # Statistics
        queryset = self.get_queryset()
        context['total_tickets'] = queryset.count()
        context['open_tickets'] = queryset.filter(status__in=['NEW', 'OPEN', 'IN_PROGRESS', 'PENDING']).count()
        context['resolved_tickets'] = queryset.filter(status='RESOLVED').count()
        context['closed_tickets'] = queryset.filter(status='CLOSED').count()
        
        return context


class TicketDetailView(DetailView):
    """Ticket detail view"""
    model = Ticket
    template_name = 'portal/tickets/detail.html'
    context_object_name = 'ticket'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        """Filter based on permissions"""
        queryset = Ticket.objects.select_related(
            'created_by', 'assigned_to', 'department'
        ).prefetch_related('notes', 'attachments', 'assignment_history')
        user = self.request.user
        
        # Super Admin and Admin can see all
        if user.role_code in ['super_admin', 'admin']:
            return queryset
        # Department Manager can see tickets in their department
        elif user.role_code == 'employee':
            try:
                agent = user.agent_profile
                if agent and agent.department:
                    return queryset.filter(department=agent.department)
            except (Agent.DoesNotExist, AttributeError):
                pass
        # Support Agent can see assigned or department tickets
        elif user.role_code == 'employee':
            try:
                agent = user.agent_profile
                if agent and agent.department:
                    return queryset.filter(
                        models.Q(assigned_to=user) | 
                        models.Q(department=agent.department)
                    )
            except (Agent.DoesNotExist, AttributeError):
                pass
            return queryset.filter(assigned_to=user)
        # Business users can only see their own
        return queryset.filter(created_by=user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticket = self.object
        
        # Get notes (separate internal and customer-visible)
        context['internal_notes'] = ticket.notes.filter(is_internal=True).order_by('-created_at')
        context['customer_notes'] = ticket.notes.filter(is_internal=False).order_by('-created_at')
        context['all_notes'] = ticket.notes.all().order_by('-created_at')
        context['attachments'] = ticket.attachments.all().order_by('-uploaded_at')
        context['assignment_history'] = ticket.assignment_history.all().order_by('-created_at')[:10]
        
        # Get available agents for assignment (if user has permission)
        user = self.request.user
        if user.role_code in ['super_admin', 'admin', 'employee']:
            if ticket.department:
                context['available_agents'] = Agent.objects.filter(
                    department=ticket.department,
                    is_available=True
                ).select_related('user')
            else:
                context['available_agents'] = Agent.objects.filter(
                    is_available=True
                ).select_related('user')
        
        context['status_choices'] = Ticket.STATUS_CHOICES
        context['priority_choices'] = Ticket.PRIORITY_CHOICES
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle ticket actions"""
        ticket = self.get_object()
        action = request.POST.get('action')
        user = request.user
        
        if action == 'update_status':
            new_status = request.POST.get('status')
            if new_status in dict(Ticket.STATUS_CHOICES):
                ticket.update_status(new_status, user)
                messages.success(request, f'Ticket status updated to {new_status}')
        
        elif action == 'update_priority':
            new_priority = request.POST.get('priority')
            if new_priority in dict(Ticket.PRIORITY_CHOICES):
                ticket.priority = new_priority
                ticket.save()
                messages.success(request, f'Ticket priority updated to {new_priority}')
        
        elif action == 'assign':
            agent_id = request.POST.get('agent_id')
            try:
                agent_user = User.objects.get(id=agent_id)
                old_agent = ticket.assigned_to
                ticket.assign_to_agent(agent_user, assigned_by=user)
                
                # Create assignment history
                TicketAssignmentHistory.objects.create(
                    ticket=ticket,
                    assigned_from=old_agent,
                    assigned_to=agent_user,
                    assigned_by=user,
                    reason=request.POST.get('reason', 'Manual assignment')
                )
                messages.success(request, f'Ticket assigned to {agent_user.username}')
            except User.DoesNotExist:
                messages.error(request, 'Agent not found')
        
        elif action == 'pick':
            # Agent picks ticket
            try:
                agent = user.agent_profile
                if not agent or (ticket.department and agent.department != ticket.department):
                    messages.error(request, 'You are not an agent in this ticket\'s department')
                elif not agent.can_accept_ticket():
                    messages.error(request, 'You have reached your maximum ticket limit')
                else:
                    ticket.assign_to_agent(user, assigned_by=user)
                    TicketAssignmentHistory.objects.create(
                        ticket=ticket,
                        assigned_from=None,
                        assigned_to=user,
                        assigned_by=user,
                        reason='Self-assigned by agent'
                    )
                    messages.success(request, 'Ticket picked successfully')
            except (Agent.DoesNotExist, AttributeError):
                messages.error(request, 'You are not an agent')
        
        elif action == 'add_note':
            content = request.POST.get('content', '').strip()
            is_internal = request.POST.get('is_internal') == 'on'
            if content:
                TicketNote.objects.create(
                    ticket=ticket,
                    created_by=user,
                    content=content,
                    is_internal=is_internal
                )
                messages.success(request, 'Note added successfully')
            else:
                messages.error(request, 'Note content is required')
        
        return redirect('ticket_detail', pk=ticket.pk)


class TicketCreateView(CreateView):
    """Create new ticket"""
    model = Ticket
    template_name = 'portal/tickets/create.html'
    fields = ['subject', 'description', 'priority', 'category', 'department']
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_form(self, form_class=None):
        """Customize form"""
        form = super().get_form(form_class)
        form.fields['subject'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]',
            'placeholder': 'Enter ticket subject'
        })
        form.fields['description'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]',
            'rows': 6,
            'placeholder': 'Describe your issue in detail'
        })
        form.fields['priority'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]'
        })
        form.fields['category'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]',
            'placeholder': 'Optional category'
        })
        form.fields['department'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]'
        })
        form.fields['department'].queryset = Department.objects.filter(is_active=True)
        form.fields['department'].required = False
        return form
    
    def form_valid(self, form):
        """Set created_by and auto-assign if department specified"""
        ticket = form.save(commit=False)
        ticket.created_by = self.request.user
        ticket.save()
        
        # Auto-assign if department is specified
        if ticket.department:
            available_agents = Agent.objects.filter(
                department=ticket.department,
                is_available=True
            ).order_by('current_tickets', 'id')
            
            for agent in available_agents:
                if agent.can_accept_ticket():
                    ticket.assign_to_agent(agent.user)
                    break
        
        messages.success(self.request, f'Ticket {ticket.ticket_id} created successfully')
        return redirect('ticket_detail', pk=ticket.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['priority_choices'] = Ticket.PRIORITY_CHOICES
        context['departments'] = Department.objects.filter(is_active=True)
        return context


# ============================================================================
# SERVICES MANAGEMENT VIEWS
# ============================================================================

class ServicesListView(ListView):
    """View to list all services"""
    model = Service
    template_name = 'portal/services/list.html'
    context_object_name = 'services'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        # Only admin and super can access services
        if not self.request.user.is_authenticated:
            return redirect('/signin/')
        if self.request.user.role_code not in ['super_admin', 'admin']:
            messages.error(self.request, 'You do not have permission to view services.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        context['total_services'] = Service.objects.count()
        context['active_services'] = Service.objects.filter(status='active', is_enabled=True).count()
        context['pending_services'] = Service.objects.filter(status='pending').count()
        context['inactive_services'] = Service.objects.filter(status='inactive').count()
        
        return context


class ApiVendorListView(ListView):
    """List API vendors (Vendor -> APIs -> Service Flow architecture)."""
    model = ApiVendor
    template_name = 'portal/services/api_vendor_list.html'
    context_object_name = 'vendors'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect('/signin/')
        if self.request.user.role_code not in ['super_admin', 'admin']:
            messages.error(self.request, 'You do not have permission to view API vendors.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return ApiVendor.objects.all().prefetch_related('apis').order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_vendors'] = ApiVendor.objects.count()
        context['active_vendors'] = ApiVendor.objects.filter(is_active=True).count()
        context['total_apis'] = VendorApi.objects.count()
        profile = getattr(self.request.user, "profile", None)
        context['has_postman_key'] = bool(profile and getattr(profile, "postman_api_key", None))
        try:
            from core.config import payswap_config
            default_key = getattr(payswap_config, "EXPLORER_DEFAULT_API_KEY", None)
            if default_key and hasattr(default_key, "get_secret_value"):
                default_key = default_key.get_secret_value()
            default_key = (default_key or "").strip()
            if not default_key and self.request.user.is_authenticated and profile and getattr(profile, "postman_api_key", None):
                default_key = (profile.postman_api_key or "").strip()
            context['default_postman_key'] = (default_key or "")[:512]
        except Exception:
            context['default_postman_key'] = ""
        return context


# Map vendor_code -> service_code for partner simulation access check
_VENDOR_TO_SERVICE = {
    'euronet': 'bbps',
    'mobikwik': 'bbps',
    'cashfree': 'kyc',
    'instantpay': 'kyc',
    'kaleyra': 'sms',
    'cashfree_pg': 'payment',
    'leegality': 'esign',
}


@login_required
@require_http_methods(["POST"])
def api_vendor_try_api_view(request, vendor_code, api_code):
    """
    POST: Try a single vendor API (Postman-style). Body = JSON payload for the handler.
    Optional keys in body: testing_mode ('admin'|'partner_simulation'), partner_id (for simulation).
    Returns JSON: { success, result, error, status_code, time_ms }.
    """
    if not request.user.is_authenticated or request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({"success": False, "error": "permission_denied"}, status=403)

    vendor = get_object_or_404(ApiVendor, code=vendor_code)
    vendor_api = get_object_or_404(VendorApi, vendor=vendor, api_code=api_code)

    try:
        body = request.body.decode("utf-8") or "{}"
        payload = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError as e:
        return JsonResponse({"success": False, "error": f"invalid_json: {e}"}, status=400)

    testing_mode = (payload.pop("testing_mode", None) or "admin").strip()
    partner_id = payload.pop("partner_id", None)

    if testing_mode == "partner_simulation" and partner_id is not None:
        try:
            partner = ResellerPartner.objects.get(id=int(partner_id), status="ACTIVE")
        except (ValueError, ResellerPartner.DoesNotExist):
            return JsonResponse({
                "success": False,
                "error": "partner_not_found",
                "message": "Invalid or inactive partner for simulation.",
            }, status=400)
        service_code = _VENDOR_TO_SERVICE.get(vendor_code)
        if service_code:
            from portal.services.partner_vendor_service import PartnerVendorService
            if not PartnerVendorService.can_partner_use_vendor(partner, service_code, vendor):
                return JsonResponse({
                    "success": False,
                    "error": "vendor_not_assigned",
                        "message": f"Partner {partner.company_name} does not have access to vendor {vendor.name} for {service_code}.",
                }, status=403)

    from portal.services.execution_engine import get_execution_engine

    class _MockStep:
        pass

    step = _MockStep()
    step.vendor_api = vendor_api
    step.vendor = vendor
    step.step_name = vendor_api.name
    step.step_order = 0

    engine = get_execution_engine()
    handler = engine.get_handler(vendor_code, api_code)
    if not handler:
        return JsonResponse({
            "success": False,
            "error": "handler_not_registered",
            "message": f"No handler for {vendor_code}:{api_code}",
        }, status=501)

    start = timezone.now()
    try:
        outcome = handler(step, {}, payload)
    except Exception as e:
        import traceback
        return JsonResponse({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc() if request.user.is_staff else None,
        }, status=500)
    elapsed_ms = int((timezone.now() - start).total_seconds() * 1000)

    return JsonResponse({
        "success": outcome.get("success", False),
        "result": outcome.get("result"),
        "error": outcome.get("error"),
        "status_code": 200,
        "time_ms": elapsed_ms,
    })


@login_required
@require_http_methods(["POST"])
def postman_sync_view(request):
    """
    POST: Sync collections from Postman API.
    Body (JSON): { "api_key": "optional if saved", "save_key": false }
    Uses request.user.profile.postman_api_key if api_key not in body.
    Returns JSON: { success, collections } or { success: false, error }.
    """
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({"success": False, "error": "permission_denied"}, status=403)
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        data = {}
    api_key = (data.get("api_key") or "").strip()
    save_key = data.get("save_key") is True
    if not api_key:
        profile = getattr(request.user, "profile", None)
        if profile:
            api_key = (profile.postman_api_key or "").strip()
    if not api_key:
        return JsonResponse({"success": False, "error": "Postman API key required. Enter key and try again or save it in Settings."}, status=400)
    if save_key:
        profile = getattr(request.user, "profile", None)
        if profile:
            profile.postman_api_key = api_key
            profile.save(update_fields=["postman_api_key"])
    from portal.services.postman_sync import fetch_postman_collections
    result = fetch_postman_collections(api_key)
    if not result.get("success"):
        return JsonResponse(result, status=400)
    return JsonResponse(result)


@login_required
@require_http_methods(["POST"])
def postman_save_key_view(request):
    """
    POST: Save Postman API key to user profile.
    Body (JSON): { "api_key": "..." }
    """
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({"success": False, "error": "permission_denied"}, status=403)
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)
    api_key = (data.get("api_key") or "").strip()
    if not api_key:
        return JsonResponse({"success": False, "error": "api_key is required."}, status=400)
    profile = getattr(request.user, "profile", None)
    if not profile:
        return JsonResponse({"success": False, "error": "User profile not found."}, status=400)
    profile.postman_api_key = api_key
    profile.save(update_fields=["postman_api_key"])
    return JsonResponse({"success": True, "message": "Postman API key saved."})


class ApiVendorDetailView(DetailView):
    """Detail view for one API vendor and its APIs."""
    model = ApiVendor
    template_name = 'portal/services/api_vendor_detail.html'
    context_object_name = 'vendor'
    slug_url_kwarg = 'vendor_code'
    slug_field = 'code'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect('/signin/')
        if self.request.user.role_code not in ['super_admin', 'admin']:
            messages.error(self.request, 'You do not have permission to view API vendors.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return ApiVendor.objects.prefetch_related('apis')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_vendors'] = ApiVendor.objects.all().order_by('name').prefetch_related('apis')
        return context


class ServiceDetailByCodeView(LoginRequiredMixin, View):
    """Redirect /services/<code>/ (e.g. /services/bbps/) to service detail by id."""
    def dispatch(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect('/signin/')
        if self.request.user.role_code not in ['super_admin', 'admin']:
            messages.error(self.request, 'You do not have permission to view services.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)

    def get(self, request, service_code):
        service = Service.objects.filter(code__iexact=service_code).first()
        if not service:
            raise Http404('Service not found')
        return redirect('service_detail', service_id=service.id)


class ServiceDetailView(DetailView):
    """View to show service details and vendor integrations"""
    model = Service
    template_name = 'portal/services/detail.html'
    context_object_name = 'service'
    pk_url_kwarg = 'service_id'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        # Only admin and super can access services
        if not self.request.user.is_authenticated:
            return redirect('/signin/')
        if self.request.user.role_code not in ['super_admin', 'admin']:
            messages.error(self.request, 'You do not have permission to view services.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self.get_object()
        
        # Get available vendors and their services for this service
        if service.code == 'VERIFICATION_API':
            from portal.models import CashfreeAPILog
            from django.utils import timezone
            from datetime import timedelta
            
            # Get vendor service configurations from Service model (stored in vendor_config JSON field)
            vendor_config = service.vendor_config if service.vendor_config else {}
            cashfree_services = vendor_config.get('cashfree', {})
            
            # Define all available Cashfree APIs with their details
            all_apis = [
                # Basic Document Verification
                {'code': 'pan', 'name': 'PAN Verification', 'icon': 'ti-file-check', 'description': 'Verify PAN card details'},
                {'code': 'aadhaar', 'name': 'Aadhaar Verification', 'icon': 'ti-id', 'description': 'Verify Aadhaar card details'},
                {'code': 'bank', 'name': 'Bank Account Verification', 'icon': 'ti-building-bank', 'description': 'Verify bank account details'},
                {'code': 'phone', 'name': 'Phone Verification', 'icon': 'ti-phone', 'description': 'Verify phone number'},
                {'code': 'email', 'name': 'Email Verification', 'icon': 'ti-mail', 'description': 'Verify email address'},
                {'code': 'driving_license', 'name': 'Driving License', 'icon': 'ti-license', 'description': 'Verify driving license details'},
                {'code': 'voter_id', 'name': 'Voter ID Verification', 'icon': 'ti-id-badge', 'description': 'Verify Voter ID card details'},
                {'code': 'passport', 'name': 'Passport Verification', 'icon': 'ti-passport', 'description': 'Verify passport details'},
                {'code': 'gst', 'name': 'GST Verification', 'icon': 'ti-receipt', 'description': 'Verify GSTIN (GST Identification Number)'},
                {'code': 'cin', 'name': 'CIN Verification', 'icon': 'ti-building', 'description': 'Verify Corporate Identification Number'},
                {'code': 'ifsc', 'name': 'IFSC Verification', 'icon': 'ti-building-bank', 'description': 'Verify IFSC code and get bank branch details'},
                {'code': 'vehicle_rc', 'name': 'Vehicle RC Verification', 'icon': 'ti-car', 'description': 'Verify vehicle registration certificate'},
                
                # Advanced Aadhaar APIs
                {'code': 'aadhaar_ocr', 'name': 'Aadhaar OCR', 'icon': 'ti-scan', 'description': 'Extract data from Aadhaar card image using OCR'},
                {'code': 'aadhaar_masking', 'name': 'Aadhaar Masking', 'icon': 'ti-shield', 'description': 'Mask Aadhaar number for privacy'},
                {'code': 'offline_aadhaar_send_otp', 'name': 'Offline Aadhaar Send OTP', 'icon': 'ti-message', 'description': 'Send OTP to registered mobile for offline Aadhaar verification'},
                {'code': 'offline_aadhaar_verify_otp', 'name': 'Offline Aadhaar Verify OTP', 'icon': 'ti-key', 'description': 'Verify OTP and get Aadhaar details'},
                
                # Advanced PAN APIs
                {'code': 'pan_advance', 'name': 'PAN Advance', 'icon': 'ti-file-info', 'description': 'Get detailed PAN information including address'},
                {'code': 'pan_ocr', 'name': 'PAN OCR', 'icon': 'ti-scan', 'description': 'Extract data from PAN card image using OCR'},
                {'code': 'pan_to_gstin', 'name': 'PAN to GSTIN', 'icon': 'ti-link', 'description': 'Get all GSTINs associated with a PAN'},
                {'code': 'pan_bulk', 'name': 'Bulk PAN Verification', 'icon': 'ti-files', 'description': 'Verify multiple PANs in a single request'},
                
                # DigiLocker APIs
                {'code': 'digilocker_create_url', 'name': 'DigiLocker Create URL', 'icon': 'ti-external-link', 'description': 'Create URL for DigiLocker authentication'},
                {'code': 'digilocker_get_status', 'name': 'DigiLocker Get Status', 'icon': 'ti-info-circle', 'description': 'Get DigiLocker verification status'},
                {'code': 'digilocker_get_document', 'name': 'DigiLocker Get Document', 'icon': 'ti-file-download', 'description': 'Get specific document from DigiLocker'},
                
                # E-sign APIs
                {'code': 'esign_create_signature', 'name': 'E-sign Create Signature', 'icon': 'ti-signature', 'description': 'Create signature request for document'},
                {'code': 'esign_get_status', 'name': 'E-sign Get Status', 'icon': 'ti-info-circle', 'description': 'Get e-signature status'},
                {'code': 'esign_upload_document', 'name': 'E-sign Upload Document', 'icon': 'ti-upload', 'description': 'Upload document for e-signing'},
                
                # Advanced Verification APIs
                {'code': 'advance_employment', 'name': 'Advance Employment', 'icon': 'ti-briefcase', 'description': 'Get employment details from EPFO/UAN'},
                {'code': 'reverse_penny_drop', 'name': 'Reverse Penny Drop', 'icon': 'ti-currency-rupee', 'description': 'Verify bank account by depositing small amount'},
                {'code': 'reverse_penny_drop_status', 'name': 'Reverse Penny Drop Status', 'icon': 'ti-info-circle', 'description': 'Get reverse penny drop transaction status'},
                {'code': 'reverse_geocoding', 'name': 'Reverse Geocoding', 'icon': 'ti-map-pin', 'description': 'Get address from coordinates'},
                {'code': 'ip_verification', 'name': 'IP Verification', 'icon': 'ti-network', 'description': 'Verify IP address location and details'},
                
                # Biometric KYC APIs
                {'code': 'face_liveness', 'name': 'Face Liveness', 'icon': 'ti-fingerprint', 'description': 'Detect live human presence and prevent spoofing'},
                {'code': 'face_match', 'name': 'Face Match', 'icon': 'ti-user-check', 'description': 'Compare facial features between images'},
                {'code': 'name_match', 'name': 'Name Match', 'icon': 'ti-abc', 'description': 'Verify names with variations and fuzzy matching'},
                
                # OCR APIs
                {'code': 'smart_ocr', 'name': 'Smart OCR', 'icon': 'ti-scan', 'description': 'Extract and verify data from documents'},
            ]
            
            # Check status for each API (based on recent logs - last 24 hours)
            last_24h = timezone.now() - timedelta(hours=24)
            for api in all_apis:
                api_code = api['code']
                # Get default enabled status from config or default to True
                api['enabled'] = cashfree_services.get(api_code, {}).get('enabled', True)
                
                # Check if API is working (has successful calls in last 24h)
                # For VERIFICATION_API service, we know it's Cashfree
                recent_success = CashfreeAPILog.objects.filter(
                    api_type=api_code,
                    status='success',
                    timestamp__gte=last_24h
                ).exists()
                
                # Check if API has errors in last 24h
                recent_errors = CashfreeAPILog.objects.filter(
                    api_type=api_code,
                    status='error',
                    timestamp__gte=last_24h
                ).exists()
                
                # Determine status
                if recent_success:
                    api['status'] = 'working'
                    api['status_color'] = 'green'
                elif recent_errors:
                    api['status'] = 'error'
                    api['status_color'] = 'red'
                else:
                    api['status'] = 'unknown'
                    api['status_color'] = 'gray'
            
            context['vendors'] = [
                {
                    'name': 'Cashfree',
                    'code': 'cashfree',
                    'icon': 'ti ti-building-store',
                    'description': 'Cashfree Verification API - Document and identity verification',
                    'status': 'available',
                    'services': all_apis,
                },
                {
                    'name': 'Leegality',
                    'code': 'leegality',
                    'icon': 'ti ti-file-signature',
                    'description': 'Leegality API - Document signing and stamp paper management',
                    'status': 'available',
                }
            ]
        elif service.code == 'SMS_IVR_GATEWAY':
            # Get vendor service configurations
            vendor_config = service.vendor_config if service.vendor_config else {}
            
            # Define available vendors for SMS/IVR Gateway
            vendors = []
            
            # Kaleyra vendor
            kaleyra_services = vendor_config.get('kaleyra', {})
            vendors.append({
                'name': 'Kaleyra',
                'code': 'kaleyra',
                'icon': 'ti ti-message',
                'description': 'Kaleyra SMS and IVR Gateway - Send SMS, OTP, and manage IVR calls',
                'status': 'available',
                'services': [
                    {'code': 'sms', 'name': 'Send SMS', 'enabled': kaleyra_services.get('sms', {}).get('enabled', True)},
                    {'code': 'template_sms', 'name': 'Template SMS', 'enabled': kaleyra_services.get('template_sms', {}).get('enabled', True)},
                    {'code': 'click_to_call', 'name': 'Click to Call', 'enabled': kaleyra_services.get('click_to_call', {}).get('enabled', True)},
                ]
            })
            
            context['vendors'] = vendors
        elif service.code == 'PAYMENT_GATEWAY':
            # Get vendor service configurations
            vendor_config = service.vendor_config if service.vendor_config else {}
            
            # Define available vendors for Payment Gateway
            vendors = []
            
            # Cashfree PG vendor
            cashfree_pg_services = vendor_config.get('cashfree_pg', {})
            vendors.append({
                'name': 'Cashfree PG',
                'code': 'cashfree_pg',
                'icon': 'ti ti-credit-card',
                'description': 'Cashfree Payment Gateway - Process payments, create orders, manage refunds',
                'status': 'available',
                'services': [
                    {'code': 'create_order', 'name': 'Create Order', 'enabled': cashfree_pg_services.get('create_order', {}).get('enabled', True)},
                    {'code': 'get_order', 'name': 'Get Order', 'enabled': cashfree_pg_services.get('get_order', {}).get('enabled', True)},
                    {'code': 'create_refund', 'name': 'Create Refund', 'enabled': cashfree_pg_services.get('create_refund', {}).get('enabled', True)},
                    {'code': 'get_refund', 'name': 'Get Refund', 'enabled': cashfree_pg_services.get('get_refund', {}).get('enabled', True)},
                    {'code': 'get_payment', 'name': 'Get Payment', 'enabled': cashfree_pg_services.get('get_payment', {}).get('enabled', True)},
                    {'code': 'create_payment_link', 'name': 'Create Payment Link', 'enabled': cashfree_pg_services.get('create_payment_link', {}).get('enabled', True)},
                    {'code': 'get_payment_link', 'name': 'Get Payment Link', 'enabled': cashfree_pg_services.get('get_payment_link', {}).get('enabled', True)},
                ]
            })
            
            context['vendors'] = vendors
        elif service.code == 'BBPS':
            # BBPS - Mobikwik and Euronet vendors
            vendor_config = service.vendor_config if service.vendor_config else {}
            mobikwik_configured = False
            euronet_configured = False
            try:
                from portal.services.vendors.mobikwik import MobikwikBBPSClient
                mobikwik_configured = MobikwikBBPSClient().is_configured()
            except Exception:
                pass
            try:
                from portal.services.vendors.euronet import EuronetBBPSClient
                euronet_configured = EuronetBBPSClient().is_configured()
            except Exception:
                pass
            context['vendors'] = [
                {
                    'name': 'Mobikwik',
                    'code': 'mobikwik',
                    'icon': 'ti ti-building-store',
                    'description': 'Mobikwik BBPS - Bharat Bill Payment System (bill fetch, pay, operators)',
                    'status': 'available' if mobikwik_configured else 'pending',
                    'services': [
                        {'code': 'operators', 'name': 'Operators / Billers', 'enabled': True},
                        {'code': 'fetch_bill', 'name': 'Fetch Bill', 'enabled': True},
                        {'code': 'pay_bill', 'name': 'Pay Bill', 'enabled': True},
                        {'code': 'payment_status', 'name': 'Payment Status', 'enabled': True},
                    ]
                },
                {
                    'name': 'Euronet',
                    'code': 'euronet',
                    'icon': 'ti ti-world',
                    'description': 'Euronet BBPS (Bharat Connect) - Bharat Bill Payment System (bill fetch, pay, operators)',
                    'status': 'available' if euronet_configured else 'pending',
                    'services': [
                        {'code': 'operators', 'name': 'Operators / Billers', 'enabled': True},
                        {'code': 'fetch_bill', 'name': 'Fetch Bill', 'enabled': True},
                        {'code': 'pay_bill', 'name': 'Pay Bill', 'enabled': True},
                        {'code': 'payment_status', 'name': 'Payment Status', 'enabled': True},
                    ]
                },
            ]
        elif service.code == 'AEPS':
            # AEPS – PayPoint only. Not used by Parkpe (Payswap / future).
            try:
                from portal.services.vendors.paypoint import PayPointAEPSClient
                client = PayPointAEPSClient()
                aeps_configured = client.is_configured()
            except Exception:
                aeps_configured = False
            context['vendors'] = [
                {
                    'name': 'PayPoint',
                    'code': 'paypoint',
                    'icon': 'ti ti-fingerprint',
                    'description': 'PayPoint AEPS - Aadhaar Enabled Payment System (balance, withdrawal, mini statement)',
                    'status': 'available' if aeps_configured else 'pending',
                    'services': [
                        {'code': 'balance_enquiry', 'name': 'Balance Enquiry', 'enabled': True},
                        {'code': 'cash_withdrawal', 'name': 'Cash Withdrawal', 'enabled': True},
                        {'code': 'mini_statement', 'name': 'Mini Statement', 'enabled': True},
                        {'code': 'transaction_status', 'name': 'Transaction Status', 'enabled': True},
                        {'code': 'agent_registration', 'name': 'Agent Registration', 'enabled': True},
                        {'code': 'update_agent_details', 'name': 'Update Agent Details', 'enabled': True},
                        {'code': 'agent_service_status', 'name': 'Check Agent Service Status', 'enabled': True},
                        {'code': 'agent_authentication', 'name': 'Check Agent Authentication', 'enabled': True},
                        {'code': 'two_factor_authentication', 'name': 'Two Factor Authentication', 'enabled': True},
                    ]
                }
            ]
        elif service.code == 'INSTANTPAY':
            try:
                from portal.services.vendors.instantpay import InstantpayClient
                client = InstantpayClient()
                configured = client.is_configured()
            except Exception:
                configured = False
            context['vendors'] = [
                {
                    'name': 'Instantpay',
                    'code': 'instantpay',
                    'icon': 'ti ti-api',
                    'description': 'Instantpay API - Identity, Banking, Payouts, AePS, Collect, Tax, AI/ML (developers.instantpay.in)',
                    'status': 'available' if configured else 'pending',
                }
            ]
        else:
            context['vendors'] = []
        
        # Service Flow (orchestration): ordered steps from ServiceFlowStep (data-driven)
        context['flow_steps'] = list(
            service.flow_steps.select_related('vendor', 'vendor_api').order_by('step_order')
        )
        
        return context


class VendorDetailView(LoginRequiredMixin, View):
    """Vendor detail view - shows all services for a specific vendor"""
    
    def dispatch(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect('/signin/')
        if self.request.user.role_code not in ['super_admin', 'admin']:
            messages.error(self.request, 'You do not have permission to view vendors.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, service_id, vendor_code):
        from portal.models import Service, CashfreeAPILog, LogEntry
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            service = Service.objects.get(id=service_id)
        except Service.DoesNotExist:
            messages.error(request, 'Service not found.')
            return redirect('services_list')
        
        if service.code not in ['VERIFICATION_API', 'SMS_IVR_GATEWAY', 'PAYMENT_GATEWAY', 'BBPS', 'INSTANTPAY']:
            messages.error(request, 'Invalid service.')
            return redirect('service_detail', service_id=service_id)
        
        # Get vendor info
        vendor_info = None
        if vendor_code == 'mobikwik' and service.code == 'BBPS':
            try:
                from portal.services.vendors.mobikwik import MobikwikBBPSClient
                client = MobikwikBBPSClient()
                configured = client.is_configured()
            except Exception:
                configured = False
            vendor_info = {
                'name': 'Mobikwik',
                'code': 'mobikwik',
                'icon': 'ti ti-building-store',
                'description': 'Mobikwik BBPS - Bharat Bill Payment System. Bill fetch, pay, operators.',
                'status': 'available' if configured else 'pending',
                'documentation_url': 'https://www.mobikwik.com/bbps',
            }
        elif vendor_code == 'euronet' and service.code == 'BBPS':
            try:
                from portal.services.vendors.euronet import EuronetBBPSClient
                client = EuronetBBPSClient()
                configured = client.is_configured()
            except Exception:
                configured = False
            vendor_info = {
                'name': 'Euronet',
                'code': 'euronet',
                'icon': 'ti ti-world',
                'description': 'Euronet BBPS (Bharat Connect) - Bharat Bill Payment System. Bill fetch, pay, operators.',
                'status': 'available' if configured else 'pending',
                'documentation_url': None,
            }
        elif vendor_code == 'cashfree':
            vendor_info = {
                'name': 'Cashfree',
                'code': 'cashfree',
                'icon': 'ti ti-building-store',
                'description': 'Cashfree Verification API - Document and identity verification',
                'status': 'available',
                'documentation_url': 'https://www.cashfree.com/docs/secure-id/introduction'
            }
        elif vendor_code == 'kaleyra':
            vendor_info = {
                'name': 'Kaleyra',
                'code': 'kaleyra',
                'icon': 'ti ti-message',
                'description': 'Kaleyra SMS and IVR Gateway - Send SMS, OTP, and manage IVR calls',
                'status': 'available',
                'documentation_url': 'https://developers.kaleyra.io/docs'
            }
        elif vendor_code == 'cashfree_pg':
            vendor_info = {
                'name': 'Cashfree PG',
                'code': 'cashfree_pg',
                'icon': 'ti ti-credit-card',
                'description': 'Cashfree Payment Gateway - Process payments, create orders, manage refunds',
                'status': 'available',
                'documentation_url': 'https://docs.cashfree.com/reference/pg-new-apis-endpoint'
            }
        elif vendor_code == 'instantpay' and service.code == 'INSTANTPAY':
            try:
                from portal.services.vendors.instantpay import InstantpayClient
                client = InstantpayClient()
                configured = client.is_configured()
            except Exception:
                configured = False
            vendor_info = {
                'name': 'Instantpay',
                'code': 'instantpay',
                'icon': 'ti ti-api',
                'description': 'Instantpay API - Identity, Banking, Payouts, AePS, Collect, Tax, AI/ML (developers.instantpay.in)',
                'status': 'available' if configured else 'pending',
                'documentation_url': 'https://developers.instantpay.in/',
            }
        else:
            messages.error(request, 'Vendor not found.')
            return redirect('service_detail', service_id=service_id)
        
        # Get vendor service configurations
        vendor_config = service.vendor_config if service.vendor_config else {}
        vendor_services_config = vendor_config.get(vendor_code, {})
        
        # Get bridge numbers for Kaleyra and initialize if not exists
        bridge_numbers = []
        ivr_bridge_numbers = []
        sms_bridge_numbers = []
        if vendor_code == 'kaleyra':
            if 'bridge_numbers' not in vendor_services_config or not vendor_services_config.get('bridge_numbers'):
                # Initialize with default IVR bridge numbers
                default_bridge_numbers = [
                    {'number': '+917314500355', 'type': 'ivr'},
                    {'number': '+911414761236', 'type': 'ivr'},
                    {'number': '+917314500351', 'type': 'ivr'}
                ]
                vendor_services_config['bridge_numbers'] = default_bridge_numbers
                vendor_config[vendor_code] = vendor_services_config
                service.vendor_config = vendor_config
                service.save(update_fields=['vendor_config'])
                bridge_numbers = default_bridge_numbers
            else:
                bridge_numbers = vendor_services_config.get('bridge_numbers', [])
            
            # Separate IVR and SMS bridge numbers
            # Handle both old format (list of strings) and new format (list of dicts)
            for bridge in bridge_numbers:
                if isinstance(bridge, dict):
                    if bridge.get('type') == 'ivr':
                        ivr_bridge_numbers.append(bridge.get('number'))
                    elif bridge.get('type') == 'sms':
                        sms_bridge_numbers.append(bridge.get('number'))
                else:
                    # Old format - treat as IVR for backward compatibility
                    ivr_bridge_numbers.append(bridge)
        
        # Define all available APIs for this vendor
        all_apis = []
        if vendor_code == 'cashfree':
            all_apis = [
                # Basic Document Verification
                {'code': 'pan', 'name': 'PAN Verification', 'icon': 'ti-file-check', 'description': 'Verify PAN card details'},
                {'code': 'aadhaar', 'name': 'Aadhaar Verification', 'icon': 'ti-id', 'description': 'Verify Aadhaar card details'},
                {'code': 'bank', 'name': 'Bank Account Verification', 'icon': 'ti-building-bank', 'description': 'Verify bank account details'},
                {'code': 'phone', 'name': 'Phone Verification', 'icon': 'ti-phone', 'description': 'Verify phone number'},
                {'code': 'email', 'name': 'Email Verification', 'icon': 'ti-mail', 'description': 'Verify email address'},
                {'code': 'driving_license', 'name': 'Driving License', 'icon': 'ti-license', 'description': 'Verify driving license details'},
                {'code': 'voter_id', 'name': 'Voter ID Verification', 'icon': 'ti-id-badge', 'description': 'Verify Voter ID card details'},
                {'code': 'passport', 'name': 'Passport Verification', 'icon': 'ti-passport', 'description': 'Verify passport details'},
                {'code': 'gst', 'name': 'GST Verification', 'icon': 'ti-receipt', 'description': 'Verify GSTIN (GST Identification Number)'},
                {'code': 'cin', 'name': 'CIN Verification', 'icon': 'ti-building', 'description': 'Verify Corporate Identification Number'},
                {'code': 'ifsc', 'name': 'IFSC Verification', 'icon': 'ti-building-bank', 'description': 'Verify IFSC code and get bank branch details'},
                {'code': 'vehicle_rc', 'name': 'Vehicle RC Verification', 'icon': 'ti-car', 'description': 'Verify vehicle registration certificate'},
                
                # Advanced Aadhaar APIs
                {'code': 'aadhaar_ocr', 'name': 'Aadhaar OCR', 'icon': 'ti-scan', 'description': 'Extract data from Aadhaar card image using OCR'},
                {'code': 'aadhaar_masking', 'name': 'Aadhaar Masking', 'icon': 'ti-shield', 'description': 'Mask Aadhaar number for privacy'},
                {'code': 'offline_aadhaar_send_otp', 'name': 'Offline Aadhaar Send OTP', 'icon': 'ti-message', 'description': 'Send OTP to registered mobile for offline Aadhaar verification'},
                {'code': 'offline_aadhaar_verify_otp', 'name': 'Offline Aadhaar Verify OTP', 'icon': 'ti-key', 'description': 'Verify OTP and get Aadhaar details'},
                
                # Advanced PAN APIs
                {'code': 'pan_advance', 'name': 'PAN Advance', 'icon': 'ti-file-info', 'description': 'Get detailed PAN information including address'},
                {'code': 'pan_ocr', 'name': 'PAN OCR', 'icon': 'ti-scan', 'description': 'Extract data from PAN card image using OCR'},
                {'code': 'pan_to_gstin', 'name': 'PAN to GSTIN', 'icon': 'ti-link', 'description': 'Get all GSTINs associated with a PAN'},
                {'code': 'pan_bulk', 'name': 'Bulk PAN Verification', 'icon': 'ti-files', 'description': 'Verify multiple PANs in a single request'},
                
                # DigiLocker APIs
                {'code': 'digilocker_create_url', 'name': 'DigiLocker Create URL', 'icon': 'ti-external-link', 'description': 'Create URL for DigiLocker authentication'},
                {'code': 'digilocker_get_status', 'name': 'DigiLocker Get Status', 'icon': 'ti-info-circle', 'description': 'Get DigiLocker verification status'},
                {'code': 'digilocker_get_document', 'name': 'DigiLocker Get Document', 'icon': 'ti-file-download', 'description': 'Get specific document from DigiLocker'},
                
                # E-sign APIs
                {'code': 'esign_create_signature', 'name': 'E-sign Create Signature', 'icon': 'ti-signature', 'description': 'Create signature request for document'},
                {'code': 'esign_get_status', 'name': 'E-sign Get Status', 'icon': 'ti-info-circle', 'description': 'Get e-signature status'},
                {'code': 'esign_upload_document', 'name': 'E-sign Upload Document', 'icon': 'ti-upload', 'description': 'Upload document for e-signing'},
                
                # Advanced Verification APIs
                {'code': 'advance_employment', 'name': 'Advance Employment', 'icon': 'ti-briefcase', 'description': 'Get employment details from EPFO/UAN'},
                {'code': 'reverse_penny_drop', 'name': 'Reverse Penny Drop', 'icon': 'ti-currency-rupee', 'description': 'Verify bank account by depositing small amount'},
                {'code': 'reverse_penny_drop_status', 'name': 'Reverse Penny Drop Status', 'icon': 'ti-info-circle', 'description': 'Get reverse penny drop transaction status'},
                {'code': 'reverse_geocoding', 'name': 'Reverse Geocoding', 'icon': 'ti-map-pin', 'description': 'Get address from coordinates'},
                {'code': 'ip_verification', 'name': 'IP Verification', 'icon': 'ti-network', 'description': 'Verify IP address location and details'},
                
                # Biometric KYC APIs
                {'code': 'face_liveness', 'name': 'Face Liveness', 'icon': 'ti-fingerprint', 'description': 'Detect live human presence and prevent spoofing'},
                {'code': 'face_match', 'name': 'Face Match', 'icon': 'ti-user-check', 'description': 'Compare facial features between images'},
                {'code': 'name_match', 'name': 'Name Match', 'icon': 'ti-abc', 'description': 'Verify names with variations and fuzzy matching'},
                
                # OCR APIs
                {'code': 'smart_ocr', 'name': 'Smart OCR', 'icon': 'ti-scan', 'description': 'Extract and verify data from documents'},
            ]
        elif vendor_code == 'leegality':
            # Define Leegality APIs
            all_apis = [
                {'code': 'create_document', 'name': 'Create Document', 'icon': 'ti-file-plus', 'description': 'Create a document for signing'},
                {'code': 'get_document_status', 'name': 'Get Document Status', 'icon': 'ti-info-circle', 'description': 'Get status of a document'},
                {'code': 'create_stamp_paper', 'name': 'Create Stamp Paper', 'icon': 'ti-stamp', 'description': 'Create stamp paper for document'},
                {'code': 'get_stamp_status', 'name': 'Get Stamp Status', 'icon': 'ti-info-circle', 'description': 'Get stamp paper status'},
                {'code': 'download_document', 'name': 'Download Document', 'icon': 'ti-download', 'description': 'Download signed document'},
                {'code': 'get_audit_trail', 'name': 'Get Audit Trail', 'icon': 'ti-history', 'description': 'Get document audit trail'},
            ]
            
            # Get vendor service configurations
            vendor_config = service.vendor_config if service.vendor_config else {}
            leegality_services = vendor_config.get('leegality', {})
            
            # Check status for each API (based on recent logs - last 24 hours)
            last_24h = timezone.now() - timedelta(hours=24)
            for api in all_apis:
                api_code = api['code']
                # Get default enabled status from config or default to True
                api['enabled'] = leegality_services.get(api_code, {}).get('enabled', True)
                
                # Check if API is working (has successful calls in last 24h)
                recent_success = LogEntry.objects.filter(
                    category='leegality',
                    log_level='INFO',
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
                
                # Check if API has errors in last 24h
                recent_errors = LogEntry.objects.filter(
                    category='leegality',
                    log_level__in=['ERROR', 'WARNING'],
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
                
                # Determine status
                if recent_success:
                    api['status'] = 'working'
                    api['status_color'] = 'green'
                elif recent_errors:
                    api['status'] = 'error'
                    api['status_color'] = 'red'
                else:
                    api['status'] = 'unknown'
                    api['status_color'] = 'gray'
        elif vendor_code == 'cashfree_pg':
            # Define Cashfree PG APIs
            all_apis = [
                {'code': 'create_order', 'name': 'Create Order', 'icon': 'ti-shopping-cart-plus', 'description': 'Create a payment order'},
                {'code': 'get_order', 'name': 'Get Order', 'icon': 'ti-info-circle', 'description': 'Get order details'},
                {'code': 'create_refund', 'name': 'Create Refund', 'icon': 'ti-currency-rupee', 'description': 'Create a refund for an order'},
                {'code': 'get_refund', 'name': 'Get Refund', 'icon': 'ti-info-circle', 'description': 'Get refund details'},
                {'code': 'get_payment', 'name': 'Get Payment', 'icon': 'ti-receipt', 'description': 'Get payment details'},
                {'code': 'create_payment_link', 'name': 'Create Payment Link', 'icon': 'ti-link', 'description': 'Create a payment link'},
                {'code': 'get_payment_link', 'name': 'Get Payment Link', 'icon': 'ti-info-circle', 'description': 'Get payment link details'},
            ]
            
            # Get vendor service configurations
            vendor_config = service.vendor_config if service.vendor_config else {}
            cashfree_pg_services = vendor_config.get('cashfree_pg', {})
            
            # Check status for each API (based on recent logs - last 24 hours)
            last_24h = timezone.now() - timedelta(hours=24)
            for api in all_apis:
                api_code = api['code']
                # Get default enabled status from config or default to True
                api['enabled'] = cashfree_pg_services.get(api_code, {}).get('enabled', True)
                
                # Check if API is working (has successful calls in last 24h)
                recent_success = LogEntry.objects.filter(
                    category='cashfree_pg',
                    log_level='INFO',
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
                
                # Check if API has errors in last 24h
                recent_errors = LogEntry.objects.filter(
                    category='cashfree_pg',
                    log_level__in=['ERROR', 'WARNING'],
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
                
                # Determine status
                if recent_success:
                    api['status'] = 'working'
                    api['status_color'] = 'green'
                elif recent_errors:
                    api['status'] = 'error'
                    api['status_color'] = 'red'
                else:
                    api['status'] = 'unknown'
                    api['status_color'] = 'gray'
        elif vendor_code == 'kaleyra':
            # Define Kaleyra APIs
            all_apis = [
                {'code': 'sms', 'name': 'Send SMS', 'icon': 'ti-message', 'description': 'Send transactional or promotional SMS'},
                {'code': 'template_sms', 'name': 'Template SMS', 'icon': 'ti-file-text', 'description': 'Send SMS using DLT templates with variables'},
                {'code': 'click_to_call', 'name': 'Click to Call', 'icon': 'ti-phone-call', 'description': 'Initiate voice call connecting two numbers'},
            ]
        elif vendor_code == 'mobikwik' and service.code == 'BBPS':
            all_apis = [
                {'code': 'operators', 'name': 'Operators / Billers', 'icon': 'ti-list', 'description': 'Get list of BBPS operators/billers'},
                {'code': 'fetch_bill', 'name': 'Fetch Bill', 'icon': 'ti-file-search', 'description': 'Fetch bill details for a consumer'},
                {'code': 'pay_bill', 'name': 'Pay Bill', 'icon': 'ti-currency-rupee', 'description': 'Pay a bill'},
                {'code': 'payment_status', 'name': 'Payment Status', 'icon': 'ti-info-circle', 'description': 'Get payment status by reference id'},
            ]
        elif vendor_code == 'euronet' and service.code == 'BBPS':
            all_apis = [
                {'code': 'operators', 'name': 'Operators / Billers', 'icon': 'ti-list', 'description': 'Get list of BBPS operators/billers'},
                {'code': 'fetch_bill', 'name': 'Fetch Bill', 'icon': 'ti-file-search', 'description': 'Fetch bill details for a consumer'},
                {'code': 'pay_bill', 'name': 'Pay Bill', 'icon': 'ti-currency-rupee', 'description': 'Pay a bill'},
                {'code': 'payment_status', 'name': 'Payment Status', 'icon': 'ti-info-circle', 'description': 'Get payment status by reference id'},
            ]
        elif vendor_code == 'instantpay' and service.code == 'INSTANTPAY':
            from portal.services.vendors.instantpay import INSTANTPAY_API_CATEGORIES
            all_apis = []
            for cat in INSTANTPAY_API_CATEGORIES:
                for api in cat['apis']:
                    all_apis.append({
                        'code': api['code'],
                        'name': api['name'],
                        'icon': api.get('icon', 'ti-api'),
                        'description': f"{cat['name']} – {api['method']}",
                    })
        
        # Check status for each API (based on recent logs - last 24 hours)
        last_24h = timezone.now() - timedelta(hours=24)
        for api in all_apis:
            api_code = api['code']
            # Get default enabled status from config or default to True
            api['enabled'] = vendor_services_config.get(api_code, {}).get('enabled', True)
            
            # Check if API is working (has successful calls in last 24h)
            if vendor_code == 'cashfree':
                recent_success = CashfreeAPILog.objects.filter(
                    api_type=api_code,
                    status='success',
                    timestamp__gte=last_24h
                ).exists()
                
                # Check if API has errors in last 24h
                recent_errors = CashfreeAPILog.objects.filter(
                    api_type=api_code,
                    status='error',
                    timestamp__gte=last_24h
                ).exists()
            elif vendor_code == 'kaleyra':
                # For Kaleyra, check LogEntry with category 'kaleyra'
                from portal.models import LogEntry
                recent_success = LogEntry.objects.filter(
                    category='kaleyra',
                    log_level='INFO',
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
                
                recent_errors = LogEntry.objects.filter(
                    category='kaleyra',
                    log_level__in=['ERROR', 'WARNING'],
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
            elif vendor_code == 'leegality':
                recent_success = LogEntry.objects.filter(
                    category='leegality',
                    log_level='INFO',
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
                
                recent_errors = LogEntry.objects.filter(
                    category='leegality',
                    log_level__in=['ERROR', 'WARNING'],
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
            elif vendor_code == 'cashfree_pg':
                recent_success = LogEntry.objects.filter(
                    category='cashfree_pg',
                    log_level='INFO',
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
                
                recent_errors = LogEntry.objects.filter(
                    category='cashfree_pg',
                    log_level__in=['ERROR', 'WARNING'],
                    message__icontains=api_code,
                    timestamp__gte=last_24h
                ).exists()
            else:
                recent_success = False
                recent_errors = False
            
            # Determine status
            if recent_success:
                api['status'] = 'working'
                api['status_color'] = 'green'
            elif recent_errors:
                api['status'] = 'error'
                api['status_color'] = 'red'
            else:
                api['status'] = 'unknown'
                api['status_color'] = 'gray'
        
        # Load DLT templates for Kaleyra
        dlt_templates = []
        if vendor_code == 'kaleyra':
            from portal.utils.template_loader import load_dlt_templates
            dlt_templates = load_dlt_templates()
        
        # Select template based on vendor
        if vendor_code == 'kaleyra':
            template_name = 'portal/services/kaleyra_vendor_detail.html'
        elif vendor_code == 'cashfree':
            template_name = 'portal/services/cashfree_vendor_detail.html'
        elif vendor_code == 'cashfree_pg':
            template_name = 'portal/services/cashfree_pg_vendor_detail.html'
        elif vendor_code == 'mobikwik':
            template_name = 'portal/services/mobikwik_vendor_detail.html'
        else:
            template_name = 'portal/services/vendor_detail.html'
        
        context = {
            'service': service,
            'vendor': vendor_info,
            'apis': all_apis,
            'bridge_numbers': bridge_numbers if vendor_code == 'kaleyra' else [],
            'ivr_bridge_numbers': ivr_bridge_numbers if vendor_code == 'kaleyra' else [],
            'sms_bridge_numbers': sms_bridge_numbers if vendor_code == 'kaleyra' else [],
            'dlt_templates': dlt_templates,
        }
        if vendor_code == 'mobikwik' and getattr(service, 'code', None) == 'BBPS':
            try:
                from portal.services.bbps_operators_loader import get_bbps_categories
                context['bbps_categories'] = get_bbps_categories()
            except Exception:
                context['bbps_categories'] = []

        # Test parameters (optional overrides) for save/edit and Test all APIs; pre-fill from env where not saved
        vendor_config = getattr(service, 'vendor_config', None) or {}
        test_params = vendor_config.get(vendor_code, {}).get('test_params') or {}
        env_defaults = _get_env_defaults_for_vendor_test_params(vendor_code)
        context['vendor_test_params'] = test_params
        schema = _get_vendor_test_params_schema(vendor_code)
        context['vendor_test_params_schema'] = [
            {**f, 'value': test_params.get(f['key']) if f['key'] in test_params else env_defaults.get(f['key'], '')} for f in schema
        ]
        context['vendor_code'] = vendor_code

        return render(request, template_name, context)


def _get_env_defaults_for_vendor_test_params(vendor_code):
    """Return dict of param key -> value from env/config for pre-filling vendor test forms."""
    try:
        from core.config import payswap_config
    except Exception:
        return {}
    out = {}
    if vendor_code == 'mobikwik':
        for attr, key in [
            ('MOBIKWIK_BBPS_CLIENT_ID', 'client_id'),
            ('MOBIKWIK_BBPS_MERCHANT_ID', 'merchant_id'),
        ]:
            v = getattr(payswap_config, attr, None)
            if v is not None:
                out[key] = (v.get_secret_value() if hasattr(v, 'get_secret_value') else str(v)) or ''
        base = getattr(payswap_config, 'MOBIKWIK_BBPS_BASE_URL', None)
        if base is not None:
            out['base_url'] = str(base) or ''
        for attr, key in [
            ('MOBIKWIK_BBPS_CLIENT_SECRET', 'client_secret'),
            ('MOBIKWIK_BBPS_API_KEY', 'api_key'),
            ('MOBIKWIK_BBPS_SECRET_KEY', 'secret_key'),
        ]:
            v = getattr(payswap_config, attr, None)
            if v is not None:
                out[key] = (v.get_secret_value() if hasattr(v, 'get_secret_value') else str(v)) or ''
    return out


def _get_vendor_test_params_schema(vendor_code):
    """Return list of {key, label, type, placeholder} for test params form per vendor."""
    if vendor_code == 'mobikwik':
        return [
            {'key': 'base_url', 'label': 'Base URL', 'type': 'text', 'placeholder': 'https://alpha3.mobikwik.com'},
            {'key': 'client_id', 'label': 'Client ID', 'type': 'text', 'placeholder': ''},
            {'key': 'client_secret', 'label': 'Client Secret', 'type': 'password', 'placeholder': ''},
            {'key': 'merchant_id', 'label': 'Merchant ID', 'type': 'text', 'placeholder': ''},
            {'key': 'api_key', 'label': 'API Key', 'type': 'password', 'placeholder': ''},
            {'key': 'secret_key', 'label': 'Secret Key', 'type': 'password', 'placeholder': ''},
        ]
    return []


@require_http_methods(["POST"])
@login_required
def save_vendor_test_params_view(request, service_id, vendor_code):
    """Save optional test parameter overrides for a vendor. Stored in service.vendor_config[vendor_code][test_params]."""
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    service = get_object_or_404(Service, id=service_id)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    test_params = data.get('test_params')
    if test_params is not None and not isinstance(test_params, dict):
        return JsonResponse({'success': False, 'message': 'test_params must be an object'}, status=400)
    vendor_config = getattr(service, 'vendor_config', None) or {}
    if vendor_code not in vendor_config:
        vendor_config[vendor_code] = {}
    vendor_config[vendor_code]['test_params'] = test_params or {}
    vendor_config[vendor_code]['test_params_updated_at'] = timezone.now().isoformat()
    vendor_config[vendor_code]['test_params_updated_by'] = request.user.id
    service.vendor_config = vendor_config
    service.save(update_fields=['vendor_config'])
    return JsonResponse({'success': True, 'message': 'Test parameters saved'})


@require_http_methods(["GET", "POST"])
@login_required
def test_all_vendor_apis_view(request, service_id, vendor_code):
    """Run all API tests for this vendor and return combined results. Uses saved test_params if set."""
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    service = get_object_or_404(Service, id=service_id)
    vendor_config = getattr(service, 'vendor_config', None) or {}
    test_params = vendor_config.get(vendor_code, {}).get('test_params') or {}

    results = []
    if vendor_code == 'mobikwik' and getattr(service, 'code', None) == 'BBPS':
        from portal.services.bbps_service import BBPSService
        bbps = BBPSService(vendor='mobikwik', test_params=test_params)
        if not bbps.is_available():
            return JsonResponse({
                'success': False,
                'message': 'Mobikwik BBPS not configured. Set .env or save test parameters above.',
                'results': [],
            }, status=503)
        for name, fn in [
            ('1. Token Generation', lambda: bbps.client.get_token() if hasattr(bbps.client, 'get_token') else {'success': False, 'error': 'No get_token'}),
            ('2. Balance Check', lambda: bbps.balance_check()),
            ('3. Get Operators', lambda: bbps.get_operators(category=None)),
        ]:
            try:
                r = fn()
                results.append({
                    'api': name,
                    'success': bool(r.get('success')),
                    'message': r.get('message') or r.get('error') or ('OK' if r.get('success') else 'Failed'),
                    'data': r.get('data') if r.get('success') else None,
                })
            except Exception as e:
                results.append({'api': name, 'success': False, 'message': str(e), 'data': None})
    else:
        return JsonResponse({'success': False, 'message': 'Test all not implemented for this vendor', 'results': []}, status=400)

    return JsonResponse({'success': True, 'results': results})


# -------------------------------------------------------------------------
# Mobikwik BBPS Test API (for portal test UI – per BBPS guideline)
# -------------------------------------------------------------------------

# Human-readable API names for BBPS log detail (which API call is this log for)
_BBPS_ACTION_DISPLAY = {
    'balance_enquiry': 'Balance Check',
    'get_billers': 'Get Operators / Billers',
    'operators': 'Get Operators (Excel)',
    'fetch_bill': 'Fetch Bill',
    'pay_bill': 'Pay Bill',
    'payment_status': 'Payment Status',
}


def _vendor_response_id_from_result(result, action):
    """Extract vendor API response/transaction ID from BBPSService result for logging."""
    if not result or not isinstance(result, dict):
        return None
    data = result.get("data") or {}
    if action == "pay_bill":
        return result.get("transaction_id") or data.get("transactionId") or data.get("refId") or data.get("transaction_id") or data.get("ref_id")
    if action == "payment_status":
        return data.get("transactionId") or data.get("refId") or result.get("ref_id")
    if action == "fetch_bill":
        bill_details = result.get("bill_details") or data.get("billDetails") or data.get("bill_details") or data
        if isinstance(bill_details, dict):
            return bill_details.get("billId") or bill_details.get("bill_id") or data.get("refId") or data.get("referenceId")
    return data.get("responseId") or data.get("refId") or data.get("transactionId") or data.get("transaction_id")


def _create_bbps_log_entry(request, action, success, message, extra_data=None, vendor=None, request_method=None, request_body=None, response_status=None, response_body=None, request_id=None, response_id=None, vendor_response_id=None):
    """Create a LogEntry for BBPS API calls (portal test UI). category: mobikwik_bbps or euronet_bbps.
    request_body/response_body are shown on log detail page (/logs/<id>/). Pass sanitized dict/str.
    request_id/response_id are shown for tracing (optional).
    vendor_response_id: ID from vendor API response (e.g. transactionId, refId) for tracing.
    """
    try:
        level = 'INFO' if success else 'ERROR'
        category = 'euronet_bbps' if vendor == 'euronet' else 'mobikwik_bbps'
        extra = dict(extra_data or {}, action=action, success=success)
        api_display = _BBPS_ACTION_DISPLAY.get(action, action.replace('_', ' ').title())
        extra['api_name'] = api_display
        if vendor_response_id is not None and str(vendor_response_id).strip():
            extra['vendor_response_id'] = str(vendor_response_id).strip()
        if request and request.path:
            extra['api_url'] = request.path
        if vendor:
            extra['vendor'] = vendor
        if request_method:
            extra['request_method'] = request_method
        if request_body is not None:
            import json
            extra['request_body'] = json.dumps(request_body, indent=2) if isinstance(request_body, dict) else str(request_body)
        if response_status is not None:
            extra['response_status'] = response_status
        if response_body is not None:
            import json
            extra['response_body'] = json.dumps(response_body, indent=2) if isinstance(response_body, dict) else str(response_body)
        message_with_api = f"[{api_display}] {message[:480]}" if message else f"[{api_display}]"
        LogEntry.objects.create(
            log_level=level,
            category=category,
            message=message_with_api[:500],
            module_name='portal.views.bbps_test',
            url=request.path if request else None,
            user=request.user if request and request.user.is_authenticated else None,
            client_ip=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            extra_data=extra,
            request_id=request_id,
            response_id=response_id,
        )
    except Exception:
        pass


def _get_bbps_test_params(service, vendor: str) -> dict:
    """Get optional test parameter overrides from service.vendor_config for BBPS tests."""
    if not service or not getattr(service, 'vendor_config', None):
        return {}
    return (service.vendor_config or {}).get(vendor, {}).get('test_params') or {}


@require_http_methods(["GET"])
@login_required
def bbps_test_balance_view(request, service_id):
    """BBPS Balance Enquiry (Postman #1) – GET ?vendor=euronet. Uses saved test_params if set."""
    request_id = get_request_id(request)
    response_id = generate_response_id()
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    service = get_object_or_404(Service, id=service_id)
    if service.code != 'BBPS':
        return JsonResponse({'success': False, 'message': 'Invalid service'}, status=400)
    vendor = request.GET.get('vendor', 'euronet')
    test_params = _get_bbps_test_params(service, vendor)
    from portal.services.bbps_service import BBPSService
    bbps = BBPSService(vendor=vendor, test_params=test_params)
    if not bbps.is_available():
        return JsonResponse({'success': False, 'message': 'BBPS service not configured for this vendor'}, status=503)
    result = bbps.balance_check()
    success = result.get('success', False)
    msg = result.get('message') or ('Balance fetched' if success else 'Balance check failed')
    _create_bbps_log_entry(
        request, 'balance_enquiry', success, msg,
        extra_data={'vendor': vendor, 'success': success},
        vendor=vendor,
        request_method='GET',
        response_status=200,
        response_body=result,
        request_id=request_id,
        response_id=response_id,
    )
    return JsonResponse(result)


@require_http_methods(["GET"])
@login_required
def bbps_test_billers_view(request, service_id):
    """BBPS Get Billers / Operators from API (Postman #2) – GET ?vendor=euronet&category=optional."""
    request_id = get_request_id(request)
    response_id = generate_response_id()
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    service = get_object_or_404(Service, id=service_id)
    if service.code != 'BBPS':
        return JsonResponse({'success': False, 'message': 'Invalid service'}, status=400)
    vendor = request.GET.get('vendor', 'euronet')
    category = request.GET.get('category') or None
    test_params = _get_bbps_test_params(service, vendor)
    from portal.services.bbps_service import BBPSService
    bbps = BBPSService(vendor=vendor, test_params=test_params)
    if not bbps.is_available():
        return JsonResponse({'success': False, 'message': 'BBPS service not configured for this vendor'}, status=503)
    result = bbps.get_operators(category=category)
    success = result.get('success', False)
    operators = result.get('operators', [])
    msg = result.get('message') or (f'Billers loaded: {len(operators)}' if success else 'Get billers failed')
    _create_bbps_log_entry(
        request, 'get_billers', success, msg,
        extra_data={'vendor': vendor, 'category': category, 'count': len(operators)},
        vendor=vendor,
        request_method='GET',
        request_body=dict(request.GET) if request.GET else None,
        response_status=200,
        response_body=result,
        request_id=request_id,
        response_id=response_id,
    )
    return JsonResponse(result)


@require_http_methods(["GET"])
@login_required
def bbps_test_operators_view(request, service_id):
    """Return BBPS operators from Operators.xlsx (JSON). Optional ?category=ELECTRICITY"""
    request_id = get_request_id(request)
    response_id = generate_response_id()
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    service = get_object_or_404(Service, id=service_id)
    if service.code != 'BBPS':
        return JsonResponse({'success': False, 'message': 'Invalid service'}, status=400)
    try:
        from portal.services.bbps_operators_loader import load_bbps_operators_from_excel
        category = request.GET.get('category') or None
        vendor = request.GET.get('vendor')
        operators = load_bbps_operators_from_excel(bbps_enabled_only=True, category=category)
        _create_bbps_log_entry(
            request, 'operators', True,
            f'BBPS operators loaded: {len(operators)} operators',
            extra_data={'category_filter': category, 'count': len(operators)},
            vendor=vendor,
            request_id=request_id,
            response_id=response_id,
        )
        return JsonResponse({'success': True, 'operators': operators})
    except Exception as e:
        _create_bbps_log_entry(request, 'operators', False, f'BBPS operators failed: {str(e)}', extra_data={'error': str(e)}, vendor=request.GET.get('vendor'), request_id=request_id, response_id=response_id)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@require_http_methods(["POST"])
@login_required
def bbps_test_fetch_bill_view(request, service_id):
    """BBPS Fetch Bill test – POST JSON: operator_id, customer_id, subscriber_id?, ad1?, ad2?, ..."""
    request_id = get_request_id(request)
    response_id = generate_response_id()
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    service = get_object_or_404(Service, id=service_id)
    if service.code != 'BBPS':
        return JsonResponse({'success': False, 'message': 'Invalid service'}, status=400)
    import json
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    operator_id = data.get('operator_id')
    customer_id = data.get('customer_id')
    if not operator_id or not customer_id:
        return JsonResponse({'success': False, 'message': 'operator_id and customer_id required'}, status=400)
    subscriber_id = data.get('subscriber_id') or None
    extra = {}
    for k in ['ad1', 'ad2', 'ad3', 'ad4', 'ad9']:
        if data.get(k) not in (None, ''):
            extra[k] = str(data[k]).strip()
    if data.get('cir') not in (None, '') or data.get('circle') not in (None, ''):
        extra['cir'] = str(data.get('cir') or data.get('circle') or '').strip()
    elif operator_id:
        try:
            from portal.models import BBPSOperator
            op_record = BBPSOperator.objects.filter(
                models.Q(biller_id=operator_id) | models.Q(op=operator_id),
                is_active=True,
            ).first()
            if op_record and getattr(op_record, 'circle', None) and str(op_record.circle).strip():
                extra['cir'] = str(op_record.circle).strip()
        except Exception:
            pass
    vendor = data.get('vendor') or request.GET.get('vendor')
    test_params = _get_bbps_test_params(service, vendor)
    from portal.services.bbps_service import BBPSService
    bbps = BBPSService(vendor=vendor, test_params=test_params)
    if not bbps.is_available():
        return JsonResponse({'success': False, 'message': 'BBPS service not configured'}, status=503)
    result = bbps.fetch_bill(operator_id=operator_id, customer_id=customer_id, subscriber_id=subscriber_id, extra=extra or None)
    success = result.get('success', False)
    msg = result.get('message') or ('Bill fetched' if success else 'Bill fetch failed')
    vendor_resp_id = _vendor_response_id_from_result(result, 'fetch_bill')
    _create_bbps_log_entry(
        request, 'fetch_bill', success, msg,
        extra_data={'operator_id': operator_id, 'success': success},
        vendor=data.get('vendor') or request.GET.get('vendor'),
        request_method='POST',
        request_body=data,
        response_status=200,
        response_body=result,
        request_id=request_id,
        response_id=response_id,
        vendor_response_id=vendor_resp_id,
    )
    return JsonResponse(result)


@require_http_methods(["POST"])
@login_required
def bbps_test_pay_bill_view(request, service_id):
    """BBPS Pay Bill test – POST JSON: operator_id, customer_id, amount, ref_id, subscriber_id?, ad1?, ..."""
    request_id = get_request_id(request)
    response_id = generate_response_id()
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    service = get_object_or_404(Service, id=service_id)
    if service.code != 'BBPS':
        return JsonResponse({'success': False, 'message': 'Invalid service'}, status=400)
    import json
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    operator_id = data.get('operator_id')
    customer_id = data.get('customer_id')
    amount = data.get('amount')
    ref_id = data.get('ref_id')
    if not operator_id or not customer_id or amount is None or not ref_id:
        return JsonResponse({'success': False, 'message': 'operator_id, customer_id, amount, ref_id required'}, status=400)
    subscriber_id = data.get('subscriber_id') or None
    extra = {}
    for k in ['ad1', 'ad2', 'ad3', 'ad4', 'ad9']:
        if data.get(k) not in (None, ''):
            extra[k] = str(data[k]).strip()
    vendor = data.get('vendor') or request.GET.get('vendor')
    test_params = _get_bbps_test_params(service, vendor)
    from portal.services.bbps_service import BBPSService
    bbps = BBPSService(vendor=vendor, test_params=test_params)
    if not bbps.is_available():
        return JsonResponse({'success': False, 'message': 'BBPS service not configured'}, status=503)
    result = bbps.pay_bill(operator_id=operator_id, customer_id=customer_id, amount=str(amount), ref_id=str(ref_id), subscriber_id=subscriber_id, extra=extra or None)
    success = result.get('success', False)
    msg = result.get('message') or ('Payment submitted' if success else 'Payment failed')
    vendor_resp_id = _vendor_response_id_from_result(result, 'pay_bill')
    _create_bbps_log_entry(
        request, 'pay_bill', success, msg,
        extra_data={'operator_id': operator_id, 'ref_id': ref_id, 'success': success},
        vendor=data.get('vendor') or request.GET.get('vendor'),
        request_method='POST',
        request_body=data,
        response_status=200,
        response_body=result,
        request_id=request_id,
        response_id=response_id,
        vendor_response_id=vendor_resp_id,
    )
    return JsonResponse(result)


@require_http_methods(["GET"])
@login_required
def bbps_test_status_view(request, service_id):
    """BBPS Payment Status test – GET ?ref_id=..."""
    request_id = get_request_id(request)
    response_id = generate_response_id()
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    service = get_object_or_404(Service, id=service_id)
    if service.code != 'BBPS':
        return JsonResponse({'success': False, 'message': 'Invalid service'}, status=400)
    ref_id = request.GET.get('ref_id')
    if not ref_id:
        return JsonResponse({'success': False, 'message': 'ref_id required'}, status=400)
    vendor = request.GET.get('vendor')
    test_params = _get_bbps_test_params(service, vendor)
    from portal.services.bbps_service import BBPSService
    bbps = BBPSService(vendor=vendor, test_params=test_params)
    if not bbps.is_available():
        return JsonResponse({'success': False, 'message': 'BBPS service not configured'}, status=503)
    result = bbps.payment_status(ref_id=ref_id)
    success = result.get('success', False)
    msg = result.get('message') or (f'Status: {result.get("status", "unknown")}' if success else 'Status fetch failed')
    vendor_resp_id = _vendor_response_id_from_result(result, 'payment_status')
    _create_bbps_log_entry(
        request, 'payment_status', success, msg,
        extra_data={'ref_id': ref_id, 'success': success},
        vendor=request.GET.get('vendor'),
        request_method='GET',
        request_body=dict(request.GET) if request.GET else None,
        response_status=200,
        response_body=result,
        request_id=request_id,
        response_id=response_id,
        vendor_response_id=vendor_resp_id,
    )
    return JsonResponse(result)


def _instantpay_test_result_html(service_id: int, success: bool, api_code: str, status_code: int, response_data, error_msg: str) -> str:
    """Return a simple HTML result page for Instantpay Quick Test (form POST)."""
    import html
    import json
    status_cls = 'text-green-600' if success else 'text-red-600'
    status_text = 'Success' if success else 'Failed'
    try:
        raw = json.dumps(response_data, indent=2) if response_data else (error_msg or 'No response')
    except Exception:
        raw = str(response_data) if response_data else (error_msg or 'No response')
    resp_pre = html.escape(raw)
    back_url = f'/services/{service_id}/vendor/instantpay/'
    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Instantpay Test Result</title>
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;}}
.back{{display:inline-block;margin-bottom:1rem;color:#2563eb;text-decoration:none;}}
.back:hover{{text-decoration:underline;}}
h1{{font-size:1.25rem;}} .status{{font-weight:600;}} pre{{background:#f3f4f6;padding:1rem;border-radius:8px;overflow:auto;font-size:0.875rem;}}</style>
</head><body>
<a href="{back_url}" class="back">&larr; Back to Instantpay</a>
<h1>Instantpay Test Result</h1>
<p><span class="status {status_cls}">{status_text}</span> &ndash; API: {api_code}, HTTP {status_code}</p>
<pre>{resp_pre}</pre>
</body></html>'''


@require_http_methods(["POST"])
@login_required
def instantpay_test_api_view(request, service_id):
    """Test Instantpay API from portal (GSTIN, PIN code, etc.). Form POST returns HTML; JSON POST returns JSON."""
    import json
    from django.http import JsonResponse, HttpResponse
    
    if request.user.role_code not in ['super_admin', 'admin']:
        if request.content_type and 'application/json' in (request.content_type or ''):
            return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
        return HttpResponse(_instantpay_test_result_html(service_id, False, '', 403, None, 'Permission denied'), status=403, content_type='text/html; charset=utf-8')
    try:
        service = Service.objects.get(id=service_id)
    except Service.DoesNotExist:
        if request.content_type and 'application/json' in (request.content_type or ''):
            return JsonResponse({'success': False, 'message': 'Service not found'}, status=404)
        return HttpResponse(_instantpay_test_result_html(service_id, False, '', 404, None, 'Service not found'), status=404, content_type='text/html; charset=utf-8')
    if service.code != 'INSTANTPAY':
        if request.content_type and 'application/json' in (request.content_type or ''):
            return JsonResponse({'success': False, 'message': 'Invalid service'}, status=400)
        return HttpResponse(_instantpay_test_result_html(service_id, False, '', 400, None, 'Invalid service'), status=400, content_type='text/html; charset=utf-8')
    
    from portal.services.vendors.instantpay import InstantpayClient
    client = InstantpayClient()
    if not client.is_configured():
        if request.content_type and 'application/json' in (request.content_type or ''):
            return JsonResponse({'success': False, 'message': 'Instantpay not configured (INSTANTPAY_* in .env)'}, status=400)
        return HttpResponse(_instantpay_test_result_html(service_id, False, '', 400, None, 'Instantpay not configured (INSTANTPAY_* in .env)'), status=400, content_type='text/html; charset=utf-8')
    
    client_ip = get_client_ip(request) or '127.0.0.1'
    is_json = request.content_type and 'application/json' in request.content_type
    if is_json:
        try:
            data = json.loads(request.body)
        except Exception:
            data = {}
        api_code = data.get('api_code', '')
        gstin = data.get('gstin', '')
        pincode = data.get('pincode', '')
    else:
        api_code = request.POST.get('api_code', '')
        gstin = request.POST.get('gstin', '').strip()
        pincode = request.POST.get('pincode', '').strip()
    
    result = None
    if api_code == 'gstin' and gstin:
        result = client.gstin_verification(gstin, client_ip=client_ip)
    elif api_code == 'pin_code_lookup' and pincode:
        result = client.pin_code_lookup(pincode, client_ip=client_ip)
    else:
        err = 'Provide api_code and required params (gstin or pincode)'
        if is_json:
            return JsonResponse({'success': False, 'message': err}, status=400)
        return HttpResponse(_instantpay_test_result_html(service_id, False, api_code or '?', 400, None, err), status=400, content_type='text/html; charset=utf-8')
    
    ok = result.get('status_code', 0) in (200, 201)
    status_code = result.get('status_code', 0)
    response_data = result.get('json') or result.get('body')
    error_msg = result.get('error')
    
    if is_json:
        return JsonResponse({
            'success': ok,
            'status_code': status_code,
            'response': response_data,
            'error': error_msg,
        })
    html = _instantpay_test_result_html(service_id, ok, api_code, status_code, response_data, error_msg)
    return HttpResponse(html, content_type='text/html; charset=utf-8')


@require_http_methods(["POST"])
@login_required
def test_verification_api_view(request, service_id):
    """Test verification API endpoint (for Verification API) or SMS/IVR Gateway API endpoint"""
    import json
    from django.http import JsonResponse
    from portal.services.verification_api import VerificationAPIService
    
    # Check permissions
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({
            'success': False,
            'message': 'Permission denied'
        }, status=403)
    
    try:
        service = Service.objects.get(id=service_id)
        if service.code not in ['VERIFICATION_API', 'SMS_IVR_GATEWAY', 'PAYMENT_GATEWAY']:
            return JsonResponse({
                'success': False,
                'message': 'Invalid service'
            }, status=400)
        
        data = json.loads(request.body)
        api_type = data.get('api_type')
        
        verification_service = VerificationAPIService()
        
        # Get user info for logging
        user_id = request.user.id if request.user.is_authenticated else None
        request_id = get_request_id(request) or str(uuid.uuid4())
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # Route to appropriate API method
        verification_id = data.get('verification_id')  # Optional, will be auto-generated if not provided
        
        # Common logging parameters
        log_params = {
            'user_id': user_id,
            'request_id': request_id,
            'client_ip': client_ip,
            'user_agent': user_agent
        }
        
        if api_type == 'pan':
            result = verification_service.verify_pan(
                data.get('pan_number'), 
                data.get('name'),
                verification_id,
                **log_params
            )
        elif api_type == 'aadhaar':
            result = verification_service.verify_aadhaar(
                data.get('aadhaar_number'), 
                data.get('name'),
                verification_id,
                **log_params
            )
        elif api_type == 'bank':
            result = verification_service.verify_bank_account(
                data.get('account_number'),
                data.get('ifsc_code'),
                data.get('name'),
                data.get('phone'),
                **log_params
            )
        elif api_type == 'phone':
            result = verification_service.verify_phone(
                data.get('phone_number'),
                **log_params
            )
        elif api_type == 'email':
            result = verification_service.verify_email(
                data.get('email'),
                **log_params
            )
        elif api_type == 'driving_license':
            result = verification_service.verify_driving_license(
                data.get('dl_number'),
                data.get('dob'),
                verification_id,
                **log_params
            )
        elif api_type == 'voter_id':
            result = verification_service.verify_voter_id(
                data.get('voter_id'),
                data.get('name'),
                verification_id,
                **log_params
            )
        elif api_type == 'passport':
            result = verification_service.verify_passport(
                data.get('passport_number'),  # This is actually file_number in Cashfree API
                data.get('dob'),
                verification_id,
                **log_params
            )
        elif api_type == 'gst':
            result = verification_service.verify_gst(
                data.get('gstin'),
                data.get('business_name'),
                **log_params
            )
        elif api_type == 'cin':
            result = verification_service.verify_cin(
                data.get('cin'),
                verification_id,
                **log_params
            )
        elif api_type == 'ifsc':
            result = verification_service.verify_ifsc(
                data.get('ifsc_code'),
                verification_id,
                **log_params
            )
        elif api_type == 'vehicle_rc':
            result = verification_service.verify_vehicle_rc(
                data.get('vehicle_number'),
                verification_id,
                **log_params
            )
        elif api_type == 'face_liveness':
            result = verification_service.verify_face_liveness(
                data.get('image_base64'),
                verification_id,
                **log_params
            )
        elif api_type == 'face_match':
            result = verification_service.verify_face_match(
                data.get('image1_base64'),
                data.get('image2_base64'),
                verification_id,
                **log_params
            )
        elif api_type == 'name_match':
            result = verification_service.verify_name_match(
                data.get('name1'),
                data.get('name2'),
                verification_id,
                **log_params
            )
        elif api_type == 'smart_ocr':
            result = verification_service.smart_ocr(
                data.get('document_type'),
                data.get('image_base64'),
                verification_id,
                **log_params
            )
        elif api_type == 'aadhaar_ocr':
            result = verification_service.verify_aadhaar_ocr(
                data.get('image_base64'),
                verification_id,
                **log_params
            )
        elif api_type == 'aadhaar_masking':
            result = verification_service.verify_aadhaar_masking(
                data.get('aadhaar_number'),
                verification_id,
                **log_params
            )
        elif api_type == 'offline_aadhaar_send_otp':
            result = verification_service.offline_aadhaar_send_otp(
                data.get('aadhaar_number'),
                verification_id,
                **log_params
            )
        elif api_type == 'offline_aadhaar_verify_otp':
            result = verification_service.offline_aadhaar_verify_otp(
                data.get('otp'),
                data.get('verification_id'),
                **log_params
            )
        elif api_type == 'pan_advance':
            result = verification_service.verify_pan_advance(
                data.get('pan_number'),
                data.get('name'),
                verification_id,
                **log_params
            )
        elif api_type == 'pan_ocr':
            result = verification_service.verify_pan_ocr(
                data.get('image_base64'),
                verification_id,
                **log_params
            )
        elif api_type == 'pan_to_gstin':
            result = verification_service.verify_pan_to_gstin(
                data.get('pan_number'),
                verification_id,
                **log_params
            )
        elif api_type == 'pan_bulk':
            result = verification_service.verify_pan_bulk(
                data.get('pan_entries', []),
                verification_id,
                **log_params
            )
        elif api_type == 'digilocker_create_url':
            result = verification_service.digilocker_create_url(
                data.get('redirect_url'),
                verification_id,
                **log_params
            )
        elif api_type == 'digilocker_get_status':
            result = verification_service.digilocker_get_status(
                data.get('verification_id'),
                **log_params
            )
        elif api_type == 'digilocker_get_document':
            result = verification_service.digilocker_get_document(
                data.get('verification_id'),
                data.get('document_type'),
                **log_params
            )
        elif api_type == 'esign_create_signature':
            result = verification_service.esign_create_signature(
                data.get('document_base64'),
                data.get('signers', []),
                verification_id,
                **log_params
            )
        elif api_type == 'esign_get_status':
            result = verification_service.esign_get_status(
                data.get('verification_id'),
                **log_params
            )
        elif api_type == 'esign_upload_document':
            result = verification_service.esign_upload_document(
                data.get('document_base64'),
                verification_id,
                **log_params
            )
        elif api_type == 'advance_employment':
            result = verification_service.verify_advance_employment(
                data.get('uan'),
                data.get('pan'),
                verification_id,
                **log_params
            )
        elif api_type == 'reverse_penny_drop':
            result = verification_service.verify_reverse_penny_drop(
                data.get('account_number'),
                data.get('ifsc_code'),
                verification_id,
                **log_params
            )
        elif api_type == 'reverse_penny_drop_status':
            result = verification_service.get_reverse_penny_drop_status(
                data.get('verification_id'),
                **log_params
            )
        elif api_type == 'reverse_geocoding':
            result = verification_service.verify_reverse_geocoding(
                data.get('latitude'),
                data.get('longitude'),
                verification_id,
                **log_params
            )
        elif api_type == 'ip_verification':
            result = verification_service.verify_ip_address(
                data.get('ip_address'),
                verification_id,
                **log_params
            )
        elif api_type == 'test_connection':
            # Test connection - handle both Verification API and SMS/IVR Gateway
            if service.code == 'VERIFICATION_API':
                result = verification_service.test_connection(**log_params)
            elif service.code == 'SMS_IVR_GATEWAY':
                # Test Kaleyra connection
                from portal.services.vendors.kaleyra import KaleyraClient
                kaleyra_client = KaleyraClient()
                try:
                    # Try sending a test SMS
                    test_result = kaleyra_client.send_sms(
                        to='919876543210',  # Test number
                        message='Test connection',
                        message_type='TXN'
                    )
                    result = {
                        'success': True,
                        'status': 'success',
                        'message': 'Connection successful - API is responding',
                        'vendor': 'kaleyra',
                        'base_url': kaleyra_client.base_url
                    }
                except Exception as e:
                    result = {
                        'success': False,
                        'status': 'error',
                        'message': f'Connection test failed: {str(e)}',
                        'vendor': 'kaleyra',
                        'base_url': kaleyra_client.base_url
                    }
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid service for test connection'
                }, status=400)
        else:
            # Check if this is a Kaleyra API (SMS/IVR Gateway service)
            if service.code == 'SMS_IVR_GATEWAY':
                from portal.services.vendors.kaleyra import KaleyraClient
                
                kaleyra_client = KaleyraClient()
                
                if api_type == 'sms':
                    # Send SMS
                    phone_number = data.get('phone_number')
                    message = data.get('message')
                    message_type = data.get('message_type', 'TXN')
                    
                    if not phone_number or not message:
                        return JsonResponse({
                            'success': False,
                            'message': 'Phone number and message are required'
                        }, status=400)
                    
                    try:
                        result = kaleyra_client.send_sms(
                            to=phone_number,
                            message=message,
                            message_type=message_type
                        )
                        # Standardize result
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'SMS sent successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                    
                elif api_type == 'template_sms':
                    # Send Template SMS
                    from portal.utils.template_loader import get_template_by_dlt_id, load_dlt_templates
                    
                    phone_number = data.get('phone_number')
                    template_id = data.get('template_id')
                    variables_str = data.get('variables', '')  # Comma-separated or JSON string
                    message_type = data.get('message_type', 'TXN')
                    
                    if not phone_number or not template_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Phone number and template ID are required'
                        }, status=400)
                    
                    # Get template details
                    template = get_template_by_dlt_id(template_id)
                    if not template:
                        return JsonResponse({
                            'success': False,
                            'message': f'Template with DLT ID {template_id} not found'
                        }, status=400)
                    
                    # Parse variables
                    variables = []
                    if variables_str:
                        # Try JSON first
                        try:
                            import json
                            variables = json.loads(variables_str)
                            if isinstance(variables, list):
                                pass
                            elif isinstance(variables, dict):
                                variables = list(variables.values())
                            else:
                                variables = [str(variables)]
                        except:
                            # Try comma-separated
                            variables = [v.strip() for v in variables_str.split(',') if v.strip()]
                    
                    try:
                        result = kaleyra_client.send_template_sms(
                            phone_number=phone_number,
                            template_id=template_id,
                            template_content=template['content'],
                            variables=variables,
                            message_type=message_type
                        )
                        # Standardize result
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': f'Template SMS sent successfully using {template["name"]}',
                            'data': result,
                            'template_name': template['name']
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                elif api_type == 'click_to_call':
                    # Click to Call
                    from_number = data.get('from_number')
                    to_number = data.get('to_number')
                    bridge_number = data.get('bridge_number')  # Optional
                    
                    if not from_number or not to_number:
                        return JsonResponse({
                            'success': False,
                            'message': 'From number and To number are required'
                        }, status=400)
                    
                    try:
                        result = kaleyra_client.click_to_call(
                            from_number=from_number,
                            to_number=to_number,
                            bridge_number=bridge_number
                        )
                        # Standardize result
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Click to Call initiated successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                else:
                    return JsonResponse({
                        'success': False,
                        'message': f'Unknown API type: {api_type}'
                    }, status=400)
            elif service.code == 'VERIFICATION_API' and vendor_code == 'leegality':
                # Leegality APIs
                from portal.services.vendors.leegality import LeegalityClient
                
                leegality_client = LeegalityClient()
                
                if api_type == 'create_document':
                    file = data.get('file')
                    name = data.get('name')
                    invitations = data.get('invitations', [])
                    workflow_id = data.get('workflow_id')
                    template_id = data.get('template_id')
                    custom_message = data.get('custom_message')
                    
                    if not file or not name or not invitations:
                        return JsonResponse({
                            'success': False,
                            'message': 'File, name, and invitations are required'
                        }, status=400)
                    
                    try:
                        result = leegality_client.create_document(
                            file=file,
                            name=name,
                            invitations=invitations,
                            workflow_id=workflow_id,
                            template_id=template_id,
                            custom_message=custom_message
                        )
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Document created successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'get_document_status':
                    document_id = data.get('document_id')
                    if not document_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Document ID is required'
                        }, status=400)
                    
                    try:
                        result = leegality_client.get_document_status(document_id)
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Document status retrieved successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'create_stamp_paper':
                    document_id = data.get('document_id')
                    stamp_details = data.get('stamp_details', {})
                    
                    if not document_id or not stamp_details:
                        return JsonResponse({
                            'success': False,
                            'message': 'Document ID and stamp details are required'
                        }, status=400)
                    
                    try:
                        result = leegality_client.create_stamp_paper(
                            document_id=document_id,
                            stamp_details=stamp_details
                        )
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Stamp paper created successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'get_stamp_status':
                    document_id = data.get('document_id')
                    if not document_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Document ID is required'
                        }, status=400)
                    
                    try:
                        result = leegality_client.get_stamp_status(document_id)
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Stamp status retrieved successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'download_document':
                    document_id = data.get('document_id')
                    if not document_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Document ID is required'
                        }, status=400)
                    
                    try:
                        document_bytes = leegality_client.download_document(document_id)
                        import base64
                        document_base64 = base64.b64encode(document_bytes).decode('utf-8')
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Document downloaded successfully',
                            'data': {
                                'document_base64': document_base64,
                                'size': len(document_bytes)
                            }
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'get_audit_trail':
                    document_id = data.get('document_id')
                    if not document_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Document ID is required'
                        }, status=400)
                    
                    try:
                        result = leegality_client.get_audit_trail(document_id)
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Audit trail retrieved successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                else:
                    return JsonResponse({
                        'success': False,
                        'message': f'Unknown API type: {api_type}'
                    }, status=400)
            elif service.code == 'PAYMENT_GATEWAY' and vendor_code == 'cashfree_pg':
                # Cashfree PG APIs
                from portal.services.vendors.cashfree_pg import CashfreePGClient
                
                cashfree_pg_client = CashfreePGClient()
                
                if api_type == 'create_order':
                    order_amount = float(data.get('order_amount', 0))
                    order_currency = data.get('order_currency', 'INR')
                    customer_details = data.get('customer_details', {})
                    order_meta = data.get('order_meta', {})
                    order_id = data.get('order_id')
                    
                    if not order_amount or not order_currency or not customer_details:
                        return JsonResponse({
                            'success': False,
                            'message': 'Order amount, currency, and customer details are required'
                        }, status=400)
                    
                    try:
                        result = cashfree_pg_client.create_order(
                            order_amount=order_amount,
                            order_currency=order_currency,
                            customer_details=customer_details,
                            order_meta=order_meta,
                            order_id=order_id
                        )
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Order created successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'get_order':
                    order_id = data.get('order_id')
                    if not order_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Order ID is required'
                        }, status=400)
                    
                    try:
                        result = cashfree_pg_client.get_order(order_id)
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Order retrieved successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'create_refund':
                    order_id = data.get('order_id')
                    refund_amount = float(data.get('refund_amount', 0))
                    refund_id = data.get('refund_id')
                    refund_note = data.get('refund_note')
                    
                    if not order_id or not refund_amount:
                        return JsonResponse({
                            'success': False,
                            'message': 'Order ID and refund amount are required'
                        }, status=400)
                    
                    try:
                        result = cashfree_pg_client.create_refund(
                            order_id=order_id,
                            refund_amount=refund_amount,
                            refund_id=refund_id,
                            refund_note=refund_note
                        )
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Refund created successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'get_refund':
                    order_id = data.get('order_id')
                    refund_id = data.get('refund_id')
                    
                    if not order_id or not refund_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Order ID and Refund ID are required'
                        }, status=400)
                    
                    try:
                        result = cashfree_pg_client.get_refund(order_id, refund_id)
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Refund retrieved successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'get_payment':
                    order_id = data.get('order_id')
                    cf_payment_id = data.get('cf_payment_id')
                    
                    if not order_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Order ID is required'
                        }, status=400)
                    
                    try:
                        result = cashfree_pg_client.get_payment(order_id, cf_payment_id)
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Payment retrieved successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'create_payment_link':
                    link_amount = float(data.get('link_amount', 0))
                    link_currency = data.get('link_currency', 'INR')
                    link_id = data.get('link_id')
                    link_purpose = data.get('link_purpose')
                    customer_details = data.get('customer_details', {})
                    
                    if not link_amount or not link_currency or not link_purpose:
                        return JsonResponse({
                            'success': False,
                            'message': 'Link amount, currency, and purpose are required'
                        }, status=400)
                    
                    try:
                        result = cashfree_pg_client.create_payment_link(
                            link_amount=link_amount,
                            link_currency=link_currency,
                            link_id=link_id,
                            link_purpose=link_purpose,
                            customer_details=customer_details if customer_details else None
                        )
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Payment link created successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                
                elif api_type == 'get_payment_link':
                    link_id = data.get('link_id')
                    if not link_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Link ID is required'
                        }, status=400)
                    
                    try:
                        result = cashfree_pg_client.get_payment_link(link_id)
                        result = {
                            'success': True,
                            'status': 'success',
                            'message': 'Payment link retrieved successfully',
                            'data': result
                        }
                    except Exception as e:
                        result = {
                            'success': False,
                            'status': 'error',
                            'message': str(e),
                            'error': str(e)
                        }
                else:
                    return JsonResponse({
                        'success': False,
                        'message': f'Unknown API type: {api_type}'
                    }, status=400)
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid service or API type'
                }, status=400)
        
        # Determine success based on result
        is_success = result.get('success', False) if isinstance(result, dict) else True
        if service.code == 'SMS_IVR_GATEWAY':
            log_category = 'kaleyra'
        elif service.code == 'VERIFICATION_API' and vendor_code == 'leegality':
            log_category = 'leegality'
        elif service.code == 'PAYMENT_GATEWAY' and vendor_code == 'cashfree_pg':
            log_category = 'cashfree_pg'
        elif service.code == 'VERIFICATION_API':
            log_category = 'cashfree'
        else:
            log_category = 'general'
        
        return JsonResponse({
            'success': is_success,
            'message': result.get('message', 'API test completed') if isinstance(result, dict) else 'API test completed',
            'data': result,
            'log_message': f'Check /logs/?category={log_category} to view detailed logs for this API call'
        })
        
    except Exception as e:
        # Log the error to standard logger as well
        import logging
        logger = logging.getLogger('portal.views')
        logger.error(
            f"Cashfree API test failed: {str(e)}",
            exc_info=True,
            extra={
                'api_type': data.get('api_type'),
                'service_id': service_id,
                'user_id': request.user.id if request.user.is_authenticated else None
            }
        )
        
        return JsonResponse({
            'success': False,
            'message': str(e),
            'error': str(e),
            'error_type': type(e).__name__
        }, status=500)


@require_http_methods(["POST"])
@login_required
def manage_kaleyra_bridge_numbers_view(request, service_id):
    """Add or delete Kaleyra bridge numbers"""
    import json
    from django.http import JsonResponse
    from portal.models import Service
    from django.utils import timezone
    
    # Check permissions
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({
            'success': False,
            'message': 'Permission denied'
        }, status=403)
    
    try:
        service = Service.objects.get(id=service_id)
        if service.code != 'SMS_IVR_GATEWAY':
            return JsonResponse({
                'success': False,
                'message': 'Invalid service'
            }, status=400)
        
        data = json.loads(request.body)
        action = data.get('action')  # 'add' or 'delete'
        bridge_number = data.get('bridge_number', '').strip()
        bridge_type = data.get('bridge_type', 'ivr').lower()  # 'ivr' or 'sms'
        
        if not action or not bridge_number:
            return JsonResponse({
                'success': False,
                'message': 'Action and bridge_number are required'
            }, status=400)
        
        if bridge_type not in ['ivr', 'sms']:
            return JsonResponse({
                'success': False,
                'message': 'Bridge type must be "ivr" or "sms"'
            }, status=400)
        
        # Get or initialize vendor_config
        vendor_config = service.vendor_config if service.vendor_config else {}
        if 'kaleyra' not in vendor_config:
            vendor_config['kaleyra'] = {}
        
        # Initialize bridge_numbers if not exists
        if 'bridge_numbers' not in vendor_config['kaleyra']:
            vendor_config['kaleyra']['bridge_numbers'] = [
                {'number': '+917314500355', 'type': 'ivr'},
                {'number': '+911414761236', 'type': 'ivr'},
                {'number': '+917314500351', 'type': 'ivr'}
            ]
        
        bridge_numbers = vendor_config['kaleyra']['bridge_numbers']
        
        # Convert old format (list of strings) to new format (list of dicts) if needed
        if bridge_numbers and isinstance(bridge_numbers[0], str):
            bridge_numbers = [{'number': num, 'type': 'ivr'} for num in bridge_numbers]
            vendor_config['kaleyra']['bridge_numbers'] = bridge_numbers
        
        if action == 'add':
            # Check if bridge number already exists (regardless of type)
            existing_numbers = [b.get('number') if isinstance(b, dict) else b for b in bridge_numbers]
            if bridge_number not in existing_numbers:
                bridge_numbers.append({'number': bridge_number, 'type': bridge_type})
                vendor_config['kaleyra']['bridge_numbers'] = bridge_numbers
                message = f'Bridge number {bridge_number} ({bridge_type.upper()}) added successfully'
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Bridge number already exists'
                }, status=400)
        elif action == 'delete':
            # Delete bridge number if exists
            bridge_numbers = [b for b in bridge_numbers if (b.get('number') if isinstance(b, dict) else b) != bridge_number]
            vendor_config['kaleyra']['bridge_numbers'] = bridge_numbers
            message = f'Bridge number {bridge_number} deleted successfully'
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid action. Use "add" or "delete"'
            }, status=400)
        
        # Save service
        service.vendor_config = vendor_config
        service.updated_by = request.user
        service.save()
        
        return JsonResponse({
            'success': True,
            'message': message,
            'bridge_numbers': bridge_numbers
        })
        
    except Service.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Service not found'
        }, status=404)
    except Exception as e:
        import logging
        logger = logging.getLogger('portal.views')
        logger.error(
            f"Bridge number management failed: {str(e)}",
            exc_info=True,
            extra={
                'service_id': service_id,
                'user_id': request.user.id if request.user.is_authenticated else None
            }
        )
        
        return JsonResponse({
            'success': False,
            'message': str(e),
            'error': str(e),
            'error_type': type(e).__name__
        }, status=500)


@require_http_methods(["POST"])
@login_required
def toggle_vendor_service_view(request, service_id):
    """Toggle vendor service enable/disable status"""
    import json
    from django.http import JsonResponse
    from portal.models import Service
    
    # Check permissions
    if request.user.role_code not in ['super_admin', 'admin']:
        return JsonResponse({
            'success': False,
            'message': 'Permission denied'
        }, status=403)
    
    try:
        service = Service.objects.get(id=service_id)
        if service.code not in ['VERIFICATION_API', 'SMS_IVR_GATEWAY', 'PAYMENT_GATEWAY', 'BBPS', 'AEPS', 'DMT']:
            return JsonResponse({
                'success': False,
                'message': 'Invalid service'
            }, status=400)
        
        data = json.loads(request.body)
        vendor_code = data.get('vendor_code') or data.get('vendor')  # Support both for backward compatibility
        api_code = data.get('api_code')
        enabled = data.get('enabled', False)
        
        if not vendor_code or not api_code:
            return JsonResponse({
                'success': False,
                'message': 'Missing vendor or api_code'
            }, status=400)
        
        # Get or initialize vendor_config
        vendor_config = service.vendor_config if service.vendor_config else {}
        if vendor_code not in vendor_config:
            vendor_config[vendor_code] = {}
        
        # Update service status
        if api_code not in vendor_config[vendor_code]:
            vendor_config[vendor_code][api_code] = {}
        
        vendor_config[vendor_code][api_code]['enabled'] = enabled
        vendor_config[vendor_code][api_code]['updated_at'] = timezone.now().isoformat()
        vendor_config[vendor_code][api_code]['updated_by'] = request.user.id
        
        # Save service
        service.vendor_config = vendor_config
        service.updated_by = request.user
        service.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Service {api_code} {"enabled" if enabled else "disabled"} successfully',
            'vendor': vendor_code,
            'api_code': api_code,
            'enabled': enabled
        })
        
    except Service.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Service not found'
        }, status=404)
    except Exception as e:
        import logging
        logger = logging.getLogger('portal.views')
        logger.error(
            f"Failed to toggle vendor service: {str(e)}",
            exc_info=True,
            extra={
                'service_id': service_id,
                'vendor_code': vendor_code,
                'api_code': data.get('api_code'),
                'user_id': request.user.id if request.user.is_authenticated else None
            }
        )
        return JsonResponse({
            'success': False,
            'message': str(e),
            'error': str(e)
        }, status=500)


# ============================================================================
# CASHFREE API LOG VIEWS
# ============================================================================


# ============================================================================
# GIFT VOUCHER MANAGEMENT VIEWS
# ============================================================================

class BrandListView(LoginRequiredMixin, ListView):
    """List all gift voucher brands"""
    model = GiftVoucherBrand
    template_name = 'portal/vouchers/brands/list.html'
    context_object_name = 'brands'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.GET.get('status')
        search_query = self.request.GET.get('search')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search_query:
            queryset = queryset.filter(
                Q(brand_name__icontains=search_query) |
                Q(brand_code__icontains=search_query) |
                Q(contact_email__icontains=search_query)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = GiftVoucherBrand.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        context['search_query'] = self.request.GET.get('search', '')
        return context


class BrandCreateView(LoginRequiredMixin, CreateView):
    """Create new brand"""
    model = GiftVoucherBrand
    template_name = 'portal/vouchers/brands/create.html'
    fields = ['brand_name', 'business_reg_no', 'contact_person', 'contact_email', 'contact_phone', 'address']
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.onboarding_status = 'IN_PROGRESS'  # Start onboarding process
        form.instance.status = 'INACTIVE'  # Inactive until onboarding approved
        messages.success(self.request, 'Brand created successfully. Please complete the onboarding process.')
        response = super().form_valid(form)
        # Redirect to onboarding
        return redirect('brand_onboarding_start_brand', brand_id=self.object.id)
    
    def get_success_url(self):
        # This won't be used since we redirect in form_valid, but required by CreateView
        return '/vouchers/brands/'


class BrandDetailView(LoginRequiredMixin, DetailView):
    """View and edit brand details"""
    model = GiftVoucherBrand
    template_name = 'portal/vouchers/brands/detail.html'
    context_object_name = 'brand'
    pk_url_kwarg = 'brand_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        return context
    
    def post(self, request, brand_id):
        """Update brand"""
        brand = get_object_or_404(GiftVoucherBrand, id=brand_id)
        
        brand.brand_name = request.POST.get('brand_name', brand.brand_name)
        brand.business_reg_no = request.POST.get('business_reg_no', brand.business_reg_no)
        brand.contact_person = request.POST.get('contact_person', brand.contact_person)
        brand.contact_email = request.POST.get('contact_email', brand.contact_email)
        brand.contact_phone = request.POST.get('contact_phone', brand.contact_phone)
        brand.address = request.POST.get('address', brand.address)
        brand.status = request.POST.get('status', brand.status)
        brand.updated_by = request.user
        brand.save()
        
        messages.success(request, 'Brand updated successfully')
        return redirect('voucher_brand_detail', brand_id=brand.id)


class BrandDeleteView(LoginRequiredMixin, View):
    """Delete brand (only when no vouchers and no batches)"""
    template_name = 'portal/vouchers/brands/confirm_delete.html'

    def get(self, request, brand_id):
        brand = get_object_or_404(GiftVoucherBrand, id=brand_id)
        from_voucherx = request.GET.get('from') == 'voucherx'
        # Check if brand can be deleted
        has_vouchers = brand.vouchers.exists()
        has_batches = brand.bulk_batches.exists()
        can_delete = not has_vouchers and not has_batches
        return render(request, self.template_name, {
            'brand': brand,
            'from_voucherx': from_voucherx,
            'can_delete': can_delete,
            'has_vouchers': has_vouchers,
            'has_batches': has_batches,
        })

    def post(self, request, brand_id):
        brand = get_object_or_404(GiftVoucherBrand, id=brand_id)
        from_voucherx = request.GET.get('from') == 'voucherx' or request.POST.get('from_voucherx') == '1'
        if brand.vouchers.exists():
            messages.error(request, 'Cannot delete brand: it has vouchers. Remove or transfer vouchers first.')
            return redirect('voucher_brand_detail', brand_id=brand_id)
        if brand.bulk_batches.exists():
            messages.error(request, 'Cannot delete brand: it has issuance batches. Remove batches first.')
            return redirect('voucher_brand_detail', brand_id=brand_id)
        brand_name = brand.brand_name
        brand.delete()
        messages.success(request, f'Brand "{brand_name}" has been deleted.')
        if from_voucherx:
            return redirect('voucherx_dashboard')
        return redirect('voucher_brand_list')


class BrandVoucherDashboardView(LoginRequiredMixin, View):
    """Comprehensive brand-specific voucher management and analytics dashboard"""
    template_name = 'portal/vouchers/brands/dashboard.html'
    
    def get(self, request, brand_id):
        from django.db.models import Sum, Count, Q
        from decimal import Decimal
        from datetime import timedelta
        
        brand = get_object_or_404(GiftVoucherBrand, id=brand_id)
        
        # Calculate statistics for this brand
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)
        
        # Voucher statistics
        vouchers_qs = GiftVoucher.objects.filter(brand=brand)
        total_vouchers = vouchers_qs.count()
        active_vouchers = vouchers_qs.filter(status='ACTIVE').count()
        redeemed_vouchers = vouchers_qs.filter(
            status__in=['FULLY_REDEEMED', 'PARTIALLY_REDEEMED']
        ).count()
        
        # Value statistics
        total_value = vouchers_qs.aggregate(
            total=Sum('original_amount')
        )['total'] or Decimal('0.00')
        
        outstanding_balance = vouchers_qs.filter(
            status__in=['ACTIVE', 'PARTIALLY_REDEEMED']
        ).aggregate(
            total=Sum('current_balance')
        )['total'] or Decimal('0.00')
        
        redeemed_value = GiftVoucherTransaction.objects.filter(
            voucher__brand=brand,
            transaction_type='REDEMPTION',
            transaction_status='SUCCESS'
        ).aggregate(
            total=Sum('transaction_amount')
        )['total'] or Decimal('0.00')
        
        # Time-based statistics
        vouchers_today = vouchers_qs.filter(issued_at__gte=today_start).count()
        vouchers_week = vouchers_qs.filter(issued_at__gte=week_start).count()
        vouchers_month = vouchers_qs.filter(issued_at__gte=month_start).count()
        
        today_value = vouchers_qs.filter(issued_at__gte=today_start).aggregate(
            total=Sum('original_amount')
        )['total'] or Decimal('0.00')
        
        week_value = vouchers_qs.filter(issued_at__gte=week_start).aggregate(
            total=Sum('original_amount')
        )['total'] or Decimal('0.00')
        
        month_value = vouchers_qs.filter(issued_at__gte=month_start).aggregate(
            total=Sum('original_amount')
        )['total'] or Decimal('0.00')
        
        # Redemption rate
        redemption_rate = 0.0
        if total_value > 0:
            redemption_rate = float((redeemed_value / total_value) * 100)
        
        # Client statistics
        from portal.models import VoucherClient
        clients = VoucherClient.objects.filter(brand=brand, status='ACTIVE')
        total_clients = clients.count()
        
        # Batch statistics
        batches_qs = BulkVoucherIssuanceBatch.objects.filter(brand=brand)
        total_batches = batches_qs.count()
        active_batches = batches_qs.filter(status__in=['PENDING', 'PROCESSING']).count()
        completed_batches = batches_qs.filter(status='COMPLETED').count()
        
        # Recent vouchers (last 10)
        recent_vouchers = vouchers_qs.select_related('client', 'issued_by').order_by('-issued_at')[:10]
        
        # Recent batches (last 5)
        recent_batches = batches_qs.select_related('client', 'issued_by').order_by('-created_at')[:5]
        
        # Client-wise voucher counts
        client_stats = []
        for client in clients:
            client_vouchers = vouchers_qs.filter(client=client).count()
            client_stats.append({
                'client': client,
                'voucher_count': client_vouchers
            })
        client_stats.sort(key=lambda x: x['voucher_count'], reverse=True)
        
        context = {
            'brand': brand,
            'from_voucherx': request.GET.get('from') == 'voucherx',
            'stats': {
                'vouchers': {
                    'total': total_vouchers,
                    'active': active_vouchers,
                    'redeemed': redeemed_vouchers,
                    'today': vouchers_today,
                    'week': vouchers_week,
                    'month': vouchers_month
                },
                'value': {
                    'total': total_value,
                    'outstanding': outstanding_balance,
                    'redeemed': redeemed_value,
                    'today': today_value,
                    'week': week_value,
                    'month': month_value,
                    'redemption_rate': round(redemption_rate, 2)
                },
                'clients': {
                    'total': total_clients
                },
                'batches': {
                    'total': total_batches,
                    'active': active_batches,
                    'completed': completed_batches
                }
            },
            'recent_vouchers': recent_vouchers,
            'recent_batches': recent_batches,
            'clients': clients,
            'client_stats': client_stats
        }
        
        return render(request, self.template_name, context)


# ============================================================================
# BRAND ONBOARDING VIEWS
# ============================================================================

class BrandOnboardingStartView(LoginRequiredMixin, View):
    """Start or resume brand onboarding"""
    template_name = 'portal/vouchers/brands/onboarding/start.html'
    
    def get(self, request, brand_id=None):
        if brand_id:
            brand = get_object_or_404(GiftVoucherBrand, id=brand_id, created_by=request.user)
        else:
            # Get user's most recent brand that needs onboarding
            brand = GiftVoucherBrand.objects.filter(
                created_by=request.user,
                onboarding_status__in=['PENDING', 'IN_PROGRESS']
            ).order_by('-created_at').first()
            
            if not brand:
                messages.info(request, 'No brand found for onboarding. Please create a brand first.')
                return redirect('voucher_brand_create')
        
        from portal.services.brand_onboarding_service import BrandOnboardingService
        service = BrandOnboardingService()
        progress = service.get_onboarding_progress(brand)
        
        return render(request, self.template_name, {
            'brand': brand,
            'progress': progress
        })


class BrandOnboardingStepView(LoginRequiredMixin, View):
    """Handle onboarding steps (1-6)"""
    
    STEP_TEMPLATES = {
        1: 'portal/vouchers/brands/onboarding/step1_basic.html',
        2: 'portal/vouchers/brands/onboarding/step2_business.html',
        3: 'portal/vouchers/brands/onboarding/step3_banking.html',
        4: 'portal/vouchers/brands/onboarding/step4_documents.html',
        5: 'portal/vouchers/brands/onboarding/step5_agreement.html',
        6: 'portal/vouchers/brands/onboarding/step6_review.html',
    }
    
    STEP_FORMS = {
        1: BrandOnboardingStep1Form,
        2: BrandOnboardingStep2Form,
        3: BrandOnboardingStep3Form,
        4: BrandOnboardingStep4Form,
        5: BrandOnboardingStep5Form,
        6: BrandOnboardingReviewForm,
    }
    
    def get(self, request, brand_id, step):
        brand = get_object_or_404(GiftVoucherBrand, id=brand_id, created_by=request.user)
        
        # Check if brand can be onboarded
        if brand.onboarding_status == 'APPROVED':
            messages.info(request, 'This brand is already approved.')
            return redirect('voucher_brand_list')
        
        if step < 1 or step > 6:
            messages.error(request, 'Invalid step number')
            return redirect('brand_onboarding_start_brand', brand_id=brand_id)
        
        from portal.services.brand_onboarding_service import BrandOnboardingService
        service = BrandOnboardingService()
        
        # Check if user can access this step
        next_step = service.get_next_step(brand)
        if next_step and step > next_step:
            messages.info(request, f'Please complete step {next_step} first.')
            return redirect('brand_onboarding_step', brand_id=brand_id, step=next_step)
        
        form_class = self.STEP_FORMS.get(step)
        if not form_class:
            messages.error(request, 'Invalid step')
            return redirect('brand_onboarding_start_brand', brand_id=brand_id)
        
        # Pre-populate form with existing data
        form = form_class(initial=self._get_initial_data(brand, step))
        
        progress = service.get_onboarding_progress(brand)
        
        return render(request, self.STEP_TEMPLATES[step], {
            'brand': brand,
            'form': form,
            'step': step,
            'progress': progress,
            'step_name': service.STEP_NAMES.get(service.STEPS[step], f'Step {step}')
        })
    
    def post(self, request, brand_id, step):
        brand = get_object_or_404(GiftVoucherBrand, id=brand_id, created_by=request.user)
        
        if brand.onboarding_status == 'APPROVED':
            messages.info(request, 'This brand is already approved.')
            return redirect('voucher_brand_list')
        
        if step < 1 or step > 6:
            messages.error(request, 'Invalid step number')
            return redirect('brand_onboarding_start_brand', brand_id=brand_id)
        
        from portal.services.brand_onboarding_service import BrandOnboardingService
        from portal.services.storage_service import StorageService
        
        service = BrandOnboardingService()
        form_class = self.STEP_FORMS.get(step)
        
        if not form_class:
            messages.error(request, 'Invalid step')
            return redirect('brand_onboarding_start_brand', brand_id=brand_id)
        
        form = form_class(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                data = form.cleaned_data.copy()
                
                # Handle document uploads for step 4 (one at a time, all optional)
                if step == 4:
                    doc_fields = {
                        'business_registration_doc': 'business_registration',
                        'pan_document': 'pan',
                        'gst_certificate': 'gst',
                        'bank_statement': 'bank_statement',
                        'agreement_document': 'agreement'
                    }
                    for field_name, doc_type in doc_fields.items():
                        file = request.FILES.get(field_name)
                        if file:
                            # Validate file size (10MB limit)
                            if file.size > 10 * 1024 * 1024:
                                messages.error(request, f'{field_name.replace("_", " ").title()} is too large (max 10MB).')
                                return self.get(request, brand_id, step)
                            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
                            file_ext = '.' + file.name.split('.')[-1].lower() if file.name else ''
                            if file_ext not in allowed_extensions:
                                messages.error(request, f'Invalid file type. Allowed: PDF, JPG, PNG.')
                                return self.get(request, brand_id, step)
                            try:
                                import os
                                from datetime import datetime
                                storage_service = StorageService()
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                safe_filename = os.path.basename(file.name)
                                path = f"brands/{brand_id}/onboarding/{doc_type}/{timestamp}_{safe_filename}"
                                s3_url = storage_service.s3_client.upload_file(file, path)
                                data[field_name] = s3_url
                            except Exception as e:
                                logger.error(f'Error uploading {field_name}: {str(e)}', traceback=traceback.format_exc())
                                messages.error(request, f'Upload failed: {str(e)}. Check storage configuration.')
                                return self.get(request, brand_id, step)
                        else:
                            # Preserve existing document URL when no new file
                            data[field_name] = getattr(brand, field_name, None)
                
                # Validate and save step
                is_valid, error_msg = service.validate_step(step, data)
                if not is_valid:
                    messages.error(request, error_msg)
                    return self.get(request, brand_id, step)
                
                brand = service.save_step(step, data, brand)
                
                # If step 6 (review), submit for approval
                if step == 6:
                    try:
                        service.submit_for_approval(brand)
                        messages.success(request, 'Brand onboarding submitted for approval. You will be notified once it is reviewed.')
                        
                        # Send notification to brand
                        from portal.tasks.notification_task import send_notification_task
                        if brand.contact_email:
                            send_notification_task.delay(
                                notification_type='email',
                                channels=['email'],
                                message=f'Your brand "{brand.brand_name}" onboarding has been submitted for review. You will be notified once it is reviewed.',
                                subject='Brand Onboarding Submitted',
                                to_email=brand.contact_email,
                                use_parkpe=True,
                            )
                        
                        # Send notification to admins
                        from portal.models import User
                        admin_users = User.objects.filter(
                            role_code__in=['super_admin', 'admin'],
                            is_active=True
                        ).select_related('profile')
                        for admin in admin_users:
                            if hasattr(admin, 'profile') and admin.profile and admin.profile.email:
                                send_notification_task.delay(
                                    notification_type='email',
                                    channels=['email'],
                                    message=f'Brand "{brand.brand_name}" has submitted their onboarding for review. Please review and approve/reject.',
                                    subject='New Brand Onboarding Submission',
                                    to_email=admin.profile.email,
                                    use_parkpe=True,
                                )
                        
                        return redirect('brand_onboarding_status', brand_id=brand_id)
                    except Exception as e:
                        messages.error(request, str(e))
                        return self.get(request, brand_id, step)
                
                # Move to next step
                next_step = service.get_next_step(brand)
                if next_step:
                    messages.success(request, f'Step {step} completed successfully.')
                    return redirect('brand_onboarding_step', brand_id=brand_id, step=next_step)
                else:
                    # All steps complete, go to review
                    return redirect('brand_onboarding_step', brand_id=brand_id, step=6)
                    
            except Exception as e:
                logger.error(f'Error saving onboarding step {step}: {str(e)}', traceback=traceback.format_exc())
                messages.error(request, f'An error occurred: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
        
        progress = service.get_onboarding_progress(brand)
        return render(request, self.STEP_TEMPLATES[step], {
            'brand': brand,
            'form': form,
            'step': step,
            'progress': progress,
            'step_name': service.STEP_NAMES.get(service.STEPS[step], f'Step {step}')
        })
    
    def _get_initial_data(self, brand, step):
        """Get initial data for form based on step and brand"""
        if step == 1:
            return {
                'brand_name': brand.brand_name,
                'contact_person': brand.contact_person,
                'contact_email': brand.contact_email,
                'contact_phone': brand.contact_phone,
                'address': brand.address,
            }
        elif step == 2:
            return {
                'business_type': brand.business_type,
                'business_reg_no': brand.business_reg_no,
                'pan_number': brand.pan_number,
                'gst_number': brand.gst_number,
            }
        elif step == 3:
            return {
                'bank_account_number': brand.get_decrypted_bank_account(),
                'bank_ifsc_code': brand.bank_ifsc_code,
                'bank_name': brand.bank_name,
                'account_holder_name': brand.account_holder_name,
            }
        elif step == 4:
            return {
                'business_registration_doc': brand.business_registration_doc,
                'pan_document': brand.pan_document,
                'gst_certificate': brand.gst_certificate,
                'bank_statement': brand.bank_statement,
                'agreement_document': brand.agreement_document,
            }
        elif step == 5:
            return {
                'terms_accepted': brand.terms_accepted,
                'agreement_signed': brand.agreement_signed,
            }
        return {}


class BrandOnboardingStatusView(LoginRequiredMixin, View):
    """View onboarding status"""
    template_name = 'portal/vouchers/brands/onboarding/status.html'
    
    def get(self, request, brand_id):
        brand = get_object_or_404(GiftVoucherBrand, id=brand_id, created_by=request.user)
        
        from portal.services.brand_onboarding_service import BrandOnboardingService
        service = BrandOnboardingService()
        progress = service.get_onboarding_progress(brand)
        
        return render(request, self.template_name, {
            'brand': brand,
            'progress': progress
        })


class BrandOnboardingAdminListView(LoginRequiredMixin, ListView):
    """Admin view: List brands pending approval"""
    template_name = 'portal/vouchers/brands/onboarding/admin_list.html'
    context_object_name = 'brands'
    paginate_by = 20
    
    def get_queryset(self):
        # Only admins and super users can access
        if not (self.request.user.role_code in ['super_admin', 'admin'] or self.request.user.is_staff):
            raise Http404
        
        queryset = GiftVoucherBrand.objects.filter(
            onboarding_status='SUBMITTED'
        ).select_related('created_by', 'onboarding_approved_by').order_by('-created_at')
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(onboarding_status=status_filter)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_count'] = GiftVoucherBrand.objects.filter(
            onboarding_status='SUBMITTED'
        ).count()
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        return context


class BrandOnboardingAdminDetailView(LoginRequiredMixin, View):
    """Admin view: Review brand onboarding details"""
    template_name = 'portal/vouchers/brands/onboarding/admin_detail.html'
    
    def get(self, request, brand_id):
        # Only admins and super users can access
        if not (request.user.role_code in ['super_admin', 'admin'] or request.user.is_staff):
            raise Http404
        
        brand = get_object_or_404(GiftVoucherBrand, id=brand_id)
        
        from portal.services.brand_onboarding_service import BrandOnboardingService
        service = BrandOnboardingService()
        progress = service.get_onboarding_progress(brand)
        
        form = BrandOnboardingAdminApprovalForm()
        
        # Check if coming from VoucherX
        from_voucherx = request.GET.get('from') == 'voucherx'
        
        return render(request, self.template_name, {
            'brand': brand,
            'progress': progress,
            'form': form,
            'from_voucherx': from_voucherx
        })
    
    def post(self, request, brand_id):
        # Only admins and super users can access
        if not (request.user.role_code in ['super_admin', 'admin'] or request.user.is_staff):
            raise Http404
        
        brand = get_object_or_404(GiftVoucherBrand, id=brand_id)
        form = BrandOnboardingAdminApprovalForm(request.POST)
        
        if form.is_valid():
            action = form.cleaned_data['action']
            notes = form.cleaned_data.get('onboarding_notes', '')
            rejection_reason = form.cleaned_data.get('rejection_reason', '')
            
            try:
                if action == 'approve':
                    brand.onboarding_notes = notes
                    brand.approve_onboarding(request.user)
                    messages.success(request, f'Brand {brand.brand_name} onboarding approved successfully.')
                    
                    # Send notification
                    from portal.tasks.notification_task import send_notification_task
                    if brand.contact_email:
                        send_notification_task.delay(
                            notification_type='email',
                            channels=['email'],
                            message=f'Your brand "{brand.brand_name}" onboarding has been approved. You can now issue vouchers.',
                            subject='Brand Onboarding Approved',
                            to_email=brand.contact_email,
                            use_parkpe=True,
                        )
                    
                elif action == 'reject':
                    brand.onboarding_notes = notes
                    brand.reject_onboarding(request.user, rejection_reason)
                    messages.success(request, f'Brand {brand.brand_name} onboarding rejected.')
                    
                    # Send notification
                    from portal.tasks.notification_task import send_notification_task
                    if brand.contact_email:
                        send_notification_task.delay(
                            notification_type='email',
                            channels=['email'],
                            message=f'Your brand "{brand.brand_name}" onboarding has been rejected. Reason: {rejection_reason}',
                            subject='Brand Onboarding Rejected',
                            to_email=brand.contact_email,
                            use_parkpe=True,
                        )
                
                # Redirect based on source
                from_voucherx = request.GET.get('from') == 'voucherx'
                if from_voucherx:
                    return redirect('voucherx_dashboard')
                return redirect('brand_onboarding_admin_list')
                
            except Exception as e:
                logger.error(f'Error processing onboarding {action}: {str(e)}', traceback=traceback.format_exc())
                messages.error(request, f'An error occurred: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
        
        from portal.services.brand_onboarding_service import BrandOnboardingService
        service = BrandOnboardingService()
        progress = service.get_onboarding_progress(brand)
        
        # Check if coming from VoucherX
        from_voucherx = request.GET.get('from') == 'voucherx'
        
        return render(request, self.template_name, {
            'brand': brand,
            'progress': progress,
            'form': form,
            'from_voucherx': from_voucherx
        })


class VoucherIssueSingleView(LoginRequiredMixin, View):
    """Single voucher issuance view"""
    template_name = 'portal/vouchers/issuance/single.html'
    
    def get(self, request):
        # Only show brands that can issue vouchers (onboarded and active)
        all_brands = GiftVoucherBrand.objects.all()
        brands = [brand for brand in all_brands if brand.can_issue_vouchers()]
        brands.sort(key=lambda x: x.brand_name)
        
        if not brands:
            messages.info(request, 'No brands available for voucher issuance. Please complete brand onboarding first.')
        
        # Check if coming from VoucherX
        from_voucherx = request.GET.get('from') == 'voucherx'
        selected_brand_id = request.GET.get('brand_id')
        
        # Get clients for selected brand (if brand is selected)
        clients = []
        if selected_brand_id:
            try:
                from portal.services.voucher_client_service import VoucherClientService
                client_service = VoucherClientService()
                clients = client_service.get_brand_clients(int(selected_brand_id))
            except:
                pass
        
        return render(request, self.template_name, {
            'brands': brands,
            'clients': clients,
            'selected_brand_id': selected_brand_id,
            'from_voucherx': from_voucherx
        })
    
    def post(self, request):
        from portal.services.voucher_service import VoucherService
        from portal.services.notification_service_v2 import NotificationServiceV2
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        from decimal import Decimal
        
        try:
            brand_id = int(request.POST.get('brand_id'))
            amount = Decimal(request.POST.get('amount', '0'))
            mobile_number = request.POST.get('mobile_number', '').strip() or None
            recipient_email = request.POST.get('recipient_email', '').strip() or None
            client_id = request.POST.get('client_id')
            if client_id:
                client_id = int(client_id) if client_id else None
            else:
                client_id = None
            
            logger.info(
                f'[VOUCHER] Single issuance POST: brand_id={brand_id} amount={amount} has_email={bool(recipient_email)}',
                extra_data={'action': 'voucher_single_post_start', 'brand_id': brand_id}
            )
            
            if amount <= 0:
                messages.error(request, 'Amount must be greater than 0')
                return redirect('voucher_issue_single')
            
            if recipient_email:
                try:
                    validate_email(recipient_email)
                except ValidationError:
                    messages.error(request, 'Please enter a valid email address.')
                    return redirect('voucher_issue_single')
            
            # Determine issuer type based on user role
            issuer_type = 'ADMIN'  # Default to ADMIN for portal users
            if request.user.role_code == 'brand_owner':
                issuer_type = 'BRAND_OWNER'
            # API_PARTNER would be set when called from API
            
            # Check if coming from VoucherX and store in session
            from_voucherx = request.GET.get('from') == 'voucherx'
            
            voucher_service = VoucherService()
            result = voucher_service.issue_single_voucher(
                brand_id=brand_id,
                amount=amount,
                mobile_number=mobile_number,
                recipient_email=recipient_email,
                created_by=request.user,
                client_id=client_id,
                issued_by=request.user,
                issuer_type=issuer_type
            )
            
            logger.info(
                f'[VOUCHER] Issued: voucher_id={result.get("voucher_id")} ref={result.get("reference_number")} code={(result.get("voucher_code") or "")[:8]}...',
                extra_data={'action': 'voucher_issued', 'voucher_id': result.get('voucher_id'), 'brand_id': brand_id}
            )
            
            # Enqueue voucher email (never send directly from request; durable queue + Celery)
            if recipient_email:
                try:
                    from django.template.loader import render_to_string
                    from portal.services.email_queue_service import enqueue_email
                    from portal.tasks.notification_tasks import process_email_queue_task

                    brand = GiftVoucherBrand.objects.get(id=brand_id)
                    logo_url = request.build_absolute_uri(static('portal/images/parkpe-logo.png'))
                    context = {
                        'brand_name': brand.brand_name,
                        'voucher_code': result['voucher_code'],
                        'pin': result['pin'],
                        'amount': result['amount'],
                        'reference_number': result['reference_number'],
                        'recipient_email': recipient_email,
                        'logo_url': logo_url,
                    }
                    body_html = render_to_string('portal/emails/voucher_delivery.html', context)
                    body_text = f"Gift Voucher – {brand.brand_name}\nAmount: ₹{result['amount']}\nReference: {result['reference_number']}\nCode: {result['voucher_code']}\nPIN: {result['pin']}\n"
                    row = enqueue_email(
                        to_email=recipient_email,
                        subject=f'Your Gift Voucher – {brand.brand_name} | ₹{result["amount"]}',
                        body_html=body_html,
                        body_text=body_text,
                        related_entity={'type': 'voucher', 'voucher_id': result.get('voucher_id')},
                        use_parkpe_smtp=True,
                    )
                    process_email_queue_task.delay(row.id)
                    messages.success(request, 'Voucher issued successfully. Customer will receive an email shortly.')
                    request.session['voucher_email_sent'] = True
                except Exception as email_err:
                    voucher_console_log.warning(f'[VOUCHER] Email enqueue failed: {email_err}', exc_info=True)
                    logger.warning(
                        f'[VOUCHER] Email enqueue failed: {email_err}',
                        extra_data={'action': 'voucher_email_enqueue_failed', 'user_id': request.user.id, 'traceback': traceback.format_exc()}
                    )
                    messages.warning(request, 'Voucher issued but email could not be queued. Please share the voucher details manually.')
                    request.session['voucher_email_sent'] = False
            else:
                messages.success(request, 'Voucher issued successfully.')
                request.session['voucher_email_sent'] = None
            
            # Log voucher issuance from view
            log_voucher_operation(
                operation='voucher_issued_view',
                log_level='INFO',
                message=f'Single voucher issued via view - Brand ID: {brand_id}, Amount: {amount}',
                user_id=request.user.id,
                request=request,
                extra_data={
                    'voucher_id': result.get('voucher_id'),
                    'brand_id': brand_id,
                    'amount': str(amount),
                    'client_id': client_id,
                    'issuer_type': issuer_type,
                    'from_voucherx': from_voucherx,
                    'email_sent': bool(recipient_email),
                }
            )
            
            # Store result in session to display on success page
            request.session['voucher_issue_result'] = result
            request.session['from_voucherx'] = from_voucherx
            return redirect('voucher_issue_single_success')
            
        except ValueError as e:
            log_voucher_operation(
                operation='voucher_issuance_failed_view',
                log_level='WARNING',
                message=f'Voucher issuance failed (validation): {str(e)}',
                user_id=request.user.id,
                request=request,
                extra_data={'error': str(e), 'brand_id': brand_id if 'brand_id' in locals() else None}
            )
            messages.error(request, str(e))
            return redirect('voucher_issue_single')
        except Exception as e:
            err_msg = str(e)
            log_voucher_operation(
                operation='voucher_issuance_failed_view',
                log_level='ERROR',
                message=f'Voucher issuance failed: {err_msg}',
                user_id=request.user.id,
                request=request,
                extra_data={'error': err_msg, 'brand_id': brand_id if 'brand_id' in locals() else None},
                exception=e
            )
            logger.error(
                f'[VOUCHER] Issuance FAILED: {err_msg}',
                extra_data={'action': 'voucher_issuance_exception', 'brand_id': brand_id if 'brand_id' in locals() else None},
                traceback=traceback.format_exc()
            )
            # Show actual error to user so they know what to fix (e.g. "Please select a brand", "Brand not found")
            messages.error(request, f'Failed to issue voucher: {err_msg[:200]}')
            return redirect('voucher_issue_single')


class VoucherIssueSingleSuccessView(LoginRequiredMixin, TemplateView):
    """Display voucher issuance success"""
    template_name = 'portal/vouchers/issuance/single_success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = self.request.session.pop('voucher_issue_result', None)
        context['voucher'] = result
        # Email was attempted but failed → show "share manually" on success page
        context['voucher_email_failed'] = (self.request.session.pop('voucher_email_sent', None) is False)
        # Check if coming from VoucherX (from session or request)
        context['from_voucherx'] = (
            self.request.GET.get('from') == 'voucherx' or
            self.request.session.get('from_voucherx', False)
        )
        # PIN and sensitive details only for users with permission or admin/super/staff
        user = self.request.user
        context['can_see_voucher_sensitive'] = (
            getattr(user, 'is_staff', False) or
            getattr(user, 'role_code', None) in ('super_admin', 'admin') or
            user.has_perm('portal.view_voucher_sensitive')
        )
        return context


class VoucherIssueBulkView(LoginRequiredMixin, View):
    """Bulk voucher issuance view"""
    template_name = 'portal/vouchers/issuance/bulk.html'
    
    def get(self, request):
        # Only show brands that can issue vouchers (onboarded and active)
        all_brands = GiftVoucherBrand.objects.all()
        brands = [brand for brand in all_brands if brand.can_issue_vouchers()]
        brands.sort(key=lambda x: x.brand_name)
        
        batches = BulkVoucherIssuanceBatch.objects.filter(created_by=request.user).order_by('-created_at')[:10]
        
        if not brands:
            messages.info(request, 'No brands available for voucher issuance. Please complete brand onboarding first.')
        
        # Check if coming from VoucherX
        from_voucherx = request.GET.get('from') == 'voucherx'
        # Pre-select brand if provided
        selected_brand_id = request.GET.get('brand_id')
        
        # Get clients for selected brand (if brand is selected)
        clients = []
        if selected_brand_id:
            try:
                from portal.services.voucher_client_service import VoucherClientService
                client_service = VoucherClientService()
                clients = client_service.get_brand_clients(int(selected_brand_id))
            except:
                pass
        
        return render(request, self.template_name, {
            'brands': brands,
            'clients': clients,
            'recent_batches': batches,
            'from_voucherx': from_voucherx,
            'selected_brand_id': selected_brand_id
        })
    
    def post(self, request):
        from portal.services.bulk_voucher_service import BulkVoucherService
        from portal.utils.voucher_utils import generate_reference_number
        from portal.tasks.voucher_tasks import process_bulk_voucher_issuance_task
        from decimal import Decimal
        
        # Check if coming from VoucherX
        from_voucherx = request.GET.get('from') == 'voucherx'
        
        # Determine issuer type
        issuer_type = 'ADMIN'
        if request.user.role_code == 'brand_owner':
            issuer_type = 'BRAND_OWNER'
        
        issuance_method = request.POST.get('issuance_method', 'FILE_UPLOAD')
        
        try:
            brand_id = int(request.POST.get('brand_id'))
            client_id = request.POST.get('client_id')
            if client_id:
                client_id = int(client_id) if client_id else None
            else:
                client_id = None
            
            # Validate brand can issue vouchers
            try:
                brand = GiftVoucherBrand.objects.get(id=brand_id)
                if not brand.can_issue_vouchers():
                    if not brand.is_onboarded():
                        messages.error(request, 'Brand onboarding is not complete. Please complete the onboarding process before issuing vouchers.')
                    else:
                        messages.error(request, 'Brand is not active. Cannot issue vouchers.')
                    return redirect('voucher_issue_bulk')
            except GiftVoucherBrand.DoesNotExist:
                messages.error(request, 'Brand not found')
                return redirect('voucher_issue_bulk')
            
            bulk_service = BulkVoucherService()
            
            # Handle manual bulk issuance
            if issuance_method == 'MANUAL_BULK':
                # Parse denominations from form
                denominations = []
                denomination_count = int(request.POST.get('denomination_count', 0))
                
                for i in range(denomination_count):
                    amount_str = request.POST.get(f'denomination_{i}_amount', '').strip()
                    quantity_str = request.POST.get(f'denomination_{i}_quantity', '').strip()
                    
                    if amount_str and quantity_str:
                        try:
                            amount = Decimal(amount_str)
                            quantity = int(quantity_str)
                            if amount > 0 and quantity > 0:
                                denominations.append({
                                    'amount': amount,
                                    'quantity': quantity
                                })
                        except (ValueError, InvalidOperation):
                            pass
                
                if not denominations:
                    messages.error(request, 'Please provide at least one valid denomination')
                    return redirect('voucher_issue_bulk')
                
                # Create manual bulk batch
                batch = bulk_service.create_manual_bulk_batch(
                    brand_id=brand_id,
                    client_id=client_id,
                    denominations=denominations,
                    issued_by=request.user,
                    issuer_type=issuer_type
                )
                
                # Process synchronously in background thread for immediate start
                # This ensures processing starts immediately and user sees progress
                import threading
                
                # Immediately update status and initialize metadata
                batch.status = 'PROCESSING'
                batch.started_at = timezone.now()
                batch.metadata = batch.metadata or {}
                batch.metadata['voucher_progress'] = {}
                batch.metadata['current_voucher_index'] = 0
                batch.save(update_fields=['status', 'started_at', 'metadata'])
                
                # Process in background thread for immediate start
                def process_batch_async():
                    try:
                        process_bulk_voucher_issuance_task(batch.id)
                    except Exception as e:
                        logger.error(f'Error processing batch {batch.id} in background: {str(e)}', traceback=traceback.format_exc())
                
                # Start processing in background thread
                thread = threading.Thread(target=process_batch_async, daemon=True)
                thread.start()
                
                messages.success(request, f'Batch {batch.batch_reference} processing started! You will see progress in real-time.')
                return redirect('voucher_bulk_status', batch_id=batch.id)
            
            # Handle file upload (existing logic)
            else:
                file = request.FILES.get('file')
                
                if not file:
                    messages.error(request, 'Please select a file')
                    return redirect('voucher_issue_bulk')
                
                # Validate file
                is_valid, error_msg = bulk_service.validate_upload_file(file)
                if not is_valid:
                    messages.error(request, error_msg)
                    return redirect('voucher_issue_bulk')
                
                # Parse file
                voucher_data, parse_error = bulk_service.parse_upload_file(file)
                if not voucher_data:
                    messages.error(request, parse_error or "Failed to parse file")
                    return redirect('voucher_issue_bulk')
                
                # Get or create default client if not provided
                if not client_id:
                    from portal.services.voucher_client_service import VoucherClientService
                    client_service = VoucherClientService()
                    client = client_service.get_or_create_default_client(brand_id)
                    client_id = client.id
                
                # Generate issuer name
                issuer_name = request.user.username
                
                # Upload file to S3
                batch = BulkVoucherIssuanceBatch.objects.create(
                    brand_id=brand_id,
                    client_id=client_id,
                    batch_reference=generate_reference_number('BATCH'),
                    batch_reference_number=generate_reference_number('BRN'),
                    total_vouchers=len(voucher_data),
                    status='PENDING',
                    issuance_method='FILE_UPLOAD',
                    issued_by=request.user,
                    issuer_type=issuer_type,
                    created_by=request.user
                )
                
                try:
                    uploaded_file_path = bulk_service.upload_file_to_s3(file, batch.id)
                    batch.uploaded_file_path = uploaded_file_path
                    batch.save()
                except Exception as e:
                    logger.error(f'Failed to upload file to S3: {str(e)}')
                
                # Process synchronously in background thread for immediate start
                # This ensures processing starts immediately and user sees progress
                import threading
                
                # Immediately update status and initialize metadata
                batch.status = 'PROCESSING'
                batch.started_at = timezone.now()
                batch.metadata = batch.metadata or {}
                batch.metadata['voucher_progress'] = {}
                batch.metadata['current_voucher_index'] = 0
                batch.save(update_fields=['status', 'started_at', 'metadata'])
                
                # Process in background thread for immediate start
                def process_batch_async():
                    try:
                        process_bulk_voucher_issuance_task(batch.id)
                    except Exception as e:
                        logger.error(f'Error processing batch {batch.id} in background: {str(e)}', traceback=traceback.format_exc())
                
                # Start processing in background thread
                thread = threading.Thread(target=process_batch_async, daemon=True)
                thread.start()
                
                messages.success(request, f'Batch {batch.batch_reference} processing started! You will see progress in real-time.')
                return redirect('voucher_bulk_status', batch_id=batch.id)
            
        except Exception as e:
            logger.error(f'Error processing bulk issuance: {str(e)}', traceback=traceback.format_exc())
            messages.error(request, f'Failed to process bulk issuance: {str(e)}')
            return redirect('voucher_issue_bulk')


class BulkIssuanceStatusView(LoginRequiredMixin, DetailView):
    """Bulk issuance status view"""
    model = BulkVoucherIssuanceBatch
    template_name = 'portal/vouchers/issuance/bulk_status.html'
    context_object_name = 'batch'
    pk_url_kwarg = 'batch_id'
    
    def get_queryset(self):
        # Only show batches created by current user
        return BulkVoucherIssuanceBatch.objects.filter(created_by=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        return context


class VoucherListView(LoginRequiredMixin, ListView):
    """List all vouchers"""
    model = GiftVoucher
    template_name = 'portal/vouchers/vouchers/list.html'
    context_object_name = 'vouchers'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('brand', 'created_by')
        brand_id = self.request.GET.get('brand_id')
        status_filter = self.request.GET.get('status')
        search_query = self.request.GET.get('search')
        
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search_query:
            queryset = queryset.filter(
                Q(voucher_code__icontains=search_query.replace('-', '')) |
                Q(reference_number__icontains=search_query)
            )
        
        return queryset.order_by('-issued_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['brands'] = GiftVoucherBrand.objects.filter(status='ACTIVE').order_by('brand_name')
        context['status_choices'] = GiftVoucher.STATUS_CHOICES
        context['current_brand'] = self.request.GET.get('brand_id', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        return context


class VoucherDetailView(LoginRequiredMixin, DetailView):
    """View voucher details and transaction history"""
    model = GiftVoucher
    template_name = 'portal/vouchers/vouchers/detail.html'
    context_object_name = 'voucher'
    pk_url_kwarg = 'voucher_id'
    
    def get_queryset(self):
        return super().get_queryset().select_related('brand', 'created_by').prefetch_related('transactions')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        voucher = self.get_object()
        # Exclude BALANCE_INQUIRY from report; balance checks are in logs only
        context['transactions'] = voucher.transactions.exclude(
            transaction_type='BALANCE_INQUIRY'
        ).order_by('-created_at')[:20]
        context['status_choices'] = GiftVoucher.STATUS_CHOICES
        # Calculate redeemed amount
        redeemed_amount = voucher.original_amount - voucher.current_balance
        context['redeemed_amount'] = redeemed_amount
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        # Sensitive details (full voucher code, mobile) only for users with permission or admin/super/staff
        user = self.request.user
        context['can_see_voucher_sensitive'] = (
            getattr(user, 'is_staff', False) or
            getattr(user, 'role_code', None) in ('super_admin', 'admin') or
            user.has_perm('portal.view_voucher_sensitive')
        )
        return context


class VoucherSearchView(LoginRequiredMixin, View):
    """Search voucher by code"""
    template_name = 'portal/vouchers/vouchers/search.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        from portal.utils.voucher_utils import unformat_voucher_code
        from portal.services.voucher_service import VoucherService
        
        voucher_code = request.POST.get('voucher_code', '').strip()
        if not voucher_code:
            messages.error(request, 'Please enter a voucher code')
            return redirect('voucher_search')
        
        try:
            voucher_service = VoucherService()
            voucher = voucher_service.validate_voucher_code(voucher_code)
            
            if voucher:
                return redirect('voucher_detail', voucher_id=voucher.id)
            else:
                messages.error(request, 'Voucher not found')
                return redirect('voucher_search')
        except Exception as e:
            logger.error(f'Error searching voucher: {str(e)}', traceback=traceback.format_exc())
            messages.error(request, 'Error searching voucher')
            return redirect('voucher_search')


class VoucherIssuanceReportView(LoginRequiredMixin, TemplateView):
    """Issuance report view"""
    template_name = 'portal/vouchers/reports/issuance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Sum, Count
        from datetime import datetime, timedelta
        
        brand_id = self.request.GET.get('brand_id')
        from_date = self.request.GET.get('from_date')
        to_date = self.request.GET.get('to_date')
        status_filter = self.request.GET.get('status')
        
        queryset = GiftVoucher.objects.select_related('brand', 'created_by')
        
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if from_date:
            queryset = queryset.filter(issued_at__gte=from_date)
        if to_date:
            queryset = queryset.filter(issued_at__lte=to_date)
        
        # Calculate totals
        from decimal import Decimal
        total_count = queryset.count()
        total_amount = queryset.aggregate(total=Sum('original_amount'))['total'] or Decimal('0.00')
        
        # Paginate
        from django.core.paginator import Paginator
        paginator = Paginator(queryset.order_by('-issued_at'), 50)
        page = self.request.GET.get('page', 1)
        page_obj = paginator.get_page(page)
        
        # Serialize items
        items = []
        for voucher in page_obj:
            items.append({
                'voucher_id': voucher.id,
                'reference_number': voucher.reference_number,
                'voucher_code': voucher.voucher_code,
                'brand_name': voucher.brand.brand_name,
                'amount': str(voucher.original_amount),
                'status': voucher.status,
                'issued_at': voucher.issued_at,
                'created_by': voucher.created_by.username if voucher.created_by else None
            })
        
        context.update({
            'vouchers': items,
            'brands': GiftVoucherBrand.objects.filter(status='ACTIVE').order_by('brand_name'),
            'status_choices': GiftVoucher.STATUS_CHOICES,
            'total_count': total_count,
            'total_amount': str(total_amount),
            'current_brand': brand_id or '',
            'current_status': status_filter or '',
            'from_date': from_date or '',
            'to_date': to_date or '',
            'page_obj': page_obj
        })
        return context


class VoucherRedemptionReportView(LoginRequiredMixin, TemplateView):
    """Redemption report view"""
    template_name = 'portal/vouchers/reports/redemption.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Sum
        from django.core.paginator import Paginator
        
        brand_id = self.request.GET.get('brand_id')
        from_date = self.request.GET.get('from_date')
        to_date = self.request.GET.get('to_date')
        
        queryset = GiftVoucherTransaction.objects.filter(
            transaction_type='REDEMPTION',
            transaction_status='SUCCESS'
        ).select_related('voucher', 'voucher__brand')
        
        if brand_id:
            queryset = queryset.filter(voucher__brand_id=brand_id)
        if from_date:
            queryset = queryset.filter(created_at__gte=from_date)
        if to_date:
            queryset = queryset.filter(created_at__lte=to_date)
        
        # Calculate totals
        from decimal import Decimal
        total_count = queryset.count()
        total_amount = queryset.aggregate(total=Sum('transaction_amount'))['total'] or Decimal('0.00')
        
        # Paginate
        paginator = Paginator(queryset.order_by('-created_at'), 50)
        page = self.request.GET.get('page', 1)
        page_obj = paginator.get_page(page)
        
        # Serialize items
        items = []
        for txn in page_obj:
            items.append({
                'transaction_id': txn.id,
                'voucher_code': txn.voucher.voucher_code,
                'reference_number': txn.voucher.reference_number,
                'brand_name': txn.voucher.brand.brand_name,
                'redeemed_amount': str(txn.transaction_amount),
                'redemption_method': txn.redemption_method,
                'transaction_status': txn.transaction_status,
                'created_at': txn.created_at
            })
        
        context.update({
            'transactions': items,
            'brands': GiftVoucherBrand.objects.filter(status='ACTIVE').order_by('brand_name'),
            'total_count': total_count,
            'total_amount': str(total_amount),
            'current_brand': brand_id or '',
            'from_date': from_date or '',
            'to_date': to_date or '',
            'page_obj': page_obj
        })
        return context


class VoucherOutstandingBalanceReportView(LoginRequiredMixin, TemplateView):
    """Outstanding balance report view"""
    template_name = 'portal/vouchers/reports/outstanding.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from decimal import Decimal
        from django.db.models import Sum
        
        # Get all active and partially redeemed vouchers
        vouchers = GiftVoucher.objects.filter(
            status__in=['ACTIVE', 'PARTIALLY_REDEEMED']
        ).select_related('brand')
        
        total_outstanding = vouchers.aggregate(
            total=Sum('current_balance')
        )['total'] or Decimal('0.00')
        
        total_vouchers = vouchers.count()
        
        # Group by brand
        by_brand = vouchers.values('brand__brand_name', 'brand__brand_code').annotate(
            count=Count('id'),
            total_balance=Sum('current_balance')
        ).order_by('-total_balance')
        
        context.update({
            'total_outstanding': total_outstanding,
            'total_vouchers': total_vouchers,
            'by_brand': by_brand,
            'vouchers': vouchers.order_by('-issued_at')[:100],
        })
        return context


# ============================================================================
# VOUCHERX UNIFIED SOLUTION
# ============================================================================

class VoucherXDashboardView(LoginRequiredMixin, View):
    """VoucherX unified dashboard view"""
    template_name = 'portal/voucherx/dashboard.html'
    permission_class = CanAccessVoucherX()
    
    def get(self, request):
        # Check permission
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to access VoucherX.')
            return redirect('dashboard')
        from portal.services.voucherx_service import VoucherXService
        
        service = VoucherXService()
        
        # Get dashboard statistics
        stats = service.get_dashboard_stats(request.user)
        
        # Get recent activity
        recent_activity = service.get_recent_activity(request.user, limit=10)
        
        # Get pending tasks
        pending_tasks = service.get_pending_tasks(request.user)
        
        # Get brand summary
        brand_summary = service.get_brand_summary()
        
        # Get issuance summary for today
        issuance_today = service.get_issuance_summary('today')
        
        # Get batch statistics
        from portal.models import BulkVoucherIssuanceBatch
        pending_batches_count = BulkVoucherIssuanceBatch.objects.filter(status='PENDING').count()
        processing_batches_count = BulkVoucherIssuanceBatch.objects.filter(status='PROCESSING').count()
        completed_batches_count = BulkVoucherIssuanceBatch.objects.filter(status='COMPLETED').count()
        failed_batches_count = BulkVoucherIssuanceBatch.objects.filter(status='FAILED').count()
        
        # Log dashboard access
        log_voucher_operation(
            operation='dashboard_accessed',
            log_level='INFO',
            message='VoucherX dashboard accessed',
            user_id=request.user.id,
            request=request,
            extra_data={'user': request.user.username}
        )
        
        return render(request, self.template_name, {
            'stats': stats,
            'recent_activity': recent_activity,
            'pending_tasks': pending_tasks,
            'brand_summary': brand_summary,
            'issuance_today': issuance_today,
            'pending_batches_count': pending_batches_count,
            'processing_batches_count': processing_batches_count,
            'completed_batches_count': completed_batches_count,
            'failed_batches_count': failed_batches_count,
        })


class VoucherXBalanceCheckView(LoginRequiredMixin, View):
    """VoucherX - Check voucher balance by code; PIN required for non-admin users"""
    template_name = 'portal/voucherx/balance_check.html'
    permission_class = CanAccessVoucherX()

    def _is_admin_user(self, user):
        return getattr(user, 'role_code', None) in ('super_admin', 'admin') or getattr(user, 'is_staff', False)

    def get(self, request):
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to access VoucherX.')
            return redirect('dashboard')
        return render(request, self.template_name, {
            'result': None,
            'pin_required': not self._is_admin_user(request.user)
        })

    def post(self, request):
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to access VoucherX.')
            return redirect('dashboard')
        voucher_code = (request.POST.get('voucher_code') or '').strip()
        pin = (request.POST.get('pin') or '').strip()
        include_transactions = request.POST.get('include_transactions') == 'on'
        is_admin = self._is_admin_user(request.user)
        if not voucher_code:
            messages.error(request, 'Voucher code is required.')
            return render(request, self.template_name, {'result': None, 'pin_required': not is_admin})
        if not is_admin and not pin:
            messages.error(request, 'Voucher code and PIN are required.')
            return render(request, self.template_name, {'result': None, 'pin_required': True})
        try:
            from portal.services.voucher_service import VoucherService
            from portal.utils.voucher_utils import format_voucher_code
            service = VoucherService()
            if is_admin:
                result = service.check_balance_without_pin(
                    voucher_code=voucher_code,
                    include_transactions=include_transactions
                )
            else:
                result = service.check_balance(
                    voucher_code=voucher_code,
                    pin=pin,
                    include_transactions=include_transactions
                )
            result['voucher_code_display'] = format_voucher_code(
                voucher_code.replace('-', '').upper()
            ) if len(voucher_code.replace('-', '')) == 16 else voucher_code
            log_voucher_operation(
                operation='voucherx_balance_check',
                log_level='INFO',
                message='VoucherX balance checked',
                user_id=request.user.id,
                request=request,
                extra_data={'reference_number': result.get('reference_number'), 'admin_check': is_admin}
            )
            return render(request, self.template_name, {'result': result, 'pin_required': not is_admin})
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, self.template_name, {'result': None, 'pin_required': not is_admin})
        except Exception as e:
            logger.exception('VoucherX balance check failed')
            messages.error(request, 'Balance check failed. Please try again.')
            return render(request, self.template_name, {'result': None, 'pin_required': not is_admin})


class VoucherXDebitView(LoginRequiredMixin, View):
    """VoucherX - Use voucher balance (debit/redeem) by code, PIN and amount"""
    template_name = 'portal/voucherx/debit.html'
    permission_class = CanAccessVoucherX()

    def get(self, request):
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to access VoucherX.')
            return redirect('dashboard')
        return render(request, self.template_name, {'result': None})

    def post(self, request):
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to access VoucherX.')
            return redirect('dashboard')
        voucher_code = (request.POST.get('voucher_code') or '').strip()
        pin = (request.POST.get('pin') or '').strip()
        amount_str = (request.POST.get('amount') or '').strip()
        transaction_ref = (request.POST.get('transaction_ref') or '').strip() or None
        if not voucher_code or not pin:
            messages.error(request, 'Voucher code and PIN are required.')
            return render(request, self.template_name, {'result': None})
        if not amount_str:
            messages.error(request, 'Amount is required.')
            return render(request, self.template_name, {'result': None})
        try:
            amount = Decimal(amount_str)
        except Exception:
            messages.error(request, 'Enter a valid amount (e.g. 100 or 99.50).')
            return render(request, self.template_name, {'result': None})
        try:
            from portal.services.voucher_service import VoucherService
            from portal.utils.voucher_utils import format_voucher_code
            from portal.utils.ip_utils import get_client_ip, get_user_agent
            service = VoucherService()
            result = service.redeem_voucher_pin(
                voucher_code=voucher_code,
                pin=pin,
                amount=amount,
                transaction_ref=transaction_ref,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            result['voucher_code_display'] = format_voucher_code(
                voucher_code.replace('-', '').upper()
            ) if len(voucher_code.replace('-', '')) == 16 else voucher_code
            log_voucher_operation(
                operation='voucherx_debit',
                log_level='INFO',
                message=f'VoucherX debit - Amount: {amount}',
                user_id=request.user.id,
                request=request,
                extra_data={
                    'transaction_id': result.get('transaction_id'),
                    'reference_number': result.get('reference_number'),
                    'amount': str(amount)
                }
            )
            messages.success(request, f'₹{result["redeemed_amount"]} debited successfully. New balance: ₹{result["balance_after"]}')
            return render(request, self.template_name, {'result': result})
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, self.template_name, {'result': None})
        except Exception as e:
            logger.exception('VoucherX debit failed')
            messages.error(request, 'Debit fail. Please try again.')
            return render(request, self.template_name, {'result': None})


class VoucherXTabbedView(LoginRequiredMixin, View):
    """VoucherX tabbed interface view"""
    template_name = 'portal/voucherx/tabbed.html'
    permission_class = CanAccessVoucherX()
    
    def get(self, request):
        # Check permission
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to access VoucherX.')
            return redirect('dashboard')
        tab = request.GET.get('tab', 'brands')
        
        # Log tabbed view access
        log_voucher_operation(
            operation='tabbed_view_accessed',
            log_level='INFO',
            message=f'VoucherX tabbed view accessed - Tab: {tab}',
            user_id=request.user.id,
            request=request,
            extra_data={'active_tab': tab, 'user': request.user.username}
        )
        
        context = {
            'active_tab': tab,
        }
        
        # Load data based on active tab
        if tab == 'brands':
            brands = GiftVoucherBrand.objects.all().order_by('-created_at')[:20]
            context['brands'] = brands
            
        elif tab == 'onboarding':
            # Pending reviews for admins
            if request.user.role_code in ['super_admin', 'admin'] or request.user.is_staff:
                pending_brands = GiftVoucherBrand.objects.filter(
                    onboarding_status='SUBMITTED'
                ).select_related('created_by').order_by('-updated_at')[:20]
                context['pending_brands'] = pending_brands
            
            # In-progress brands
            in_progress_brands = GiftVoucherBrand.objects.filter(
                onboarding_status='IN_PROGRESS'
            ).select_related('created_by').order_by('-updated_at')[:20]
            context['in_progress_brands'] = in_progress_brands
            
        elif tab == 'issuance':
            # Get brands that can issue vouchers
            all_brands = GiftVoucherBrand.objects.all()
            available_brands = [brand for brand in all_brands if brand.can_issue_vouchers()]
            context['available_brands'] = available_brands
            
            # Recent batches
            recent_batches = BulkVoucherIssuanceBatch.objects.filter(
                created_by=request.user
            ).select_related('brand').order_by('-created_at')[:10]
            context['recent_batches'] = recent_batches
            
        elif tab == 'vouchers':
            vouchers = GiftVoucher.objects.select_related(
                'brand', 'created_by'
            ).order_by('-issued_at')[:50]
            context['vouchers'] = vouchers
            
        elif tab == 'reports':
            from portal.services.voucherx_service import VoucherXService
            service = VoucherXService()
            context['issuance_summary'] = service.get_issuance_summary('month')
            context['brand_summary'] = service.get_brand_summary()
        
        return render(request, self.template_name, context)


class BrandAdminOnboardingView(LoginRequiredMixin, View):
    """Admin view to create and onboard brand in one flow"""
    template_name = 'portal/voucherx/admin_onboard.html'
    permission_class = CanManageVoucherXBrands()
    
    def get(self, request):
        # Check permission
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to onboard brands.')
            return redirect('voucherx_dashboard')
        
        form = BrandAdminOnboardingForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        # Check permission
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to onboard brands.')
            return redirect('voucherx_dashboard')
        
        form = BrandAdminOnboardingForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                from portal.services.brand_onboarding_service import BrandOnboardingService
                from portal.services.storage_service import StorageService
                
                data = form.cleaned_data
                auto_approve = data.get('auto_approve', False)
                
                # Create brand
                brand = GiftVoucherBrand.objects.create(
                    brand_name=data['brand_name'],
                    contact_person=data['contact_person'],
                    contact_email=data['contact_email'],
                    contact_phone=data['contact_phone'],
                    address=data['address'],
                    business_type=data['business_type'],
                    business_reg_no=data['business_reg_no'],
                    pan_number=data.get('pan_number', ''),
                    gst_number=data.get('gst_number', ''),
                    bank_ifsc_code=data['bank_ifsc_code'],
                    bank_name=data['bank_name'],
                    account_holder_name=data['account_holder_name'],
                    terms_accepted=data['terms_accepted'],
                    agreement_signed=data['agreement_signed'],
                    created_by=request.user,
                    onboarding_status='IN_PROGRESS',
                    status='INACTIVE'
                )
                
                # Set encrypted bank account
                brand.set_encrypted_bank_account(data['bank_account_number'])
                
                # Handle document uploads
                storage_service = StorageService()
                doc_fields = {
                    'business_registration_doc': 'business_registration',
                    'pan_document': 'pan',
                    'gst_certificate': 'gst',
                    'bank_statement': 'bank_statement',
                    'agreement_document': 'agreement'
                }
                
                for field_name, doc_type in doc_fields.items():
                    file = request.FILES.get(field_name)
                    if file:
                        # Validate file
                        if file.size > 10 * 1024 * 1024:  # 10MB limit
                            messages.error(request, f'{field_name.replace("_", " ").title()} file is too large (max 10MB)')
                            brand.delete()
                            return render(request, self.template_name, {'form': form})
                        
                        # Upload to S3
                        try:
                            import os
                            from datetime import datetime
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            safe_filename = os.path.basename(file.name)
                            path = f"brands/{brand.id}/onboarding/{doc_type}/{timestamp}_{safe_filename}"
                            s3_url = storage_service.s3_client.upload_file(file, path)
                            setattr(brand, field_name, s3_url)
                        except Exception as e:
                            logger.error(f'Error uploading {field_name}: {str(e)}', traceback=traceback.format_exc())
                            messages.error(request, f'Failed to upload {field_name.replace("_", " ").title()}')
                            brand.delete()
                            return render(request, self.template_name, {'form': form})
                
                # Set timestamps
                from django.utils import timezone
                if data['terms_accepted']:
                    brand.terms_accepted_at = timezone.now()
                if data['agreement_signed']:
                    brand.agreement_signed_at = timezone.now()
                
                brand.save()
                
                # If auto-approve, approve immediately
                if auto_approve:
                    brand.approve_onboarding(request.user)
                    log_voucher_operation(
                        operation='brand_created_and_approved',
                        log_level='INFO',
                        message=f'Brand created and approved - {brand.brand_name}',
                        user_id=request.user.id,
                        request=request,
                        extra_data={
                            'brand_id': brand.id,
                            'brand_name': brand.brand_name,
                            'brand_code': brand.brand_code,
                            'auto_approve': True,
                            'approved_by': request.user.username
                        }
                    )
                    messages.success(request, f'Brand "{brand.brand_name}" created and approved successfully. It can now issue vouchers.')
                else:
                    # Mark as submitted for review
                    brand.submit_for_approval()
                    log_voucher_operation(
                        operation='brand_created',
                        log_level='INFO',
                        message=f'Brand created and submitted for review - {brand.brand_name}',
                        user_id=request.user.id,
                        request=request,
                        extra_data={
                            'brand_id': brand.id,
                            'brand_name': brand.brand_name,
                            'brand_code': brand.brand_code,
                            'onboarding_status': brand.onboarding_status
                        }
                    )
                    messages.success(request, f'Brand "{brand.brand_name}" created and submitted for review.')
                
                return redirect('voucherx_dashboard')
                
            except Exception as e:
                log_voucher_operation(
                    operation='brand_creation_failed',
                    log_level='ERROR',
                    message=f'Error creating brand: {str(e)}',
                    user_id=request.user.id,
                    request=request,
                    extra_data={'error': str(e)},
                    exception=e
                )
                logger.error(f'Error creating brand: {str(e)}', traceback=traceback.format_exc())
                messages.error(request, f'An error occurred: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
        
        return render(request, self.template_name, {'form': form})


class VoucherXQuickIssueWizard(LoginRequiredMixin, View):
    """Quick issue wizard for step-by-step voucher issuance"""
    template_name = 'portal/voucherx/wizard_issue.html'
    permission_class = CanIssueVouchers()
    
    def get(self, request):
        # Check permission
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to issue vouchers.')
            return redirect('voucherx_dashboard')
        step = int(request.GET.get('step', 1))
        
        # Get brands that can issue vouchers
        all_brands = GiftVoucherBrand.objects.all()
        available_brands = [brand for brand in all_brands if brand.can_issue_vouchers()]
        
        context = {
            'step': step,
            'available_brands': available_brands,
        }
        
        # Pre-fill from session if returning
        if step == 2:
            context['selected_brand_id'] = request.session.get('wizard_brand_id')
            context['issuance_type'] = request.session.get('wizard_issuance_type', 'single')
            # Get brand for display
            brand_id = request.session.get('wizard_brand_id')
            if brand_id:
                try:
                    context['selected_brand'] = GiftVoucherBrand.objects.get(id=brand_id)
                except GiftVoucherBrand.DoesNotExist:
                    pass
        elif step == 3:
            context['selected_brand_id'] = request.session.get('wizard_brand_id')
            context['issuance_type'] = request.session.get('wizard_issuance_type', 'single')
            context['amount'] = request.session.get('wizard_amount')
            context['mobile_number'] = request.session.get('wizard_mobile_number')
            
            # Get brand for display
            brand_id = request.session.get('wizard_brand_id')
            if brand_id:
                try:
                    context['selected_brand'] = GiftVoucherBrand.objects.get(id=brand_id)
                except GiftVoucherBrand.DoesNotExist:
                    pass
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        from django.urls import reverse
        
        # Check permission
        if not self.permission_class.has_permission(request, self):
            messages.error(request, 'You do not have permission to issue vouchers.')
            return redirect('voucherx_dashboard')
        
        step = int(request.POST.get('step', 1))
        wizard_url = reverse('voucherx_wizard_issue')
        
        if step == 1:
            # Step 1: Select brand and issuance type
            brand_id = request.POST.get('brand_id')
            issuance_type = request.POST.get('issuance_type', 'single')
            
            if not brand_id:
                messages.error(request, 'Please select a brand')
                return redirect(f"{wizard_url}?step=1")
            
            # Store in session
            request.session['wizard_brand_id'] = int(brand_id)
            request.session['wizard_issuance_type'] = issuance_type
            
            return redirect(f"{wizard_url}?step=2")
        
        elif step == 2:
            # Step 2: Enter details
            brand_id = request.session.get('wizard_brand_id')
            issuance_type = request.session.get('wizard_issuance_type', 'single')
            
            if not brand_id:
                messages.error(request, 'Please start from step 1')
                return redirect(f"{wizard_url}?step=1")
            
            amount = request.POST.get('amount')
            mobile_number = request.POST.get('mobile_number', '').strip() or None
            
            if not amount or float(amount) <= 0:
                messages.error(request, 'Please enter a valid amount')
                return redirect(f"{wizard_url}?step=2")
            
            # Store in session
            request.session['wizard_amount'] = amount
            request.session['wizard_mobile_number'] = mobile_number
            
            return redirect(f"{wizard_url}?step=3")
        
        elif step == 3:
            # Step 3: Review and confirm
            brand_id = request.session.get('wizard_brand_id')
            issuance_type = request.session.get('wizard_issuance_type', 'single')
            amount = request.session.get('wizard_amount')
            mobile_number = request.session.get('wizard_mobile_number')
            
            if not all([brand_id, amount]):
                messages.error(request, 'Missing required information')
                return redirect(f"{wizard_url}?step=1")
            
            try:
                from portal.services.voucher_service import VoucherService
                from decimal import Decimal
                
                voucher_service = VoucherService()
                
                if issuance_type == 'single':
                    result = voucher_service.issue_single_voucher(
                        brand_id=int(brand_id),
                        amount=Decimal(amount),
                        mobile_number=mobile_number,
                        created_by=request.user,
                        issued_by=request.user,
                        issuer_type='ADMIN'
                    )
                    
                    # Log wizard voucher issuance
                    log_voucher_operation(
                        operation='voucher_issued_wizard',
                        log_level='INFO',
                        message=f'Voucher issued via wizard - Brand ID: {brand_id}, Amount: {amount}',
                        user_id=request.user.id,
                        request=request,
                        extra_data={
                            'voucher_id': result.get('voucher_id'),
                            'brand_id': brand_id,
                            'amount': str(amount),
                            'wizard_step': step
                        }
                    )
                    
                    # Clear session
                    request.session.pop('wizard_brand_id', None)
                    request.session.pop('wizard_issuance_type', None)
                    request.session.pop('wizard_amount', None)
                    request.session.pop('wizard_mobile_number', None)
                    
                    # Store result for success page
                    request.session['voucher_issue_result'] = result
                    messages.success(request, 'Voucher issued successfully!')
                    return redirect('voucher_issue_single_success')
                else:
                    # For bulk, redirect to bulk issuance page with pre-filled brand
                    messages.info(request, 'Please use the bulk issuance page for bulk operations')
                    return redirect(f'voucher_issue_bulk?brand_id={brand_id}&from=voucherx')
                    
            except ValueError as e:
                log_voucher_operation(
                    operation='voucher_issuance_failed_wizard',
                    log_level='WARNING',
                    message=f'Wizard voucher issuance failed (validation): {str(e)}',
                    user_id=request.user.id,
                    request=request,
                    extra_data={'error': str(e), 'wizard_step': step}
                )
                messages.error(request, str(e))
                return redirect(f"{wizard_url}?step=2")
            except Exception as e:
                log_voucher_operation(
                    operation='voucher_issuance_failed_wizard',
                    log_level='ERROR',
                    message=f'Wizard voucher issuance failed: {str(e)}',
                    user_id=request.user.id,
                    request=request,
                    extra_data={'error': str(e), 'wizard_step': step},
                    exception=e
                )
                logger.error(f'Error issuing voucher: {str(e)}', traceback=traceback.format_exc())
                messages.error(request, 'Failed to issue voucher')
                return redirect(f"{wizard_url}?step=2")
        
        return redirect(f"{wizard_url}?step=1")


class VoucherOutstandingBalanceReportView(LoginRequiredMixin, TemplateView):
    """Outstanding balance report view"""
    template_name = 'portal/vouchers/reports/outstanding.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Sum
        from django.core.paginator import Paginator
        
        brand_id = self.request.GET.get('brand_id')
        
        queryset = GiftVoucher.objects.filter(
            status__in=['ACTIVE', 'PARTIALLY_REDEEMED']
        ).select_related('brand')
        
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        
        # Calculate totals
        total_count = queryset.count()
        from decimal import Decimal
        total_outstanding = queryset.aggregate(total=Sum('current_balance'))['total'] or Decimal('0.00')
        total_issued = queryset.aggregate(total=Sum('original_amount'))['total'] or Decimal('0.00')
        total_redeemed = total_issued - total_outstanding
        
        # Paginate
        paginator = Paginator(queryset.order_by('-issued_at'), 50)
        page = self.request.GET.get('page', 1)
        page_obj = paginator.get_page(page)
        
        # Serialize items with redeemed amount
        items = []
        for voucher in page_obj:
            redeemed_amount = voucher.original_amount - voucher.current_balance
            items.append({
                'voucher_id': voucher.id,
                'voucher_code': voucher.voucher_code,
                'reference_number': voucher.reference_number,
                'brand_name': voucher.brand.brand_name,
                'original_amount': str(voucher.original_amount),
                'current_balance': str(voucher.current_balance),
                'redeemed_amount': str(redeemed_amount),
                'status': voucher.status,
                'issued_at': voucher.issued_at,
                'last_transaction_at': voucher.last_transaction_at
            })
        
        context.update({
            'vouchers': items,
            'brands': GiftVoucherBrand.objects.filter(status='ACTIVE').order_by('brand_name'),
            'clients': VoucherClient.objects.filter(status='ACTIVE').order_by('client_name'),
            'total_count': total_count,
            'total_outstanding': str(total_outstanding),
            'total_issued': str(total_issued),
            'total_redeemed': str(total_redeemed),
            'current_brand': brand_id or '',
            'current_client': client_id or '',
            'page_obj': page_obj
        })
        return context


# ============================================================================
# VOUCHER CLIENT MANAGEMENT VIEWS
# ============================================================================

class VoucherClientListView(LoginRequiredMixin, ListView):
    """List all voucher clients"""
    model = VoucherClient
    template_name = 'portal/vouchers/clients/list.html'
    context_object_name = 'clients'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('brand', 'created_by')
        brand_id = self.request.GET.get('brand_id')
        status_filter = self.request.GET.get('status')
        search_query = self.request.GET.get('search')
        
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search_query:
            queryset = queryset.filter(
                Q(client_name__icontains=search_query) |
                Q(client_code__icontains=search_query) |
                Q(contact_email__icontains=search_query)
            )
        
        return queryset.order_by('-is_default', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['brands'] = GiftVoucherBrand.objects.filter(status='ACTIVE').order_by('brand_name')
        context['status_choices'] = VoucherClient.STATUS_CHOICES
        context['current_brand'] = self.request.GET.get('brand_id', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        return context
    
    def get(self, request, *args, **kwargs):
        # Support JSON format for AJAX calls
        if request.GET.get('format') == 'json':
            brand_id = request.GET.get('brand_id')
            clients = self.get_queryset()
            if brand_id:
                clients = clients.filter(brand_id=brand_id)
            
            from django.http import JsonResponse
            return JsonResponse({
                'clients': [
                    {
                        'id': client.id,
                        'client_name': client.client_name,
                        'client_code': client.client_code,
                        'is_default': client.is_default
                    }
                    for client in clients
                ]
            })
        
        return super().get(request, *args, **kwargs)


class VoucherClientCreateView(LoginRequiredMixin, View):
    """Create new voucher client"""
    template_name = 'portal/vouchers/clients/create.html'
    
    def get(self, request):
        brand_id = request.GET.get('brand_id')
        brands = GiftVoucherBrand.objects.filter(status='ACTIVE', onboarding_status='APPROVED').order_by('brand_name')
        
        return render(request, self.template_name, {
            'brands': brands,
            'selected_brand_id': brand_id,
            'from_voucherx': request.GET.get('from') == 'voucherx'
        })
    
    def post(self, request):
        from portal.services.voucher_client_service import VoucherClientService
        
        brand_id = request.POST.get('brand_id')
        client_name = request.POST.get('client_name', '').strip()
        contact_person = request.POST.get('contact_person', '').strip()
        contact_email = request.POST.get('contact_email', '').strip()
        contact_phone = request.POST.get('contact_phone', '').strip()
        is_default = request.POST.get('is_default') == 'on'
        
        if not brand_id:
            messages.error(request, 'Brand is required')
            return redirect('voucher_client_create')
        if not client_name:
            messages.error(request, 'Client name is required')
            return redirect('voucher_client_create')
        
        try:
            client_service = VoucherClientService()
            client = client_service.create_client(
                brand_id=int(brand_id),
                client_data={
                    'client_name': client_name,
                    'contact_person': contact_person or None,
                    'contact_email': contact_email or None,
                    'contact_phone': contact_phone or None,
                    'is_default': is_default,
                    'status': 'ACTIVE'
                },
                created_by=request.user
            )
            
            messages.success(request, f'Client "{client.client_name}" created successfully')
            if request.GET.get('from') == 'voucherx':
                return redirect('voucherx_dashboard')
            return redirect('voucher_client_list')
            
        except Exception as e:
            logger.error(f'Error creating client: {str(e)}', traceback=traceback.format_exc())
            messages.error(request, f'Error creating client: {str(e)}')
            return redirect('voucher_client_create')


class VoucherClientDetailView(LoginRequiredMixin, DetailView):
    """View and edit voucher client details"""
    model = VoucherClient
    template_name = 'portal/vouchers/clients/detail.html'
    context_object_name = 'client'
    pk_url_kwarg = 'client_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        return context
    
    def post(self, request, client_id):
        """Update client"""
        from portal.services.voucher_client_service import VoucherClientService
        
        client = get_object_or_404(VoucherClient, id=client_id)
        client_service = VoucherClientService()
        
        try:
            client_service.update_client(
                client_id=client_id,
                client_data={
                    'client_name': request.POST.get('client_name', '').strip(),
                    'contact_person': request.POST.get('contact_person', '').strip(),
                    'contact_email': request.POST.get('contact_email', '').strip(),
                    'contact_phone': request.POST.get('contact_phone', '').strip(),
                    'status': request.POST.get('status', 'ACTIVE')
                }
            )
            messages.success(request, 'Client updated successfully')
        except Exception as e:
            logger.error(f'Error updating client: {str(e)}', traceback=traceback.format_exc())
            messages.error(request, f'Error updating client: {str(e)}')
        
        return redirect('voucher_client_detail', client_id=client.id)


class VoucherClientDeleteView(LoginRequiredMixin, View):
    """Deactivate voucher client"""
    
    def post(self, request, client_id):
        from portal.services.voucher_client_service import VoucherClientService
        
        client_service = VoucherClientService()
        
        try:
            client_service.deactivate_client(client_id)
            messages.success(request, 'Client deactivated successfully')
        except Exception as e:
            logger.error(f'Error deactivating client: {str(e)}', traceback=traceback.format_exc())
            messages.error(request, f'Error deactivating client: {str(e)}')
        
        return redirect('voucher_client_list')


# ============================================================================
# VOUCHER BATCH MANAGEMENT VIEWS
# ============================================================================

class VoucherBatchListView(LoginRequiredMixin, ListView):
    """List all voucher batches"""
    model = BulkVoucherIssuanceBatch
    template_name = 'portal/vouchers/batches/list.html'
    context_object_name = 'batches'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('brand', 'client', 'issued_by', 'created_by')
        brand_id = self.request.GET.get('brand_id')
        client_id = self.request.GET.get('client_id')
        issuer_type = self.request.GET.get('issuer_type')
        status_filter = self.request.GET.get('status')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        if issuer_type:
            queryset = queryset.filter(issuer_type=issuer_type)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['brands'] = GiftVoucherBrand.objects.filter(status='ACTIVE').order_by('brand_name')
        context['clients'] = VoucherClient.objects.filter(status='ACTIVE').order_by('client_name')
        context['status_choices'] = BulkVoucherIssuanceBatch.STATUS_CHOICES
        context['issuer_type_choices'] = BulkVoucherIssuanceBatch.ISSUER_TYPE_CHOICES
        context['current_brand'] = self.request.GET.get('brand_id', '')
        context['current_client'] = self.request.GET.get('client_id', '')
        context['current_issuer_type'] = self.request.GET.get('issuer_type', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        return context


class VoucherBatchDetailView(LoginRequiredMixin, DetailView):
    """View batch details with denomination breakdown"""
    model = BulkVoucherIssuanceBatch
    template_name = 'portal/vouchers/batches/detail.html'
    context_object_name = 'batch'
    pk_url_kwarg = 'batch_id'
    
    def get_queryset(self):
        return super().get_queryset().select_related('brand', 'client', 'issued_by', 'created_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from portal.services.bulk_voucher_service import BulkVoucherService
        
        batch = self.get_object()
        bulk_service = BulkVoucherService()
        
        # Get denomination breakdown
        breakdown = bulk_service.generate_denomination_breakdown(batch)
        context['denomination_breakdown'] = breakdown
        
        # Get vouchers in this batch (if tracked in metadata)
        vouchers = GiftVoucher.objects.filter(
            metadata__batch_id=batch.id
        ).select_related('brand', 'client', 'issued_by')[:100]  # Limit for display
        context['vouchers'] = vouchers
        context['vouchers_count'] = GiftVoucher.objects.filter(metadata__batch_id=batch.id).count()
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        
        # Add processing and export flags
        context['can_process'] = batch.status in ['PENDING', 'FAILED']
        context['can_export'] = batch.status == 'COMPLETED'
        context['export_available'] = bool(batch.result_file_path) if batch.status == 'COMPLETED' else False
        
        return context


class VoucherBatchProcessView(LoginRequiredMixin, View):
    """Manually process or retry a batch with locking"""
    
    def post(self, request, batch_id):
        from portal.tasks.voucher_tasks import process_bulk_voucher_issuance_task
        from django.db import transaction
        
        batch = get_object_or_404(BulkVoucherIssuanceBatch, id=batch_id)
        
        # Check if already processing (database-level lock check)
        if batch.status == 'PROCESSING':
            if batch.processing_locked_at:
                time_diff = (timezone.now() - batch.processing_locked_at).total_seconds()
                if time_diff < 3600:  # Lock is less than 1 hour old
                    messages.warning(request, 'Batch is already being processed')
                    return redirect('voucher_batch_processing', batch_id=batch_id)
        
        # Only allow processing PENDING or FAILED batches
        if batch.status not in ['PENDING', 'FAILED']:
            messages.error(request, f'Cannot process batch with status: {batch.get_status_display()}')
            return redirect('voucher_batch_detail', batch_id=batch_id)
        
        # Acquire lock using select_for_update (database-level)
        try:
            with transaction.atomic():
                # Lock the row for update
                batch = BulkVoucherIssuanceBatch.objects.select_for_update().get(id=batch_id)
                
                # Double-check status after lock
                if batch.status == 'PROCESSING':
                    if batch.processing_locked_at:
                        time_diff = (timezone.now() - batch.processing_locked_at).total_seconds()
                        if time_diff < 3600:
                            messages.warning(request, 'Batch is already being processed')
                            return redirect('voucher_batch_processing', batch_id=batch_id)
                
                # Set lock
                batch.processing_locked_at = timezone.now()
                batch.processing_locked_by = request.user
                
                # Immediately update status and initialize metadata before queuing task
                # This ensures the processing page shows PROCESSING status instantly
                batch.status = 'PROCESSING'
                batch.started_at = timezone.now()
                batch.metadata = batch.metadata or {}
                batch.metadata['voucher_progress'] = {}
                batch.metadata['current_voucher_index'] = 0
                batch.save(update_fields=['processing_locked_at', 'processing_locked_by', 'status', 'started_at', 'metadata'])
            
            # Immediately process first voucher synchronously for instant feedback (MANUAL_BULK only)
            # This ensures user sees progress immediately
            if batch.issuance_method == 'MANUAL_BULK':
                try:
                    from portal.services.voucher_service import VoucherService
                    from portal.utils.voucher_utils import format_voucher_code
                    from decimal import Decimal
                    
                    voucher_service = VoucherService()
                    denomination_breakdown = batch.denomination_breakdown or {}
                    first_amount = None
                    
                    # Get first denomination with quantity > 0
                    for amount_str, denom_data in denomination_breakdown.items():
                        if denom_data.get('quantity', 0) > 0:
                            first_amount = Decimal(amount_str)
                            break
                    
                    # Process first voucher immediately if we have an amount
                    if first_amount:
                        try:
                            result = voucher_service.issue_single_voucher(
                                brand_id=batch.brand.id,
                                amount=first_amount,
                                mobile_number=None,
                                created_by=batch.created_by,
                                issued_by=batch.issued_by,
                                issuer_type=batch.issuer_type or 'ADMIN'
                            )
                            
                            # Update batch metadata to show first voucher completed
                            batch.refresh_from_db()
                            batch.metadata = batch.metadata or {}
                            batch.metadata['voucher_progress'] = batch.metadata.get('voucher_progress', {})
                            voucher_code = result.get('voucher_code', '')
                            # Format voucher code for display
                            if voucher_code and '-' not in voucher_code:
                                formatted_code = format_voucher_code(voucher_code) if len(voucher_code) == 16 else voucher_code
                            else:
                                formatted_code = voucher_code
                            
                            batch.metadata['voucher_progress']['1'] = {
                                'status': 'completed',
                                'voucher_id': result.get('voucher_id'),
                                'voucher_code': formatted_code,
                                'processed_at': timezone.now().isoformat()
                            }
                            batch.metadata['current_voucher_index'] = 1
                            batch.successful_vouchers = 1
                            batch.processed_vouchers = 1
                            batch.save(update_fields=['metadata', 'successful_vouchers', 'processed_vouchers'])
                            
                            logger.info(f'Immediately processed first voucher for batch {batch.batch_reference}')
                        except Exception as e:
                            logger.error(f'Error processing first voucher immediately: {str(e)}', traceback=traceback.format_exc())
                            # Continue with normal processing - don't fail the whole batch
                except Exception as e:
                    logger.error(f'Error in immediate first voucher processing: {str(e)}', traceback=traceback.format_exc())
                    # Continue with normal Celery queueing
            
            # Check if Celery worker is available
            celery_available = False
            try:
                from celery import current_app
                inspect = current_app.control.inspect()
                active_workers = inspect.active()
                celery_available = active_workers is not None and len(active_workers) > 0
            except Exception:
                pass
            
            if celery_available:
                # Queue task and get task ID
                task = process_bulk_voucher_issuance_task.delay(batch.id)
                batch.celery_task_id = task.id
                batch.save()
                
                # Verify task is actually queued (check after 2 seconds)
                import time
                time.sleep(2)
                try:
                    from celery.result import AsyncResult
                    from celery import current_app
                    task_result = AsyncResult(task.id, app=current_app)
                    if task_result.state == 'PENDING':
                        # Task is still pending - might be stuck, process synchronously
                        logger.warning(f'Task {task.id} still pending after 2s, processing synchronously')
                        try:
                            result = process_bulk_voucher_issuance_task(batch.id)
                            batch.refresh_from_db()
                            if batch.status == 'COMPLETED':
                                messages.success(request, f'Batch {batch.batch_reference} processed successfully! {batch.successful_vouchers} vouchers created.')
                            elif batch.status == 'FAILED':
                                messages.error(request, f'Batch {batch.batch_reference} processing failed: {batch.error_log or "Unknown error"}')
                            else:
                                messages.warning(request, f'Batch {batch.batch_reference} processing completed with status: {batch.status}')
                            return redirect('voucher_batch_processing', batch_id=batch_id)
                        except Exception as sync_error:
                            logger.error(f'Error processing batch synchronously after task pending: {str(sync_error)}', traceback=traceback.format_exc())
                            # Continue - task might still execute
                except Exception as e:
                    logger.error(f'Error checking task status: {str(e)}')
                    # Continue - task might still execute
                
                if batch.status == 'FAILED':
                    messages.success(request, f'Batch {batch.batch_reference} queued for retry')
                else:
                    messages.success(request, f'Batch {batch.batch_reference} queued for processing')
            else:
                # Celery worker not available - process synchronously
                try:
                    # Process synchronously
                    result = process_bulk_voucher_issuance_task(batch.id)
                    batch.refresh_from_db()
                    
                    if batch.status == 'COMPLETED':
                        messages.success(request, f'Batch {batch.batch_reference} processed successfully! {batch.successful_vouchers} vouchers created.')
                    elif batch.status == 'FAILED':
                        messages.error(request, f'Batch {batch.batch_reference} processing failed: {batch.error_log or "Unknown error"}')
                    else:
                        messages.warning(request, f'Batch {batch.batch_reference} processing completed with status: {batch.status}')
                except Exception as e:
                    logger.error(f'Error processing batch synchronously: {str(e)}', traceback=traceback.format_exc())
                    messages.error(request, f'Failed to process batch: {str(e)}')
                    return redirect('voucher_batch_detail', batch_id=batch_id)
            
            return redirect('voucher_batch_processing', batch_id=batch_id)
            
        except Exception as e:
            logger.error(f'Error queueing batch processing: {str(e)}', traceback=traceback.format_exc())
            messages.error(request, f'Failed to queue batch processing: {str(e)}')
            return redirect('voucher_batch_detail', batch_id=batch_id)


class VoucherBatchProcessingView(LoginRequiredMixin, DetailView):
    """Dedicated processing screen with real-time updates"""
    model = BulkVoucherIssuanceBatch
    template_name = 'portal/vouchers/batches/processing.html'
    context_object_name = 'batch'
    pk_url_kwarg = 'batch_id'
    
    def get_queryset(self):
        return super().get_queryset().select_related('brand', 'client', 'issued_by', 'created_by', 'processing_locked_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from portal.services.bulk_voucher_service import BulkVoucherService
        from portal.tasks.voucher_tasks import process_bulk_voucher_issuance_task
        from celery.result import AsyncResult
        from celery import current_app
        
        batch = self.get_object()
        bulk_service = BulkVoucherService()
        
        # AUTO-RETRY: If batch is PROCESSING but stuck (no progress for >30 seconds or failed task)
        if batch.status == 'PROCESSING' and batch.processed_vouchers == 0:
            should_retry = False
            retry_reason = None
            
            # Check if task failed
            if batch.celery_task_id:
                try:
                    task_result = AsyncResult(batch.celery_task_id, app=current_app)
                    if task_result.state == 'FAILURE':
                        should_retry = True
                        retry_reason = 'Task failed'
                except Exception:
                    pass
            
            # Check if no progress for >30 seconds
            if batch.started_at:
                elapsed = (timezone.now() - batch.started_at).total_seconds()
                if elapsed > 30 and batch.processed_vouchers == 0:
                    should_retry = True
                    retry_reason = 'No progress for 30+ seconds'
            
            # Auto-retry if needed
            if should_retry:
                logger.warning(f'Auto-retrying batch {batch.id}: {retry_reason}')
                try:
                    # Reset batch
                    batch.status = 'PENDING'
                    batch.started_at = None
                    batch.celery_task_id = None
                    batch.processing_locked_at = None
                    batch.processing_locked_by = None
                    batch.metadata = {}
                    batch.save()
                    
                    # Process synchronously (more reliable)
                    process_bulk_voucher_issuance_task(batch.id)
                    batch.refresh_from_db()
                    logger.info(f'Auto-retry completed for batch {batch.id}: {batch.status}')
                except Exception as e:
                    logger.error(f'Auto-retry failed for batch {batch.id}: {str(e)}', traceback=traceback.format_exc())
        
        # Get denomination breakdown
        breakdown = bulk_service.generate_denomination_breakdown(batch)
        context['denomination_breakdown'] = breakdown
        
        # Get recent vouchers (last 20)
        vouchers = GiftVoucher.objects.filter(
            metadata__batch_id=batch.id
        ).select_related('brand', 'client', 'issued_by').order_by('-issued_at')[:20]
        context['recent_vouchers'] = vouchers
        
        # Calculate progress
        progress_percent = 0
        if batch.total_vouchers > 0:
            progress_percent = int((batch.processed_vouchers / batch.total_vouchers) * 100)
        context['progress_percent'] = progress_percent
        
        # Calculate elapsed time
        elapsed_time = None
        if batch.started_at:
            elapsed = timezone.now() - batch.started_at
            hours, remainder = divmod(elapsed.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                elapsed_time = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            elif minutes > 0:
                elapsed_time = f"{int(minutes)}m {int(seconds)}s"
            else:
                elapsed_time = f"{int(seconds)}s"
        context['elapsed_time'] = elapsed_time
        
        context['from_voucherx'] = self.request.GET.get('from') == 'voucherx'
        context['is_complete'] = batch.status in ['COMPLETED', 'FAILED']
        
        return context


class VoucherBatchProcessingStatusView(LoginRequiredMixin, View):
    """API endpoint for polling processing status"""
    
    def get(self, request, batch_id):
        from django.http import JsonResponse
        from portal.tasks.voucher_tasks import process_bulk_voucher_issuance_task
        from celery.result import AsyncResult
        from celery import current_app
        
        batch = get_object_or_404(BulkVoucherIssuanceBatch, id=batch_id)
        
        # AUTO-RETRY: If batch is PROCESSING but stuck (no progress for >30 seconds or failed task)
        if batch.status == 'PROCESSING' and batch.processed_vouchers == 0:
            should_retry = False
            retry_reason = None
            
            # Check if task failed
            if batch.celery_task_id:
                try:
                    task_result = AsyncResult(batch.celery_task_id, app=current_app)
                    if task_result.state == 'FAILURE':
                        should_retry = True
                        retry_reason = 'Task failed'
                except Exception:
                    pass
            
            # Check if no progress for >30 seconds
            if batch.started_at:
                elapsed = (timezone.now() - batch.started_at).total_seconds()
                if elapsed > 30 and batch.processed_vouchers == 0:
                    should_retry = True
                    retry_reason = 'No progress for 30+ seconds'
            
            # Auto-retry if needed
            if should_retry:
                logger.warning(f'Auto-retrying batch {batch.id} via status API: {retry_reason}')
                try:
                    # Reset batch
                    batch.status = 'PENDING'
                    batch.started_at = None
                    batch.celery_task_id = None
                    batch.processing_locked_at = None
                    batch.processing_locked_by = None
                    batch.metadata = {}
                    batch.save()
                    
                    # Process synchronously (more reliable)
                    process_bulk_voucher_issuance_task(batch.id)
                    batch.refresh_from_db()
                    logger.info(f'Auto-retry completed for batch {batch.id}: {batch.status}')
                except Exception as e:
                    logger.error(f'Auto-retry failed for batch {batch.id}: {str(e)}', traceback=traceback.format_exc())
        
        # Get recent vouchers (last 20)
        vouchers = GiftVoucher.objects.filter(
            metadata__batch_id=batch.id
        ).select_related('brand', 'client', 'issued_by').order_by('-issued_at')[:20]
        
        voucher_list = []
        for voucher in vouchers:
            voucher_list.append({
                'id': voucher.id,
                'voucher_code': f"{voucher.voucher_code[:4]}-{voucher.voucher_code[4:8]}-****-****",
                'reference_number': voucher.reference_number,
                'amount': str(voucher.original_amount),
                'status': voucher.status,
                'issued_at': voucher.issued_at.isoformat() if voucher.issued_at else None,
            })
        
        # Calculate progress
        progress_percent = 0
        if batch.total_vouchers > 0:
            progress_percent = int((batch.processed_vouchers / batch.total_vouchers) * 100)
        
        # Calculate elapsed time
        elapsed_time = None
        if batch.started_at:
            elapsed = timezone.now() - batch.started_at
            hours, remainder = divmod(elapsed.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                elapsed_time = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            elif minutes > 0:
                elapsed_time = f"{int(minutes)}m {int(seconds)}s"
            else:
                elapsed_time = f"{int(seconds)}s"
        
        # Get voucher progress from metadata
        voucher_progress = {}
        current_index = 0
        if batch.metadata:
            voucher_progress = batch.metadata.get('voucher_progress', {})
            current_index = batch.metadata.get('current_voucher_index', 0)
        
        # Build progress list for all vouchers
        progress_list = []
        for i in range(1, batch.total_vouchers + 1):
            progress = voucher_progress.get(str(i), {'status': 'pending'})
            progress_list.append({
                'index': i,
                'status': progress.get('status', 'pending'),  # pending, processing, completed, failed
                'voucher_code': progress.get('voucher_code'),
                'voucher_id': progress.get('voucher_id'),
                'error': progress.get('error'),
                'processed_at': progress.get('processed_at')
            })
        
        # Mark current processing voucher - always show what's being processed
        # Check if current_index is set and within valid range
        if current_index > 0 and current_index <= batch.total_vouchers:
            current_progress = voucher_progress.get(str(current_index), {})
            current_status = current_progress.get('status', 'pending')
            # If not completed/failed, mark as processing
            if current_status not in ['completed', 'failed']:
                progress_list[current_index - 1]['status'] = 'processing'
            # Also mark next pending voucher if current is completed (shows we're moving forward)
            elif current_index < batch.total_vouchers:
                next_index = current_index + 1
                next_progress = voucher_progress.get(str(next_index), {})
                if next_progress.get('status') == 'pending':
                    progress_list[next_index - 1]['status'] = 'processing'
        
        # Calculate estimated time remaining
        estimated_time_remaining = None
        if batch.started_at and batch.processed_vouchers > 0 and batch.status == 'PROCESSING':
            elapsed_seconds = (timezone.now() - batch.started_at).total_seconds()
            avg_time_per_voucher = elapsed_seconds / batch.processed_vouchers
            remaining_vouchers = batch.total_vouchers - batch.processed_vouchers
            if remaining_vouchers > 0:
                estimated_seconds = avg_time_per_voucher * remaining_vouchers
                # Format as "Xh Ym" or "Xm Ys" or "Xs"
                hours, remainder = divmod(estimated_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                if hours > 0:
                    estimated_time_remaining = f"{int(hours)}h {int(minutes)}m"
                elif minutes > 0:
                    estimated_time_remaining = f"{int(minutes)}m {int(seconds)}s"
                else:
                    estimated_time_remaining = f"{int(seconds)}s"
        
        return JsonResponse({
            'status': batch.status,
            'status_display': batch.get_status_display(),
            'total_vouchers': batch.total_vouchers,
            'processed_vouchers': batch.processed_vouchers,
            'successful_vouchers': batch.successful_vouchers,
            'failed_vouchers': batch.failed_vouchers,
            'progress_percent': progress_percent,
            'elapsed_time': elapsed_time,
            'estimated_time_remaining': estimated_time_remaining,
            'recent_vouchers': voucher_list,
            'voucher_progress': progress_list,
            'current_processing_index': current_index,
            'is_complete': batch.status in ['COMPLETED', 'FAILED'],
            'started_at': batch.started_at.isoformat() if batch.started_at else None,
            'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
        })


class VoucherBatchExportView(LoginRequiredMixin, View):
    """Export batch to CSV/Excel"""
    
    def get(self, request, batch_id):
        from portal.services.voucher_export_service import VoucherExportService
        
        format_type = request.GET.get('format', 'csv')
        export_service = VoucherExportService()
        
        try:
            if format_type == 'excel':
                return export_service.export_batch_to_excel(batch_id)
            else:
                return export_service.export_batch_to_csv(batch_id)
        except Exception as e:
            logger.error(
                f'Error exporting batch: {str(e)}',
                traceback=traceback.format_exc()
            )
            messages.error(request, f'Error exporting batch: {str(e)}')
            return redirect('voucher_batch_detail', batch_id=batch_id)


# Reseller/Partner UI removed — ParkPe & Payswap managed via Project Management (dashboard/projects/).


