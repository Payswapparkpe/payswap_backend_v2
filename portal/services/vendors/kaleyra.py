"""
Kaleyra SMS API client for India
Based on Kaleyra API documentation: https://developers.kaleyra.io/docs/sms-api-send-the-first-sms
"""
import httpx
from typing import Optional
from core.config import payswap_config
from portal.utils.phone_utils import format_phone_for_kaleyra, normalize_phone_number


class KaleyraClient:
    """Kaleyra SMS API client for India region"""
    
    def __init__(self):
        self.api_key = payswap_config.get_kaleyra_api_key()
        self.sid = payswap_config.KALEYRA_SID
        # Use India-specific API endpoint: https://api.in.kaleyra.io/v1/<<SID>>
        self.base_url = f"https://api.in.kaleyra.io/v1/{self.sid}"
    
    def send_sms(
        self, 
        to: str, 
        message: str, 
        message_type: str = "TXN",
        sender: Optional[str] = None
    ) -> dict:
        """
        Send SMS via Kaleyra API (India)
        
        Args:
            to: Phone number (will be normalized to +91XXXXXXXXXX format)
            message: SMS message content
            message_type: Message type - "TXN" for transactional, "MKT" for marketing (default: "TXN")
            sender: Sender ID (defaults to configured SID)
        
        Returns:
            API response dict
        
        Raises:
            ValueError: If phone number is invalid
            Exception: If API call fails
        """
        # Normalize phone number to 91XXXXXXXXXX format (no +), then add + for Kaleyra API
        try:
            # First normalize to 91XXXXXXXXXX (no +)
            normalized = normalize_phone_number(to)
            # Kaleyra API requires + prefix, so format it
            normalized_phone = format_phone_for_kaleyra(normalized)
        except ValueError as e:
            raise ValueError(f"Invalid phone number format: {str(e)}")
        
        # Use configured SID as sender if not provided
        sender_id = sender or self.sid
        
        # Kaleyra India API endpoint: POST /sms
        url = f"{self.base_url}/sms"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Request body according to Kaleyra API documentation
        data = {
            "to": normalized_phone,  # Format: +91XXXXXXXXXX (Kaleyra requires +)
            "sender": sender_id,
            "type": message_type,  # TXN for transactional, MKT for marketing
            "body": message,
            "unicode": "Auto"  # Auto-detect Unicode
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=headers, timeout=10)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            raise Exception(f"Kaleyra API error: {error_detail}")
        except Exception as e:
            raise Exception(f"Kaleyra API error: {str(e)}")
    
    def send_otp(self, phone_number: str, otp: str) -> bool:
        """
        Send OTP via SMS using transactional message type
        
        Args:
            phone_number: Phone number (will be normalized to +91XXXXXXXXXX)
            otp: OTP code
        
        Returns:
            True if sent successfully, False otherwise
        """
        message = f"Your Payswap verification code is {otp}. Valid for 5 minutes."
        try:
            # Use TXN type for OTP messages (transactional)
            result = self.send_sms(phone_number, message, message_type="TXN")
            # Check for success indicators in response
            # Kaleyra API may return different success indicators
            if isinstance(result, dict):
                # Check common success indicators
                status = result.get('status', '').lower()
                if status in ['queued', 'sent', 'success', 'submitted']:
                    return True
                # Check for message ID or similar indicators
                if 'id' in result or 'message_id' in result or 'request_id' in result:
                    return True
            return False
        except Exception:
            return False
