"""
Encryption utilities for sensitive data
"""
from cryptography.fernet import Fernet
from django.conf import settings
from core.config import payswap_config
import base64
import hashlib


def get_encryption_key() -> bytes:
    """
    Get encryption key from config
    
    Returns:
        Encryption key as bytes
    """
    encryption_key = payswap_config.get_encryption_key()
    # Ensure key is 32 bytes for Fernet
    key_hash = hashlib.sha256(encryption_key.encode()).digest()
    return base64.urlsafe_b64encode(key_hash)


def encrypt_data(data: str) -> str:
    """
    Encrypt sensitive data
    
    Args:
        data: String data to encrypt
    
    Returns:
        Encrypted string (base64 encoded)
    """
    key = get_encryption_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data.encode())
    return encrypted.decode()


def decrypt_data(encrypted_data: str) -> str:
    """
    Decrypt sensitive data
    
    Args:
        encrypted_data: Encrypted string (base64 encoded)
    
    Returns:
        Decrypted string
    """
    key = get_encryption_key()
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted_data.encode())
    return decrypted.decode()
