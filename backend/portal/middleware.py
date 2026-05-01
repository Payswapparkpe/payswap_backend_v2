"""
Custom middleware for portal app
"""
import time
import traceback
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import logout
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse
from portal.utils.user_utils import is_mfa_required_role
from portal.utils.logging_utils import get_request_id, generate_response_id
from portal.utils.ip_utils import get_client_ip, get_user_agent, get_session_id
from portal.tasks.write_logs_task import write_logs_task

FLEET_PORTAL_ROLE_CODES = {
    "fleet_admin", "fleet_manager", "fleet_operator", "fleet_dispatcher",
    "parking_owner", "parking_manager", "parking_attendant",
    "super_distributor", "distributor", "retailer", "customer",
}


class FleetPortalBlockMiddleware:
    """
    Prevent fleet-only accounts from accessing Django portal session flows.
    Fleet users must authenticate through ParkPe app (JWT flow), not portal UI.
    """

    EXCLUDED_PATHS = [
        '/signin/',
        '/signout/',
        '/logout/',
        '/admin/',
        '/static/',
        '/media/',
        '/api/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return self.get_response(request)

        if request.user.is_authenticated:
            role_code = getattr(request.user, "role_code", "")
            if role_code in FLEET_PORTAL_ROLE_CODES:
                logout(request)
                # Message middleware may not be initialized yet in some test flows.
                if hasattr(request, "_messages"):
                    from django.contrib import messages
                    messages.error(request, "Fleet accounts must use the ParkPe app.")
                return redirect('/signin/')

        return self.get_response(request)


class ProfileCompletionMiddleware:
    """
    Middleware to enforce profile completion for social signup users
    Blocks dashboard access until profile is completed
    """
    
    # Paths that don't require profile completion check
    EXCLUDED_PATHS = [
        '/profile/complete/',
        '/logout/',
        '/signin/',
        '/signup/',
        '/mfa/setup/',
        '/mfa/verify/',
        '/auth/set-pin/',
        '/auth/unlock-with-pin/',
        '/admin/',
        '/static/',
        '/media/',
        '/api/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if path is excluded
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return self.get_response(request)
        
        # Check if user is authenticated
        if request.user.is_authenticated:
            user = request.user
            
            # Check if profile completion is required
            if hasattr(user, 'profile') and user.profile:
                if user.profile.profile_completion_required:
                    # Redirect to profile completion page
                    if request.path != '/profile/complete/':
                        return redirect('/profile/complete/')
        
        return self.get_response(request)


class MFARequiredMiddleware:
    """
    Middleware to enforce MFA setup for specific roles
    Enforced roles: Admin, Employee, Super, Distributor
    Optional roles: Customer, Retailer, Vendor (show prompt but don't block)
    """
    
    # Paths that don't require MFA check
    EXCLUDED_PATHS = [
        '/signin/',
        '/signup/',
        '/mfa/setup/',
        '/mfa/verify/',
        '/auth/set-pin/',
        '/auth/unlock-with-pin/',
        '/logout/',
        '/profile/complete/',
        '/admin/',
        '/static/',
        '/media/',
        '/api/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if path is excluded
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return self.get_response(request)
        
        # Check if user is authenticated
        if request.user.is_authenticated:
            user = request.user
            
            # Check if user's role requires MFA
            if hasattr(user, 'role_code') and is_mfa_required_role(user.role_code):
                # Check if MFA is configured
                if not user.mfa_configured:
                    # Redirect to MFA setup page
                    if request.path != '/mfa/setup/':
                        return redirect('/mfa/setup/')
        
        response = self.get_response(request)
        return response


class SessionLockMiddleware:
    """
    After session expiry (user anonymous), redirect to PIN unlock when applicable.
    User identity comes from signed lock_identity cookie; PIN unlock is offered only
    if user has PIN set, is not locked, and last_full_auth_at is within window.
    OTP/2FA is primary auth; PIN is secondary re-unlock only.
    """
    EXCLUDED_PATHS = [
        '/',
        '/signin/',
        '/signup/',
        '/mfa/setup/',
        '/mfa/verify/',
        '/auth/set-pin/',
        '/auth/unlock-with-pin/',
        '/logout/',
        '/profile/complete/',
        '/admin/',
        '/static/',
        '/media/',
        '/api/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(p) for p in self.EXCLUDED_PATHS):
            return self.get_response(request)
        if request.user.is_authenticated:
            return self.get_response(request)
        from portal.utils.session_lock import get_user_from_lock_cookie, can_offer_pin_unlock
        user = get_user_from_lock_cookie(request)
        if user and can_offer_pin_unlock(user):
            from urllib.parse import quote
            next_path = request.get_full_path()
            return redirect(f'/auth/unlock-with-pin/?next={quote(next_path)}')
        return self.get_response(request)


class RequestLoggingMiddleware:
    """
    Middleware to log all HTTP requests and responses
    Captures request details, response status, timing, and errors
    """
    
    # Paths to exclude from logging (static files, health checks, etc.)
    EXCLUDED_PATHS = [
        '/static/',
        '/media/',
        '/favicon.ico',
        '/robots.txt',
        '/.well-known/',
        '/health/',
        '/ping/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Main middleware entry point"""
        # Process request (store timing info)
        self.process_request(request)
        
        # Get response
        response = self.get_response(request)
        
        # Process response (log the request)
        response = self.process_response(request, response)
        
        return response
    
    def process_request(self, request: HttpRequest):
        """Store request start time and generate IDs"""
        # Skip excluded paths
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return None
        
        # Store request metadata
        request._log_start_time = time.time()
        request._request_id = get_request_id(request)
        request._response_id = generate_response_id()
        
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse):
        """Log the request and response with bodies"""
        # Skip excluded paths
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return response
        
        # Calculate response time
        response_time = None
        if hasattr(request, '_log_start_time'):
            response_time = time.time() - request._log_start_time
        
        # Get request metadata
        request_id = getattr(request, '_request_id', None) or get_request_id(request)
        response_id = getattr(request, '_response_id', None) or generate_response_id()
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        
        # Determine log level based on response status
        if response.status_code >= 500:
            log_level = 'ERROR'
        elif response.status_code >= 400:
            log_level = 'WARNING'
        else:
            log_level = 'INFO'
        
        # Get user ID if authenticated
        user_id = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = request.user.id
        
        # Extract request body (for POST/PUT/PATCH/DELETE)
        request_body = None
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            try:
                from portal.services.unified_logging_service import UnifiedLoggingService
                unified_logger = UnifiedLoggingService()
                request_body = unified_logger._extract_request_body(request)
            except Exception as e:
                request_body = f'[Error extracting request body: {str(e)}]'
        
        # Extract response body
        response_body = None
        try:
            from portal.services.unified_logging_service import UnifiedLoggingService
            unified_logger = UnifiedLoggingService()
            response_body = unified_logger._extract_response_body(response)
        except Exception as e:
            response_body = f'[Error extracting response body: {str(e)}]'
        
        # Build extra data
        extra_data = {
            'method': request.method,
            'status_code': response.status_code,
            'response_time_seconds': round(response_time, 3) if response_time else None,
            'content_length': len(response.content) if hasattr(response, 'content') else None,
        }
        # Tag requests from API Explorer UI for dedicated log category
        if (request.META.get('HTTP_X_API_EXPLORER') == 'true' or
                (request.META.get('HTTP_REFERER') or '').find('api-explorer') != -1):
            extra_data['source'] = 'api_explorer'
        
        # Add request body if captured
        if request_body:
            extra_data['request_body'] = request_body
        
        # Add response body if captured
        if response_body:
            extra_data['response_body'] = response_body
        
        # Add query parameters (sanitized)
        if request.GET:
            extra_data['query_params'] = dict(request.GET)
        
        # Build log message
        message = f"{request.method} {request.path} - {response.status_code}"
        if response_time:
            message += f" ({response_time:.3f}s)"
        
        # Log the request (sync for API Explorer so logs appear without Celery)
        log_kwargs = dict(
            log_level=log_level,
            message=message,
            module_name='portal.middleware.request_logging',
            url=request.path,
            request_id=request_id,
            response_id=response_id,
            user_id=user_id,
            extra_data=extra_data,
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id,
        )
        if extra_data.get('source') == 'api_explorer':
            write_logs_task.apply(kwargs=log_kwargs)
        else:
            write_logs_task.delay(**log_kwargs)

        return response
    
    def process_exception(self, request: HttpRequest, exception: Exception):
        """Log exceptions"""
        # Skip excluded paths
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return None
        
        # Get request metadata
        request_id = getattr(request, '_request_id', None) or get_request_id(request)
        response_id = getattr(request, '_response_id', None) or generate_response_id()
        client_ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        session_id = get_session_id(request)
        
        # Get user ID if authenticated
        user_id = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = request.user.id
        
        # Get traceback
        tb_str = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        
        # Build extra data
        extra_data = {
            'method': request.method,
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'traceback': tb_str,
        }
        
        # Log the exception
        write_logs_task.delay(
            log_level='ERROR',
            message=f"Exception in {request.method} {request.path}: {type(exception).__name__} - {str(exception)}",
            module_name='portal.middleware.request_logging',
            url=request.path,
            request_id=request_id,
            response_id=response_id,
            user_id=user_id,
            extra_data=extra_data,
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        
        return None  # Let Django handle the exception normally
