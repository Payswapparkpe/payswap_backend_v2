"""
Kaleyra SMS API client
"""
import httpx
from typing import Optional
from core.config import payswap_config


class KaleyraClient:
    """Kaleyra SMS API client"""
    
    def __init__(self):
        self.api_key = payswap_config.get_kaleyra_api_key()
        self.sid = payswap_config.KALEYRA_SID
        self.base_url = payswap_config.KALEYRA_BASE_URL
    
    def send_sms(self, to: str, message: str) -> dict:
        """
        Send SMS via Kaleyra
        
        Args:
            to: Phone number (with country code)
            message: SMS message
        
        Returns:
            API response dict
        """
        url = f"{self.base_url}/messages"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        data = {
            "to": to,
            "sender": self.sid,
            "body": message
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=headers, timeout=10)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            raise Exception(f"Kaleyra API error: {str(e)}")
    
    def send_otp(self, phone_number: str, otp: str) -> bool:
        """
        Send OTP via SMS
        
        Args:
            phone_number: Phone number
            otp: OTP code
        
        Returns:
            True if sent successfully
        """
        message = f"Your Payswap verification code is {otp}. Valid for 5 minutes."
        try:
            result = self.send_sms(phone_number, message)
            return result.get('status') == 'queued' or 'id' in result
        except Exception:
            return False
