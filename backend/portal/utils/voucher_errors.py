"""
Error codes and messages for gift voucher operations
"""

# Error codes
VOUCHER_NOT_FOUND = 'VOUCHER_NOT_FOUND'
INVALID_PIN = 'INVALID_PIN'
PIN_LOCKED = 'PIN_LOCKED'
INSUFFICIENT_BALANCE = 'INSUFFICIENT_BALANCE'
VOUCHER_BLOCKED = 'VOUCHER_BLOCKED'
VOUCHER_EXPIRED = 'VOUCHER_EXPIRED'
INVALID_OTP = 'INVALID_OTP'
OTP_EXPIRED = 'OTP_EXPIRED'
OTP_MAX_ATTEMPTS = 'OTP_MAX_ATTEMPTS'
PIN_REUSED = 'PIN_REUSED'
INVALID_AMOUNT = 'INVALID_AMOUNT'
BRAND_NOT_FOUND = 'BRAND_NOT_FOUND'
DUPLICATE_TRANSACTION = 'DUPLICATE_TRANSACTION'
BULK_UPLOAD_FAILED = 'BULK_UPLOAD_FAILED'
INVALID_FILE_FORMAT = 'INVALID_FILE_FORMAT'
INVALID_VOUCHER_CODE_FORMAT = 'INVALID_VOUCHER_CODE_FORMAT'
VOUCHER_ALREADY_REDEEMED = 'VOUCHER_ALREADY_REDEEMED'
MOBILE_NUMBER_REQUIRED = 'MOBILE_NUMBER_REQUIRED'
INVALID_MOBILE_NUMBER = 'INVALID_MOBILE_NUMBER'
OTP_NOT_SENT = 'OTP_NOT_SENT'
OTP_RESEND_COOLDOWN = 'OTP_RESEND_COOLDOWN'

# Error messages mapping
ERROR_MESSAGES = {
    VOUCHER_NOT_FOUND: 'Voucher code does not exist',
    INVALID_PIN: 'PIN does not match',
    PIN_LOCKED: 'Too many failed attempts. PIN is temporarily blocked. Please try again after 15 minutes.',
    INSUFFICIENT_BALANCE: 'Redemption amount exceeds available balance',
    VOUCHER_BLOCKED: 'Voucher is permanently blocked',
    VOUCHER_EXPIRED: 'Voucher has expired',
    INVALID_OTP: 'OTP does not match',
    OTP_EXPIRED: 'OTP validity period has expired',
    OTP_MAX_ATTEMPTS: 'Maximum OTP verification attempts exceeded',
    PIN_REUSED: 'New PIN matches a recently used PIN. Please choose a different PIN.',
    INVALID_AMOUNT: 'Invalid redemption amount',
    BRAND_NOT_FOUND: 'Brand does not exist',
    DUPLICATE_TRANSACTION: 'Transaction reference already exists',
    BULK_UPLOAD_FAILED: 'Bulk file processing failed',
    INVALID_FILE_FORMAT: 'Uploaded file format is invalid',
    INVALID_VOUCHER_CODE_FORMAT: 'Invalid voucher code format',
    VOUCHER_ALREADY_REDEEMED: 'Voucher has already been fully redeemed',
    MOBILE_NUMBER_REQUIRED: 'Mobile number is required for OTP-based operations',
    INVALID_MOBILE_NUMBER: 'Invalid mobile number format',
    OTP_NOT_SENT: 'OTP could not be sent. Please try again.',
    OTP_RESEND_COOLDOWN: 'Please wait 30 seconds before requesting a new OTP',
}


def get_error_message(error_code: str) -> str:
    """
    Get human-readable error message for error code
    
    Args:
        error_code: Error code constant
    
    Returns:
        Error message string
    """
    return ERROR_MESSAGES.get(error_code, 'An error occurred')


def create_error_response(error_code: str, details: dict = None, retry_attempts_left: int = None) -> dict:
    """
    Create standard error response dict
    
    Args:
        error_code: Error code constant
        details: Additional error details
        retry_attempts_left: Number of retry attempts remaining (for PIN errors)
    
    Returns:
        Error response dictionary
    """
    response = {
        'success': False,
        'error': {
            'code': error_code,
            'message': get_error_message(error_code),
        }
    }
    
    if details:
        response['error']['details'] = details
    
    if retry_attempts_left is not None:
        response['error']['retry_attempts_left'] = retry_attempts_left
    
    return response
