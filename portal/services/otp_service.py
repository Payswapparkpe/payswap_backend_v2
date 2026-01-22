"""
OTP Service using Kaleyra
"""
import random
import string
from typing import Optional
from django.core.cache import cache
from portal.services.vendors.kaleyra import KaleyraClient
from portal.utils.mfa_utils import store_otp_in_cache, verify_otp_from_cache


class OTPService:
    """OTP service for SMS OTP"""
    
    def __init__(self):
        self.kaleyra_client = KaleyraClient()
        self.otp_length = 6
        self.otp_expiry = 300  # 5 minutes
    
    def generate_otp(self) -> str:
        """
        Generate random OTP
        
        Returns:
            6-digit OTP string
        """
        return ''.join(random.choices(string.digits, k=self.otp_length))
    
    def send_otp(self, phone_number: str) -> tuple[bool, Optional[str]]:
        """
        Generate and send OTP via SMS
        
        Args:
            phone_number: Phone number
        
        Returns:
            Tuple of (success, otp_code or error_message)
        """
        # Check rate limiting
        rate_limit_key = f"otp_rate_limit:{phone_number}"
        request_count = cache.get(rate_limit_key, 0)
        
        if request_count >= 3:
            return False, "Maximum OTP requests reached. Please try again later."
        
        # Generate OTP
        otp = self.generate_otp()
        
        # Store OTP in cache
        store_otp_in_cache(phone_number, otp, self.otp_expiry)
        
        # Update rate limit
        cache.set(rate_limit_key, request_count + 1, timeout=600)  # 10 minutes window
        
        # Send SMS
        try:
            success = self.kaleyra_client.send_otp(phone_number, otp)
            if success:
                return True, otp
            else:
                return False, "Failed to send OTP. Please try again."
        except Exception as e:
            return False, f"Error sending OTP: {str(e)}"
    
    def verify_otp(self, phone_number: str, otp_code: str) -> bool:
        """
        Verify OTP code
        
        Args:
            phone_number: Phone number
            otp_code: OTP code to verify
        
        Returns:
            True if OTP is valid
        """
        return verify_otp_from_cache(phone_number, otp_code)
