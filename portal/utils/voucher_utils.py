"""
Utility functions for gift voucher operations
"""
import secrets
import bcrypt
import re
from typing import Optional
from django.utils import timezone
from datetime import timedelta
from portal.models import GiftVoucher


# Character set for voucher codes (excludes I, O, 0, 1 to avoid confusion)
VOUCHER_CODE_CHARSET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
VOUCHER_CODE_LENGTH = 16
PIN_LENGTH = 4
PIN_MIN = 1000
PIN_MAX = 9999
MAX_CODE_GENERATION_RETRIES = 3


def generate_voucher_code() -> str:
    """
    Generate unique 16-digit alphanumeric voucher code
    Format: XXXX-XXXX-XXXX-XXXX
    Character set: 23456789ABCDEFGHJKLMNPQRSTUVWXYZ (excludes I, O, 0, 1)
    
    Returns:
        16-character voucher code (without hyphens for storage)
    """
    code = ''
    for _ in range(VOUCHER_CODE_LENGTH):
        random_index = secrets.randbelow(len(VOUCHER_CODE_CHARSET))
        code += VOUCHER_CODE_CHARSET[random_index]
    
    return code


def format_voucher_code(code: str) -> str:
    """
    Format voucher code with hyphens for display
    Format: XXXX-XXXX-XXXX-XXXX
    
    Args:
        code: 16-character voucher code
    
    Returns:
        Formatted code with hyphens
    """
    if len(code) != VOUCHER_CODE_LENGTH:
        return code
    return '-'.join([code[i:i+4] for i in range(0, VOUCHER_CODE_LENGTH, 4)])


def unformat_voucher_code(formatted_code: str) -> str:
    """
    Remove hyphens from formatted voucher code
    
    Args:
        formatted_code: Formatted code with hyphens
    
    Returns:
        Code without hyphens
    """
    return formatted_code.replace('-', '').upper()


def generate_unique_voucher_code() -> str:
    """
    Generate unique voucher code that doesn't exist in database
    Retries up to MAX_CODE_GENERATION_RETRIES times
    
    Returns:
        Unique 16-character voucher code
    """
    for attempt in range(MAX_CODE_GENERATION_RETRIES):
        code = generate_voucher_code()
        # Check if code already exists (without hyphens)
        if not GiftVoucher.objects.filter(voucher_code=code).exists():
            return code
    
    # If all retries failed, raise exception
    raise Exception("Failed to generate unique voucher code after multiple attempts")


def generate_pin() -> str:
    """
    Generate random 4-digit PIN (1000-9999)
    Avoids sequential patterns (1234, 4321) and repeated digits (1111, 2222)
    
    Returns:
        4-digit PIN string
    """
    max_attempts = 100
    for _ in range(max_attempts):
        pin = str(secrets.randbelow(PIN_MAX - PIN_MIN + 1) + PIN_MIN)
        
        # Check for sequential patterns
        is_sequential = False
        digits = [int(d) for d in pin]
        if len(set(digits)) == 4:  # All digits different
            # Check ascending sequence
            if digits == sorted(digits) or digits == sorted(digits, reverse=True):
                is_sequential = True
        
        # Check for repeated digits (all same)
        if len(set(digits)) == 1:
            continue
        
        # If not sequential, return it
        if not is_sequential:
            return pin
    
    # Fallback: return any random PIN if we couldn't find a non-sequential one
    return str(secrets.randbelow(PIN_MAX - PIN_MIN + 1) + PIN_MIN)


