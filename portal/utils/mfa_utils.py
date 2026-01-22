"""
MFA (Multi-Factor Authentication) utilities
"""
import pyotp
import qrcode
import io
import base64
from typing import Optional, Tuple
from django.core.cache import cache
from django.conf import settings


def generate_totp_secret() -> str:
    """
    Generate TOTP secret for authenticator app
    
    Returns:
        Base32 encoded secret
    """
    return pyotp.random_base32()


def generate_totp_uri(secret: str, email: str, issuer: str = "Payswap") -> str:
    """
    Generate TOTP URI for QR code
    
    Args:
        secret: TOTP secret
        email: User email
        issuer: Service name
    
    Returns:
        TOTP URI string
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(
        name=email,
        issuer_name=issuer
    )


def generate_qr_code(uri: str) -> str:
    """
    Generate QR code as base64 string
    
    Args:
        uri: TOTP URI
    
    Returns:
        Base64 encoded QR code image
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


def verify_totp(secret: str, token: str) -> bool:
    """
    Verify TOTP token
    
    Args:
        secret: TOTP secret
        token: User-provided token
    
    Returns:
        True if token is valid
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)


def store_otp_in_cache(phone_number: str, otp: str, expiry_seconds: int = 300) -> None:
    """
    Store OTP in Redis cache
    
    Args:
        phone_number: Phone number
        otp: OTP code
        expiry_seconds: OTP expiry time in seconds (default: 5 minutes)
    """
    cache_key = f"otp:{phone_number}"
    cache.set(cache_key, otp, timeout=expiry_seconds)


def verify_otp_from_cache(phone_number: str, otp: str) -> bool:
    """
    Verify OTP from cache
    
    Args:
        phone_number: Phone number
        otp: OTP code to verify
    
    Returns:
        True if OTP is valid
    """
    cache_key = f"otp:{phone_number}"
    cached_otp = cache.get(cache_key)
    
    if cached_otp and cached_otp == otp:
        # Delete OTP after successful verification
        cache.delete(cache_key)
        return True
    
    return False
