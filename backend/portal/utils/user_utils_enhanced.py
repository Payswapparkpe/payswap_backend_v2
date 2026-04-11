"""
Enhanced User Utility Functions
Additional helpers for user-related operations
"""
from typing import Optional, Any


def get_user_id(user: Any) -> Optional[int]:
    """
    Safely extract user ID from user object
    
    Args:
        user: User object or None
        
    Returns:
        User ID as integer, or None if not available
    """
    if not user:
        return None
    
    if hasattr(user, 'id'):
        return user.id
    
    return None


def get_issuer_name(user: Any) -> str:
    """
    Extract issuer name from user object
    
    Args:
        user: User object or None
        
    Returns:
        Issuer name as string
    """
    if not user:
        return "Unknown"
    
    # Try username first
    if hasattr(user, 'username') and user.username:
        return user.username
    
    # Try getting name from profile
    if hasattr(user, 'profile'):
        profile = user.profile
        if hasattr(profile, 'first_name') and hasattr(profile, 'last_name'):
            full_name = f"{profile.first_name} {profile.last_name}".strip()
            if full_name:
                return full_name
        if hasattr(profile, 'first_name') and profile.first_name:
            return profile.first_name
    
    # Fallback to string representation
    return str(user)


def get_user_display_name(user: Any) -> str:
    """
    Get user's display name with fallback
    
    Args:
        user: User object or None
        
    Returns:
        Display name as string
    """
    if not user:
        return "Unknown User"
    
    # Try profile name first
    if hasattr(user, 'profile'):
        profile = user.profile
        if hasattr(profile, 'first_name') and hasattr(profile, 'last_name'):
            full_name = f"{profile.first_name} {profile.last_name}".strip()
            if full_name:
                return full_name
    
    # Fallback to username
    if hasattr(user, 'username') and user.username:
        return user.username
    
    # Fallback to email
    if hasattr(user, 'email') and user.email:
        return user.email
    
    return "Unknown User"


def is_user_admin(user: Any) -> bool:
    """
    Check if user is an admin
    
    Args:
        user: User object or None
        
    Returns:
        True if user is admin, False otherwise
    """
    if not user:
        return False
    
    # Check role_code
    if hasattr(user, 'role_code') and user.role_code == 'ADMIN':
        return True
    
    # Check is_staff
    if hasattr(user, 'is_staff') and user.is_staff:
        return True
    
    # Check is_superuser
    if hasattr(user, 'is_superuser') and user.is_superuser:
        return True
    
    return False
