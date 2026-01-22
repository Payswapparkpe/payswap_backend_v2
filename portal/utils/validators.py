"""
Custom validators
"""
from django.core.exceptions import ValidationError
import re


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
