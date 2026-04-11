"""
Logging utility functions
Helpers for extracting request context, module names, request/response IDs
"""
import inspect
import uuid
from typing import Optional, Dict, Any
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


def categorize_log(
    module_name: Optional[str] = None, 
    url: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Determine log category based on module name, URL, and extra_data
    
    Args:
        module_name: Module name (e.g., 'portal.views', 'api.v1.views')
        url: URL path (e.g., '/api/v1/auth/login')
        extra_data: Additional data dictionary that may contain operation information
    
    Returns:
        Log category string: 'api', 'auth', 'payment', 'notification', 'security', 'gift_voucher', 'general'
    """
    # Check extra_data for API Explorer source (requests from /api-explorer/ UI)
    if extra_data and extra_data.get('source') == 'api_explorer':
        return 'api_explorer'

    # Check extra_data first for operation field (highest priority for voucher detection)
    if extra_data and extra_data.get('operation'):
        operation = str(extra_data.get('operation', '')).lower()
        # Check if operation indicates voucher activity
        if any(x in operation for x in [
            'voucher', 'batch', 'client', 'brand', 'onboarding', 
            'issuance', 'redemption', 'export', 'pin', 'otp'
        ]):
            return 'gift_voucher'
    
    # Check URL second
    if url:
        # Check for voucher-related URLs (before other checks)
        if any(x in url.lower() for x in ['/voucher', '/voucherx', '/batch', '/brand', '/client']):
            return 'gift_voucher'
        # ParkPe Connect – vehicle CRUD, RC fetch, delete OTP, QR
        if '/connect/' in url.lower() or (extra_data and extra_data.get('category') == 'connect_vehicle'):
            return 'connect_vehicle'
        # Mobikwik BBPS (portal test UI and API v2)
        if 'bbps' in url.lower() or 'mobikwik' in url.lower():
            return 'mobikwik_bbps'
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
    
    # Check module name third
    if module_name:
        # Check for voucher-related modules (before other checks)
        if any(x in module_name.lower() for x in ['voucher', 'voucherx', 'bulk_voucher', 'voucher_client', 'voucher_export', 'brand_onboarding']):
            return 'gift_voucher'
        if 'connect.vehicle' in module_name.lower() or 'api.connect' in module_name.lower():
            return 'connect_vehicle'
        if any(x in module_name.lower() for x in ['mobikwik', 'bbps_service', 'bbps_views']):
            return 'mobikwik_bbps'
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
