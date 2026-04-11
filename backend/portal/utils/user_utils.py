"""
User utility functions
"""
import secrets
import string
from typing import Optional
from django.contrib.auth import get_user_model


def generate_username(role_prefix: str) -> str:
    """
    Generate cryptographically secure unique username in format: [Role Prefix]00[8 random alphanumeric]
    
    Uses secrets module for cryptographically secure random generation.
    
    Args:
        role_prefix: Single character role prefix (A, E, S, D, R, C, V)
    
    Returns:
        Unique username string
    """
    User = get_user_model()
    max_attempts = 100
    
    for _ in range(max_attempts):
        # Generate 8 cryptographically secure random alphanumeric characters
        # Using secrets.choice for cryptographically secure randomness
        random_chars = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        username = f"{role_prefix}00{random_chars}"
        
        # Check uniqueness
        if not User.objects.filter(username=username).exists():
            return username
    
    raise ValueError(f"Failed to generate unique username after {max_attempts} attempts")


def get_role_prefix(role_code: str) -> str:
    """
    Get role prefix for username generation
    
    Args:
        role_code: Role code (super_admin, admin, employee, super_distributor, distributor, retailer, customer)
    
    Returns:
        Single character prefix
    """
    role_mapping = {
        'super_admin': 'X',
        'admin': 'A',
        'employee': 'E',
        'super_distributor': 'S',
        'distributor': 'D',
        'retailer': 'R',
        'customer': 'C',
    }
    return role_mapping.get(role_code.lower(), 'U')  # Default to 'U' for unknown


def is_mfa_required_role(role_code: str) -> bool:
    """
    Check if role requires MFA enforcement
    
    Args:
        role_code: Role code
    
    Returns:
        True if MFA is required
    """
    mfa_required_roles = ['super_admin', 'admin', 'employee', 'super_distributor', 'distributor']
    return role_code.lower() in mfa_required_roles
