"""
Custom Django Allauth Adapter
Handles social signup with role=customer and profile_completion_required=True
"""
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.http import HttpResponseRedirect
from django.contrib.auth import login
from portal.models import User, Profile, Role
from portal.utils.user_utils import generate_username, get_role_prefix
from portal.utils.ip_utils import get_client_ip, get_user_agent, get_session_id
from portal.tasks.write_logs_task import write_logs_task
from portal.utils.logging_utils import get_request_id, generate_response_id
import uuid


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for social authentication
    - Assigns role=customer for social signups (mandatory)
    - Sets profile_completion_required=True
    - Creates minimal profile with social provider info
    """
    
    def pre_social_login(self, request, sociallogin):
        """Called before social login/signup"""
        # Extract context for logging
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        request_id = get_request_id(request) or str(uuid.uuid4())
        response_id = generate_response_id()
        
        # Log social auth attempt
        write_logs_task.delay(
            log_level='INFO',
            message=f'Social authentication attempt: {sociallogin.account.provider}',
            module_name='portal.adapters.CustomSocialAccountAdapter',
            url=request.path,
            request_id=request_id,
            response_id=response_id,
            user_id=None,
            extra_data={
                'action': 'social_auth_pre_login',
                'provider': sociallogin.account.provider
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
    
    def save_user(self, request, sociallogin, form=None):
        """
        Save user from social account
        Creates user with role=customer and profile_completion_required=True
        """
        user = sociallogin.user
        
        # Get customer role (mandatory for social signup)
        try:
            role = Role.objects.get(code='customer')
        except Role.DoesNotExist:
            from django.core.exceptions import ValidationError
            raise ValidationError('Customer role does not exist. Please run "python manage.py setup_roles".')
        
        # Set role to customer (MANDATORY)
        user.role_code = 'customer'
        user.role = role
        
        # Generate username if not set
        if not user.username:
            username = generate_username(get_role_prefix('customer'))
            user.username = username
        
        # Set email_verified to True (social providers verify email)
        user.email_verified = True
        
        # Save user
        user.save()
        
        # Create profile with minimal data from social provider
        social_account = sociallogin.account
        extra_data = social_account.extra_data
        
        # Extract data from social provider
        email = extra_data.get('email') or user.email or ''
        first_name = (
            extra_data.get('given_name') or 
            extra_data.get('first_name') or 
            (extra_data.get('name', '').split()[0] if extra_data.get('name') else '') or
            'User'
        )
        
        # Create profile with profile_completion_required=True
        profile = Profile.objects.create(
            user=user,
            email=email,
            first_name=first_name,
            profile_completion_required=True,  # MANDATORY - user must complete profile
            social_provider=social_account.provider,
            social_provider_id=social_account.uid,
            email_verified=True,  # Social providers verify email
            phone_verified=False  # Phone not provided yet
        )
        
        # Extract context for logging
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        request_id = get_request_id(request) or str(uuid.uuid4())
        response_id = generate_response_id()
        
        # Log social signup
        write_logs_task.delay(
            log_level='INFO',
            message=f'Social signup completed: user {user.username} via {social_account.provider}',
            module_name='portal.adapters.CustomSocialAccountAdapter',
            url=request.path,
            request_id=request_id,
            response_id=response_id,
            user_id=user.id,
            extra_data={
                'action': 'social_signup',
                'provider': social_account.provider,
                'profile_id': profile.id,
                'role': 'customer'
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        
        return user
    
    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Allow auto signup for social accounts
        We handle user creation in save_user()
        """
        return True
    
    def get_connect_redirect_url(self, request, socialaccount):
        """
        Redirect after connecting social account
        """
        # Check if profile completion is required
        if hasattr(request.user, 'profile') and request.user.profile.profile_completion_required:
            return '/profile/complete/'
        return '/dashboard/'
