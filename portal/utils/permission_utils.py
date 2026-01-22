"""
Permission checking utilities
"""
from typing import List
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType


def user_has_permission(user: User, permission_codename: str, app_label: str = 'portal') -> bool:
    """
    Check if user has specific permission
    
    Args:
        user: User instance
        permission_codename: Permission codename
        app_label: App label (default: 'portal')
    
    Returns:
        True if user has permission
    """
    return user.has_perm(f"{app_label}.{permission_codename}")


def user_has_any_permission(user: User, permission_codenames: List[str], app_label: str = 'portal') -> bool:
    """
    Check if user has any of the specified permissions
    
    Args:
        user: User instance
        permission_codenames: List of permission codenames
        app_label: App label (default: 'portal')
    
    Returns:
        True if user has at least one permission
    """
    for codename in permission_codenames:
        if user_has_permission(user, codename, app_label):
            return True
    return False


def user_has_all_permissions(user: User, permission_codenames: List[str], app_label: str = 'portal') -> bool:
    """
    Check if user has all specified permissions
    
    Args:
        user: User instance
        permission_codenames: List of permission codenames
        app_label: App label (default: 'portal')
    
    Returns:
        True if user has all permissions
    """
    for codename in permission_codenames:
        if not user_has_permission(user, codename, app_label):
            return False
    return True


def get_user_role(user: User) -> str:
    """
    Get user's role code
    
    Args:
        user: User instance
    
    Returns:
        Role code string
    """
    if hasattr(user, 'role'):
        return user.role.code if hasattr(user.role, 'code') else str(user.role)
    return 'unknown'
