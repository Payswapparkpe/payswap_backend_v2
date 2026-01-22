"""
API Version 2 Permissions - External Parties
"""
from rest_framework import permissions


class IsExternalUser(permissions.BasePermission):
    """
    Permission class for external API access.
    Allows access to:
    - Public endpoints (no auth required)
    - API key authenticated users
    - Token authenticated users (for partners)
    """
    
    def has_permission(self, request, view):
        # Public access by default
        # Override in views that require authentication
        return True


class HasAPIKey(permissions.BasePermission):
    """
    Permission for API key authentication (for external partners)
    Customize based on your API key implementation
    """
    
    def has_permission(self, request, view):
        # Check for API key in headers
        api_key = request.META.get('HTTP_X_API_KEY') or request.META.get('HTTP_AUTHORIZATION')
        
        if not api_key:
            return False
        
        # Add your API key validation logic here
        # Example: Check against database or environment variable
        # from core.config import payswap_config
        # return api_key == payswap_config.get_external_api_key()
        
        return True  # Placeholder - implement your validation
