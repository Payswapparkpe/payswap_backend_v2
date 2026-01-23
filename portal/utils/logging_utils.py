"""
Logging utility functions
Helpers for extracting request context, module names, request/response IDs
"""
import inspect
import uuid
from typing import Optional
from django.http import HttpRequest


def get_module_name(skip_frames: int = 2) -> str:
    """
    Get the module name of the calling function
    
    Args:
        skip_frames: Number of stack frames to skip (default: 2 to skip this function and caller)
    
    Returns:
        Module name string (e.g., 'portal.views', 'api.v1.views')
    """
    try:
        frame = inspect.currentframe()
        for _ in range(skip_frames):
            frame = frame.f_back
        module = inspect.getmodule(frame)
        if module:
            return module.__name__
    except (AttributeError, TypeError):
        pass
    return 'unknown'


def get_request_id(request: Optional[HttpRequest] = None) -> Optional[str]:
    """
    Extract or generate request ID
    
    Args:
        request: Django request object
    
    Returns:
        Request ID string or None
    """
    if request:
        # Check X-Request-ID header
        request_id = request.META.get('HTTP_X_REQUEST_ID')
        if request_id:
            return request_id
        
        # Check if already in request object
        if hasattr(request, 'request_id'):
            return request.request_id
        
        # Generate new request ID
        request_id = str(uuid.uuid4())
        request.request_id = request_id
        return request_id
    
    return None


def generate_response_id() -> str:
    """
    Generate response ID (UUID)
    
    Returns:
        Response ID string
    """
    return str(uuid.uuid4())


def categorize_log(module_name: Optional[str] = None, url: Optional[str] = None) -> str:
    """
    Determine log category based on module name and URL
    
    Args:
        module_name: Module name (e.g., 'portal.views', 'api.v1.views')
        url: URL path (e.g., '/api/v1/auth/login')
    
    Returns:
        Log category string: 'api', 'auth', 'payment', 'notification', 'security', 'general'
    """
    # Check URL first
    if url:
        if '/api/' in url:
            return 'api'
        if any(x in url for x in ['/login', '/signup', '/signin', '/auth', '/mfa', '/password']):
            return 'auth'
        if any(x in url for x in ['/payment', '/wallet', '/transaction']):
            return 'payment'
        if any(x in url for x in ['/notification', '/sms', '/email', '/otp']):
            return 'notification'
        if any(x in url for x in ['/security', '/lockout', '/failed']):
            return 'security'
    
    # Check module name
    if module_name:
        if 'api' in module_name.lower():
            return 'api'
        if any(x in module_name.lower() for x in ['auth', 'login', 'signup', 'mfa']):
            return 'auth'
        if any(x in module_name.lower() for x in ['payment', 'wallet', 'transaction']):
            return 'payment'
        if any(x in module_name.lower() for x in ['notification', 'sms', 'email', 'otp']):
            return 'notification'
        if any(x in module_name.lower() for x in ['security', 'lockout']):
            return 'security'
    
    return 'general'
