"""
API Version 1 Permissions - Internal Access Only
"""
from rest_framework import permissions


class IsInternalUser(permissions.BasePermission):
    """
    Permission class for internal API access.
    Allows access to:
    - Staff users
    - Authenticated users (can be customized)
    """
    
    def has_permission(self, request, view):
        # Staff users always have access
        if request.user and request.user.is_staff:
            return True
        
        # Authenticated users have access (customize as needed)
        if request.user and request.user.is_authenticated:
            return True
        
        return False


class IsStaffOnly(permissions.BasePermission):
    """
    Strict internal access - Staff only
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_staff
