"""
Custom middleware for portal app
"""
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import logout
from portal.utils.user_utils import is_mfa_required_role


class MFARequiredMiddleware:
    """
    Middleware to enforce MFA setup for specific roles
    Enforced roles: Admin, Employee, Super, Distributor
    """
    
    # Paths that don't require MFA check
    EXCLUDED_PATHS = [
        '/signin/',
        '/signup/',
        '/mfa/setup/',
        '/mfa/verify/',
        '/logout/',
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