def validate_pin_format(pin: str) -> bool:
    """
    Validate PIN format (4 digits, 1000-9999)
    
    Args:
        pin: PIN string to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not pin or not isinstance(pin, str):
        return False
    
    # Check if it's exactly 4 digits
    if not re.match(r'^\d{4}$', pin):
        return False
    
    # Check if it's in valid range
    try:
        pin_int = int(pin)
        return PIN_MIN <= pin_int <= PIN_MAX
    except ValueError:
        return False


def hash_pin(pin: str) -> str:
    """
    Hash PIN using bcrypt (salt rounds=12)
    
    Args:
        pin: Plain text PIN
    
    Returns:
        Hashed PIN string
    """
    if not validate_pin_format(pin):
        raise ValueError("Invalid PIN format")
    
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pin.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_pin(pin: str, pin_hash: str) -> bool:
    """
    Verify PIN against hash
    
    Args:
        pin: Plain text PIN
        pin_hash: Hashed PIN
    
    Returns:
        True if PIN matches, False otherwise
    """
    if not validate_pin_format(pin):
        return False
    
    try:
        return bcrypt.checkpw(pin.encode('utf-8'), pin_hash.encode('utf-8'))
    except Exception:
        return False


def check_pin_history(new_pin: str, pin_history: list) -> bool:
    """
    Check if new PIN matches any of the last 3 PINs in history
    
    Args:
        new_pin: New PIN to check
        pin_history: List of previous PIN hashes (JSON array)
    
    Returns:
        True if PIN matches any in history, False otherwise
    """
    if not validate_pin_format(new_pin):
        return True  # Invalid PIN is considered as reused
    
    if not pin_history or not isinstance(pin_history, list):
        return False
    
    # Check against all hashes in history
    for old_hash in pin_history:
        if verify_pin(new_pin, old_hash):
            return True
    
    return False


def generate_reference_number(prefix: str = 'REF') -> str:
    """
    Generate unique reference number
    Format: PREFIX-YYYYMMDD-HHMMSS-XXXXXX (random 6 digits)
    
    Args:
        prefix: Reference prefix (default: 'REF')
    
    Returns:
        Unique reference number
    """
    from datetime import datetime
    timestamp = datetime.now()
    date_str = timestamp.strftime('%Y%m%d')
    time_str = timestamp.strftime('%H%M%S')
    random_suffix = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    return f"{prefix}-{date_str}-{time_str}-{random_suffix}"


def mask_mobile_number(mobile_number: str) -> str:
    """
    Mask mobile number for display
    Format: ******7890 (last 4 digits visible)
    
    Args:
        mobile_number: Mobile number to mask
    
    Returns:
        Masked mobile number
    """
    if not mobile_number or len(mobile_number) < 4:
        return '****'
    
    # Show last 4 digits
    return '*' * (len(mobile_number) - 4) + mobile_number[-4:]


def is_pin_blocked(pin_blocked_until: Optional[timezone.datetime]) -> bool:
    """
    Check if PIN is currently blocked
    
    Args:
        pin_blocked_until: Timestamp until which PIN is blocked
    
    Returns:
        True if blocked, False otherwise
    """
    if not pin_blocked_until:
        return False
    
    return timezone.now() < pin_blocked_until


def get_pin_block_duration_minutes() -> int:
    """
    Get PIN block duration in minutes (15 minutes)
    
    Returns:
        Block duration in minutes
    """
    return 15


def calculate_pin_block_until() -> timezone.datetime:
    """
    Calculate timestamp when PIN block expires (15 minutes from now)
    
    Returns:
        Timestamp when block expires
    """
    return timezone.now() + timedelta(minutes=get_pin_block_duration_minutes())


def generate_client_code(brand, client_name: str) -> str:
    """
    Generate unique client code based on brand and client name
    Format: BRANDCODE-CLIENT-XXXXXX (6 random alphanumeric)
    
    Args:
        brand: GiftVoucherBrand instance
        client_name: Client name
    
    Returns:
        Unique client code
    """
    from portal.models import VoucherClient
    import string
    
    # Get brand code prefix
    brand_prefix = brand.brand_code[:6].upper() if brand.brand_code else 'BRAND'
    
    # Get client name prefix (first 3 letters, uppercase)
    client_prefix = ''.join([c for c in client_name[:3] if c.isalnum()]).upper()
    if not client_prefix:
        client_prefix = 'CLT'
    
    # Generate unique code
    max_attempts = 10
    for attempt in range(max_attempts):
        random_suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        client_code = f"{brand_prefix}-{client_prefix}-{random_suffix}"
        
        # Check if code already exists
        if not VoucherClient.objects.filter(client_code=client_code).exists():
            return client_code
    
    # Fallback: use timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{brand_prefix}-{client_prefix}-{timestamp[-6:]}"
