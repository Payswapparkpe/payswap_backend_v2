"""
Request Utility Functions
Helpers for extracting information from Django requests
"""
from typing import Optional


def get_client_ip(request) -> Optional[str]:
    """
    Get client IP address from request
    
    Args:
        request: Django request object
        
    Returns:
        Client IP address as string, or None if not available
    """
    if not request:
        return None
    
    # Check X-Forwarded-For header first (for proxied requests)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = x_forwarded_for.split(',')[0].strip()
        return ip
    
    # Fallback to REMOTE_ADDR
    ip = request.META.get('REMOTE_ADDR')
    return ip


def get_request_info(request) -> dict:
    """
    Extract comprehensive request information
    
    Args:
        request: Django request object
        
    Returns:
        Dictionary with request information
    """
    if not request:
        return {}
    
    return {
        'client_ip': get_client_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'method': request.method,
        'path': request.path if hasattr(request, 'path') else None,
        'referer': request.META.get('HTTP_REFERER', ''),
        'host': request.get_host() if hasattr(request, 'get_host') else None,
    }
