"""
Encryption utilities for voucher codes
Extends existing encryption utilities for voucher-specific operations
"""
from portal.utils.encryption import encrypt_data, decrypt_data


def encrypt_voucher_code(voucher_code: str) -> str:
    """
    Encrypt voucher code for storage
    
    Args:
        voucher_code: Plain text voucher code (16 characters, no hyphens)
    
    Returns:
        Encrypted voucher code string
    """
    return encrypt_data(voucher_code)


def decrypt_voucher_code(encrypted_code: str) -> str:
    """
    Decrypt voucher code from storage
    
    Args:
        encrypted_code: Encrypted voucher code string
    
    Returns:
        Plain text voucher code (16 characters, no hyphens)
    """
    return decrypt_data(encrypted_code)
