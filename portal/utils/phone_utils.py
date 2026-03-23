"""
Phone Number Utility Functions
Helpers for phone number normalization and validation
"""
from typing import Tuple, Optional

# Re-export normalize_phone_number from validators for backward compatibility
from portal.utils.validators import normalize_phone_number


def phone_lookup_candidates(normalized_phone: str) -> list:
    """
    Return list of phone strings to try when looking up Profile.
    DB may store 10-digit, 91..., or +91... so we try all variants.
    """
    candidates = [normalized_phone]
    if normalized_phone.startswith("+91"):
        candidates.append(normalized_phone[1:])  # 91XXXXXXXXXX
        if len(normalized_phone) == 13:  # +91 + 10 digits
            candidates.append(normalized_phone[3:])  # 10-digit only
    elif normalized_phone.startswith("91") and len(normalized_phone) == 12:
        candidates.append(normalized_phone[2:])  # 10-digit only
    return candidates


__all__ = [
    'normalize_phone_number',
    'safe_normalize_phone',
    'format_phone_display',
    'format_phone_for_kaleyra',
    'mask_phone_number',
    'phone_lookup_candidates',
    'is_valid_indian_mobile'
]


def format_phone_for_kaleyra(phone_number: str) -> str:
    """
    Format phone number for Kaleyra API (91XXXXXXXXXX format)
    
    Args:
        phone_number: Phone number string
        
    Returns:
        Phone number in 91XXXXXXXXXX format for Kaleyra
    """
    # Remove any non-digit characters
    digits = ''.join(filter(str.isdigit, phone_number))
    
    # If it starts with +91, remove the +
    if phone_number.startswith('+91'):
        digits = phone_number[1:]  # Remove +, keep 91XXXXXXXXXX
        digits = ''.join(filter(str.isdigit, digits))
    
    # If it's 10 digits, add 91 prefix
    if len(digits) == 10:
        return f"91{digits}"
    
    # If it already has 91 prefix (12 digits), return as-is
    if len(digits) == 12 and digits.startswith('91'):
        return digits
    
    # If it starts with 0, remove it and add 91
    if digits.startswith('0') and len(digits) == 11:
        return f"91{digits[1:]}"
    
    # Return as-is if already in correct format or unknown format
    return digits


def safe_normalize_phone(phone_number: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize phone number with safe error handling
    
    Args:
        phone_number: Phone number string to normalize
        
    Returns:
        Tuple of (normalized_phone, error_message)
        - If successful: (normalized_phone, None)
        - If failed: (None, error_message)
    """
    if not phone_number:
        return None, "Phone number is required"
    
    try:
        normalized = normalize_phone_number(phone_number)
        return normalized, None
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Invalid phone number: {str(e)}"


def format_phone_display(phone_number: str) -> str:
    """
    Format phone number for display
    
    Args:
        phone_number: Phone number string
        
    Returns:
        Formatted phone number string
    """
    if not phone_number:
        return ""
    
    # Remove any non-digit characters
    digits = ''.join(filter(str.isdigit, phone_number))
    
    # Format based on length
    if len(digits) == 10:
        # Format as (XXX) XXX-XXXX
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 12 and digits.startswith('91'):
        # Indian format with country code: +91 XXXXX XXXXX
        return f"+91 {digits[2:7]} {digits[7:]}"
    elif len(digits) > 10:
        # Generic format for international numbers
        return f"+{digits[:len(digits)-10]} {digits[-10:-5]} {digits[-5:]}"
    
    # Return as-is if format not recognized
    return phone_number


def mask_phone_number(phone_number: str, show_last_digits: int = 4) -> str:
    """
    Mask phone number for security
    
    Args:
        phone_number: Phone number string
        show_last_digits: Number of last digits to show
        
    Returns:
        Masked phone number string
    """
    if not phone_number:
        return ""
    
    # Remove any non-digit characters
    digits = ''.join(filter(str.isdigit, phone_number))
    
    if len(digits) <= show_last_digits:
        return phone_number
    
    # Mask all but last N digits
    masked_part = '*' * (len(digits) - show_last_digits)
    visible_part = digits[-show_last_digits:]
    
    # Add country code prefix if present
    if phone_number.startswith('+'):
        return f"+{masked_part}{visible_part}"
    
    return f"{masked_part}{visible_part}"


def is_valid_indian_mobile(phone_number: str) -> bool:
    """
    Check if phone number is a valid Indian mobile number
    
    Args:
        phone_number: Phone number string
        
    Returns:
        True if valid Indian mobile, False otherwise
    """
    if not phone_number:
        return False
    
    # Remove any non-digit characters
    digits = ''.join(filter(str.isdigit, phone_number))
    
    # Indian mobile numbers:
    # - 10 digits starting with 6-9
    # - Or 12 digits starting with 91 followed by 6-9
    if len(digits) == 10 and digits[0] in '6789':
        return True
    elif len(digits) == 12 and digits[:2] == '91' and digits[2] in '6789':
        return True
    
    return False
