"""
Custom validators
"""
from django.core.exceptions import ValidationError
import re


def normalize_phone_number(phone_number: str) -> str:
    """
    Normalize phone number to standard format (+91XXXXXXXXXX)
    
    Args:
        phone_number: Phone number string in any format
        
    Returns:
        Normalized phone number in +91XXXXXXXXXX format
        
    Raises:
        ValueError: If phone number is invalid
    """
    if not phone_number:
        raise ValueError("Phone number is required")
    
    # Remove spaces, hyphens, and other non-digit characters except +
    cleaned = phone_number.strip()
    digits = ''.join(filter(str.isdigit, cleaned))
    
    # Remove leading zeros
    digits = digits.lstrip('0')
    
    # Handle different formats
    if len(digits) == 10:
        # 10-digit number, add +91
        if digits[0] not in '6789':
            raise ValueError("Indian mobile numbers must start with 6, 7, 8, or 9")
        return f"+91{digits}"
    elif len(digits) == 12 and digits.startswith('91'):
        # Already has 91 prefix, just add +
        if digits[2] not in '6789':
            raise ValueError("Indian mobile numbers must start with 6, 7, 8, or 9")
        return f"+{digits}"
    elif len(digits) == 11 and digits.startswith('91'):
        # Has 91 but one digit short, likely error
        raise ValueError("Invalid phone number length")
    else:
        raise ValueError(f"Invalid phone number format. Expected 10 digits, got {len(digits)}")


def validate_phone_number(value: str) -> None:
    """
    Validate phone number format (Indian format)
    
    Args:
        value: Phone number string
    
    Raises:
        ValidationError: If phone number is invalid
    """
    # Indian phone number: 10 digits, optionally with +91 or 0 prefix
    pattern = r'^(\+91|0)?[6-9]\d{9}$'
    if not re.match(pattern, value.replace(' ', '').replace('-', '')):
        raise ValidationError('Invalid phone number format. Use 10-digit Indian mobile number.')


def validate_pan_number(value: str) -> None:
    """
    Validate PAN (Permanent Account Number) format
    
    Args:
        value: PAN string
    
    Raises:
        ValidationError: If PAN is invalid
    """
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
    if not re.match(pattern, value.upper()):
        raise ValidationError('Invalid PAN format. Use format: ABCDE1234F')


def validate_aadhaar_number(value: str) -> None:
    """
    Validate Aadhaar number format
    
    Args:
        value: Aadhaar string
    
    Raises:
        ValidationError: If Aadhaar is invalid
    """
    # Aadhaar: 12 digits
    pattern = r'^\d{12}$'
    if not re.match(pattern, value.replace(' ', '').replace('-', '')):
        raise ValidationError('Invalid Aadhaar format. Use 12-digit number.')
