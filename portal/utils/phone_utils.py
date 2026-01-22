"""
Phone number utility functions
"""
import re
from typing import Optional


def normalize_phone_number(phone: str, country_code: str = "91") -> str:
    """
    Normalize phone number to format: 91XXXXXXXXXX (no + sign)
    
    Args:
        phone: Phone number in any format (e.g., "9876543210", "+919876543210", "0919876543210")
        country_code: Country code to use (default: "91" for India)
    
    Returns:
        Normalized phone number in format: 91XXXXXXXXXX (no + sign)
    
    Examples:
        >>> normalize_phone_number("9876543210")
        '919876543210'
        >>> normalize_phone_number("+919876543210")
        '919876543210'
        >>> normalize_phone_number("0919876543210")
        '919876543210'
        >>> normalize_phone_number("919876543210")
        '919876543210'
    """
    if not phone:
        raise ValueError("Phone number cannot be empty")
    
    # Remove all spaces, dashes, and parentheses
    phone = re.sub(r'[\s\-\(\)]', '', str(phone).strip())
    
    # Remove leading + if present
    if phone.startswith('+'):
        phone = phone[1:]
    
    # Remove leading 0 if present (common in Indian numbers)
    if phone.startswith('0'):
        phone = phone[1:]
    
    # Remove country code if already present at the start
    if phone.startswith(country_code):
        phone = phone[len(country_code):]
    
    # Validate that remaining digits are valid Indian mobile number (10 digits starting with 6-9)
    if not re.match(r'^[6-9]\d{9}$', phone):
        raise ValueError(f"Invalid Indian mobile number format: {phone}. Must be 10 digits starting with 6-9.")
    
    # Return normalized format: 91XXXXXXXXXX (no + sign)
    return f"{country_code}{phone}"


def format_phone_for_kaleyra(phone: str) -> str:
    """
    Format phone number specifically for Kaleyra API (India)
    Kaleyra API requires + prefix, so we add it here
    
    Args:
        phone: Phone number in any format
    
    Returns:
        Phone number formatted as +91XXXXXXXXXX for Kaleyra API
    """
    normalized = normalize_phone_number(phone, country_code="91")
    # Kaleyra API requires + prefix
    return f"+{normalized}"


def is_valid_indian_mobile(phone: str) -> bool:
    """
    Check if phone number is a valid Indian mobile number
    
    Args:
        phone: Phone number to validate
    
    Returns:
        True if valid Indian mobile number, False otherwise
    """
    try:
        normalized = normalize_phone_number(phone)
        # Check if it's 12 digits (91 + 10 digit mobile)
        return len(normalized) == 12 and normalized.startswith('91') and normalized[2:].isdigit()
    except (ValueError, AttributeError):
        return False
