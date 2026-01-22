"""
User utility functions
"""
import random
import string
from typing import Optional
from django.contrib.auth import get_user_model


def generate_username(role_prefix: str) -> str:
    """
    Generate unique username in format: [Role Prefix]00[6 random digits]
    
    Args:
        role_prefix: Single character role prefix (A, E, S, D, R, C, V)
    
    Returns:
        Unique username string
    """
    User = get_user_model()
    max_attempts = 100
    
    for _ in range(max_attempts):
        # Generate 6 random digits
        random_digits = ''.join(random.choices(string.digits, k=6))
        username = f"{role_prefix}00{random_digits}"
        
        # Check uniqueness
        if not User.objects.filter(username=username).exists():
            return username
    
    raise ValueError(f"Failed to generate unique username after {max_attempts} attempts")


def get_role_prefix(role_code: str) -> str:
    """
    Get role prefix for username generation
    
    Args:
        role_code: Role code (admin, employee, super, distributor, retailer, customer, vendor)
    
    Returns:
        Single character prefix
    """
    role_mapping = {
        'admin': 'A',
        'employee': 'E',
        'super': 'S',
        'distributor': 'D',
        'retailer': 'R',
        'customer': 'C',
        'vendor': 'V',
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
    mfa_required_roles = ['admin', 'employee', 'super', 'distributor']
    return role_code.lower() in mfa_required_roles
