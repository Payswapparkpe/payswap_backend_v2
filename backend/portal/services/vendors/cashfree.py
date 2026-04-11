"""
Cashfree Verification API client
Complete integration for all Cashfree verification APIs
Based on Cashfree Secure ID VRS API documentation
"""
import httpx
import uuid
import time
import traceback
import base64
from typing import Optional, Dict, Any
from django.utils import timezone
from core.config import payswap_config

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False


class CashfreeClient:
    """Cashfree Verification API client with all verification methods"""
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Cashfree client
        
        Args:
            api_key: Cashfree API key (Client ID)
            api_secret: Cashfree API secret (Client Secret)
        """
        # Get credentials from config or parameters
        config_key = getattr(payswap_config, 'CASHFREE_API_KEY', None)
        config_secret = getattr(payswap_config, 'CASHFREE_API_SECRET', None)
        
        # Handle SecretStr type from config
        if config_key:
            self.api_key = api_key or (config_key.get_secret_value() if hasattr(config_key, 'get_secret_value') else str(config_key))
        else:
            self.api_key = api_key
        
        if config_secret:
            self.api_secret = api_secret or (config_secret.get_secret_value() if hasattr(config_secret, 'get_secret_value') else str(config_secret))
        else:
            self.api_secret = api_secret
        
        # Use production URL by default (as per user requirement)
        # Can be overridden via CASHFREE_BASE_URL in .env if needed
        cashfree_base_url = getattr(payswap_config, 'CASHFREE_BASE_URL', None)
        if cashfree_base_url:
            self.base_url = cashfree_base_url.rstrip('/')
            if not self.base_url.endswith('/verification'):
                self.base_url = f"{self.base_url}/verification"
        else:
            # Default to production URL (user has production API keys)
            self.base_url = "https://api.cashfree.com/verification"
        self.api_version = "2023-08-01"
        
        # Load public key for signature generation (optional - only needed if IP is not whitelisted)
        self.public_key = None
        self._load_public_key()
    
    def _load_public_key(self):
        """Load Cashfree public key for signature generation"""
        if not CRYPTOGRAPHY_AVAILABLE:
            return
        
        try:
            # Try to load from config (PEM string)
            public_key_str = getattr(payswap_config, 'CASHFREE_PUBLIC_KEY', None)
            if public_key_str:
                self.public_key = load_pem_public_key(
                    public_key_str.encode('utf-8'),
                    backend=default_backend()
                )
                return
            
            # Try to load from file path
            public_key_path = getattr(payswap_config, 'CASHFREE_PUBLIC_KEY_PATH', None)
            if public_key_path:
                with open(public_key_path, 'rb') as f:
                    self.public_key = load_pem_public_key(
                        f.read(),
                        backend=default_backend()
                    )
        except Exception as e:
            import logging
            logging.getLogger('portal.services.cashfree').warning(
                f"Failed to load Cashfree public key: {str(e)}. "
                "Signature generation will be disabled. "
                "Either whitelist your IP in Cashfree dashboard or configure CASHFREE_PUBLIC_KEY."
            )
            self.public_key = None
    
    def _generate_signature(self) -> Optional[str]:
        """
        Generate x-cf-signature for Cashfree API authentication
        
        Steps:
        1. Retrieve clientId (x-client-id)
        2. Append CURRENT UNIX timestamp separated by period (.)
        3. Encrypt using RSA with public key (PKCS1_OAEP_PADDING)
        4. Base64 encode the result
        
        Returns:
            Base64 encoded signature string, or None if signature generation fails
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            return None
        
        if not self.public_key or not self.api_key:
            return None
        
        try:
            # Step 1 & 2: clientId + current timestamp
            # Note: Use current Unix timestamp (seconds since epoch)
            current_timestamp = int(time.time())
            data_to_sign = f"{self.api_key}.{current_timestamp}"
            
            # Step 3: Encrypt with RSA
            # Based on Cashfree PHP examples and common RSA encryption practices,
            # we use OAEP padding with SHA-1 (more compatible with Cashfree's system)
            encrypted = self.public_key.encrypt(
                data_to_sign.encode('utf-8'),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA1()),
                    algorithm=hashes.SHA1(),
                    label=None
                )
            )
            
            # Step 4: Base64 encode
            signature = base64.b64encode(encrypted).decode('utf-8')
            return signature
            
        except Exception as e:
            import logging
            logging.getLogger('portal.services.cashfree').error(
                f"Failed to generate Cashfree signature: {str(e)}",
                exc_info=True
            )
            return None
    
    def _generate_verification_id(self, prefix: str = "verif") -> str:
        """
        Generate unique verification ID for Cashfree API requests.

        Uses unified ParkPe transaction ID format (20 chars, ``T`` + timestamp + entropy).
        The ``prefix`` argument is kept for API compatibility but not prepended (Cashfree
        accepts alphanumeric IDs; length <= 50).
        """
        from portal.utils.transaction_id import generate_transaction_id

        return generate_transaction_id()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests"""
        headers = {
            "x-api-version": self.api_version,
            "Content-Type": "application/json"
        }
        
        if self.api_key:
            headers["x-client-id"] = self.api_key
        if self.api_secret:
            headers["x-client-secret"] = self.api_secret
        
        # Generate and add signature if public key is available
        # Signature is required if IP is not whitelisted in Cashfree dashboard
        signature = self._generate_signature()
        if signature:
            headers["x-cf-signature"] = signature
        
        return headers
    
    def _make_request(self, method: str, endpoint: str, payload: Optional[Dict] = None, api_type: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Make API request to Cashfree with proper error handling and logging
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            payload: Request payload
            api_type: Type of API call (for logging)
            user_id: User ID making the request (for logging)
            request_id: Request ID for tracing
            client_ip: Client IP address
            user_agent: User agent string
        
        Returns:
            API response as dict
        """
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()
        start_time = time.time()
        status = 'success'
        status_code = None
        response_data = None
        error_message = None
        error_code = None
        error_type = None
        error_traceback = None
        
        # Sanitize payload for logging (remove sensitive data)
        sanitized_payload = self._sanitize_payload(payload) if payload else None
        
        try:
            with httpx.Client(timeout=30.0) as client:
                if method.upper() == "POST":
                    response = client.post(url, headers=headers, json=payload)
                elif method.upper() == "GET":
                    response = client.get(url, headers=headers, params=payload)
                else:
                    response = client.request(method, url, headers=headers, json=payload)
                
                status_code = response.status_code
                
                # Try to parse response JSON
                try:
                    response_data = response.json()
                except:
                    # If JSON parsing fails, use text response
                    response_text = response.text
                    response_data = {'raw_response': response_text} if response_text else {}
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Calculate response time
                response_time = time.time() - start_time
                
                # Log successful API call - ALWAYS log, even if there's an error in logging
                try:
                    self._log_api_call(
                        api_type=api_type or endpoint,
                        endpoint=endpoint,
                        method=method,
                        status='success',
                        status_code=status_code,
                        request_payload=sanitized_payload,
                        response_data=response_data,
                        response_time=response_time,
                        user_id=user_id,
                        request_id=request_id,
                        client_ip=client_ip,
                        user_agent=user_agent,
                        verification_id=payload.get('verification_id') if payload else None
                    )
                except Exception as log_exception:
                    # Even if logging fails, don't break the API response
                    import logging
                    logging.getLogger('portal.services.cashfree').error(
                        f"Failed to log successful API call: {str(log_exception)}",
                        exc_info=True
                    )
                
                return response_data
                
        except httpx.HTTPStatusError as e:
            status = 'error'
            status_code = e.response.status_code
            error_msg = f"Cashfree API error: HTTP {e.response.status_code}"
            error_code = None
            error_type = None
            response_data = None
            response_text = None
            
            # Try to get error details from response
            try:
                response_text = e.response.text if hasattr(e.response, 'text') else str(e.response)
                if response_text:
                    try:
                        error_data = e.response.json()
                        # Cashfree error format can vary - check multiple possible structures
                        error_msg = (
                            error_data.get('message') or 
                            error_data.get('error', {}).get('message') if isinstance(error_data.get('error'), dict) else None or
                            error_data.get('error') if isinstance(error_data.get('error'), str) else None or
                            error_msg
                        )
                        error_code = (
                            error_data.get('code') or
                            error_data.get('error', {}).get('code') if isinstance(error_data.get('error'), dict) else None
                        )
                        error_type = (
                            error_data.get('type') or
                            error_data.get('error', {}).get('type') if isinstance(error_data.get('error'), dict) else None
                        )
                        response_data = error_data
                    except Exception as json_error:
                        # If JSON parsing fails, use text response
                        error_msg = f"Cashfree API error: HTTP {status_code} - {response_text[:200]}"
                        response_data = {'raw_response': response_text, 'parse_error': str(json_error)}
            except Exception as parse_error:
                # If we can't get response text, use status code
                error_msg = f"Cashfree API error: HTTP {status_code} (Failed to parse response: {str(parse_error)})"
                response_data = {'parse_error': str(parse_error), 'status_code': status_code}
            
            error_message = error_msg
            error_traceback = traceback.format_exc()
            response_time = time.time() - start_time
            
            # Log failed API call - IMPORTANT: This must happen before raising exception
            # Use a separate try-except to ensure logging doesn't prevent error from being raised
            try:
                self._log_api_call(
                    api_type=api_type or endpoint,
                    endpoint=endpoint,
                    method=method,
                    status='error',
                    status_code=status_code,
                    request_payload=sanitized_payload,
                    response_data=response_data,
                    response_time=response_time,
                    error_message=error_message,
                    error_code=error_code,
                    error_type=error_type,
                    traceback=error_traceback,
                    user_id=user_id,
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    verification_id=payload.get('verification_id') if payload else None
                )
            except Exception as log_error:
                # Even if logging fails, we should still raise the original error
                # But also try to create a minimal log entry directly
                try:
                    from django.contrib.auth import get_user_model
                    from portal.models import LogEntry
                    from django.utils import timezone
                    User = get_user_model()
                    user = None
                    if user_id:
                        try:
                            user = User.objects.get(id=user_id)
                        except:
                            pass
                    LogEntry.objects.create(
                        timestamp=timezone.now(),
                        log_level='ERROR',
                        category='cashfree',
                        message=f"Cashfree API Error (Logging failed): {api_type or endpoint} - {endpoint} - {error_message}",
                        module_name='portal.services.vendors.cashfree',
                        url=f"/verification/{endpoint}",
                        request_id=request_id,
                        user=user,
                        client_ip=client_ip,
                        user_agent=user_agent,
                        extra_data={'api_type': api_type, 'endpoint': endpoint, 'logging_error': str(log_error)},
                        exception_type=error_type,
                        traceback=error_traceback
                    )
                except:
                    pass  # If even minimal logging fails, just continue
                
                import logging
                logging.getLogger('portal.services.cashfree').error(
                    f"Failed to log error: {str(log_error)}. Original error: {error_message}",
                    exc_info=True
                )
            
            raise Exception(f"Cashfree API error: {error_msg} (Code: {error_code}, Type: {error_type})")
            
        except httpx.RequestError as e:
            status = 'error'
            error_message = f"Cashfree API connection error: {str(e)}"
            error_traceback = traceback.format_exc()
            response_time = time.time() - start_time
            
            # Log connection error - IMPORTANT: This must happen before raising exception
            try:
                self._log_api_call(
                    api_type=api_type or endpoint,
                    endpoint=endpoint,
                    method=method,
                    status='error',
                    request_payload=sanitized_payload,
                    response_time=response_time,
                    error_message=error_message,
                    error_type='ConnectionError',
                    traceback=error_traceback,
                    user_id=user_id,
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent
                )
            except Exception as log_error:
                # Even if logging fails, try minimal log entry
                try:
                    from django.contrib.auth import get_user_model
                    from portal.models import LogEntry
                    from django.utils import timezone
                    User = get_user_model()
                    user = None
                    if user_id:
                        try:
                            user = User.objects.get(id=user_id)
                        except:
                            pass
                    LogEntry.objects.create(
                        timestamp=timezone.now(),
                        log_level='ERROR',
                        category='cashfree',
                        message=f"Cashfree API Connection Error (Logging failed): {api_type or endpoint} - {endpoint} - {error_message}",
                        module_name='portal.services.vendors.cashfree',
                        url=f"/verification/{endpoint}",
                        request_id=request_id,
                        user=user,
                        client_ip=client_ip,
                        user_agent=user_agent,
                        extra_data={'api_type': api_type, 'endpoint': endpoint, 'logging_error': str(log_error)},
                        exception_type='ConnectionError',
                        traceback=error_traceback
                    )
                except:
                    pass
                
                import logging
                logging.getLogger('portal.services.cashfree').error(
                    f"Failed to log connection error: {str(log_error)}. Original error: {error_message}",
                    exc_info=True
                )
            
            raise Exception(error_message)
            
        except Exception as e:
            status = 'error'
            error_message = f"Cashfree API error: {str(e)}"
            error_traceback = traceback.format_exc()
            response_time = time.time() - start_time
            
            # Log unexpected error - IMPORTANT: This must happen before raising exception
            try:
                self._log_api_call(
                    api_type=api_type or endpoint,
                    endpoint=endpoint,
                    method=method,
                    status='error',
                    request_payload=sanitized_payload,
                    response_time=response_time,
                    error_message=error_message,
                    error_type=type(e).__name__,
                    traceback=error_traceback,
                    user_id=user_id,
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent
                )
            except Exception as log_error:
                # Even if logging fails, try minimal log entry
                try:
                    from django.contrib.auth import get_user_model
                    from portal.models import LogEntry
                    from django.utils import timezone
                    User = get_user_model()
                    user = None
                    if user_id:
                        try:
                            user = User.objects.get(id=user_id)
                        except:
                            pass
                    LogEntry.objects.create(
                        timestamp=timezone.now(),
                        log_level='ERROR',
                        category='cashfree',
                        message=f"Cashfree API Unexpected Error (Logging failed): {api_type or endpoint} - {endpoint} - {error_message}",
                        module_name='portal.services.vendors.cashfree',
                        url=f"/verification/{endpoint}",
                        request_id=request_id,
                        user=user,
                        client_ip=client_ip,
                        user_agent=user_agent,
                        extra_data={'api_type': api_type, 'endpoint': endpoint, 'logging_error': str(log_error)},
                        exception_type=type(e).__name__,
                        traceback=error_traceback
                    )
                except:
                    pass
                
                import logging
                logging.getLogger('portal.services.cashfree').error(
                    f"Failed to log unexpected error: {str(log_error)}. Original error: {error_message}",
                    exc_info=True
                )
            
            raise Exception(error_message)
    
    def _sanitize_payload(self, payload: Dict) -> Dict:
        """
        Sanitize payload to remove sensitive data for logging
        
        Args:
            payload: Original payload
        
        Returns:
            Sanitized payload
        """
        if not payload:
            return {}
        
        sanitized = payload.copy()
        
        # Remove or mask sensitive fields
        sensitive_fields = ['api_key', 'api_secret', 'x-client-id', 'x-client-secret', 'client_id', 'client_secret']
        
        for key in sensitive_fields:
            if key in sanitized:
                sanitized[key] = '***REDACTED***'
        
        # Mask long base64 strings (images)
        for key, value in sanitized.items():
            if isinstance(value, str) and len(value) > 100 and ('base64' in key.lower() or 'image' in key.lower()):
                sanitized[key] = f"{value[:50]}...{value[-10:]} (truncated)"
        
        return sanitized
    
    def _log_api_call(
        self,
        api_type: str,
        endpoint: str,
        method: str,
        status: str,
        status_code: Optional[int] = None,
        request_payload: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        response_time: Optional[float] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        error_type: Optional[str] = None,
        traceback: Optional[str] = None,
        user_id: Optional[int] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        verification_id: Optional[str] = None
    ):
        """
        Log Cashfree API call using unified logging service
        Also creates detailed CashfreeAPILog entry for Cashfree-specific tracking
        """
        import logging
        from portal.services.unified_logging_service import UnifiedLoggingService
        logger = logging.getLogger('portal.services.cashfree')
        
        # Use unified logging service for consistent logging
        unified_logger = UnifiedLoggingService()
        
        # Build extra data for verification_id
        extra_api_data = {}
        if verification_id:
            extra_api_data['verification_id'] = verification_id
        if error_code:
            extra_api_data['error_code'] = error_code
        if error_type:
            extra_api_data['error_type'] = error_type
        
        # Log via unified logging service
        unified_logger.log_api_call(
            service='cashfree',
            endpoint=f"{api_type}/{endpoint}",
            method=method,
            request_payload=request_payload,
            response_data=response_data,
            status_code=status_code,
            response_time=response_time,
            user=None,  # User object not available here, user_id is passed
            request=None,  # Request object not available in this context
            error_message=error_message if status == 'error' else None,
            async_log=True
        )
        
        # Also create detailed CashfreeAPILog entry for Cashfree-specific tracking
        try:
            from django.contrib.auth import get_user_model
            from portal.models import CashfreeAPILog
            from django.utils import timezone
            
            User = get_user_model()
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    pass
            
            CashfreeAPILog.objects.create(
                timestamp=timezone.now(),
                api_type=api_type,
                status=status,
                endpoint=endpoint,
                method=method,
                request_payload=request_payload,
                response_data=response_data,
                status_code=status_code,
                response_time=response_time,
                error_message=error_message,
                error_code=error_code,
                error_type=error_type,
                traceback=traceback,
                user=user,
                request_id=request_id,
                client_ip=client_ip,
                user_agent=user_agent,
                verification_id=verification_id,
                log_entry=None  # LogEntry is created by unified logging service
            )
            logger.debug(f"Cashfree API log created: {api_type} - {endpoint} - {status}")
            if status == 'success':
                try:
                    from portal.services.hub_cost_service import record_hub_cost
                    if api_type == 'vehicle_rc':
                        record_hub_cost('cashfree_rc', 'cashfree', unit_count=1, reference_id=verification_id or request_id)
                    elif api_type not in ('test_connection',):
                        record_hub_cost('cashfree_kyc', 'cashfree', unit_count=1, reference_id=verification_id or request_id)
                except Exception:
                    pass
        except Exception as cashfree_log_error:
            logger.warning(f"Failed to create CashfreeAPILog: {str(cashfree_log_error)}", exc_info=True)
            # Don't fail if Cashfree-specific log fails, unified logging already succeeded
    
    # ============================================================================
    # DOCUMENT VERIFICATION APIs
    # ============================================================================
    
    def verify_pan(self, pan_number: str, name: Optional[str] = None, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify PAN card using Cashfree VRS API
        
        Args:
            pan_number: PAN card number (10 characters, e.g., ABCDE1234F)
            name: Optional name to verify against PAN
            verification_id: Optional verification ID (auto-generated if not provided)
            user_id: User ID making the request (for logging)
            request_id: Request ID for tracing
            client_ip: Client IP address
            user_agent: User agent string
        
        Returns:
            Verification response dict with pan, type, valid, name_match_score, etc.
        """
        payload = {
            "pan": pan_number.upper().strip()
        }
        if name:
            payload["name"] = name.strip()
        
        return self._make_request(
            "POST", 
            "pan", 
            payload,
            api_type='pan',
            user_id=user_id,
            request_id=request_id,
            client_ip=client_ip,
            user_agent=user_agent
        )
    
    def verify_aadhaar(self, aadhaar_number: str, name: Optional[str] = None, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify Aadhaar card using Cashfree VRS API
        
        Note: Aadhaar verification may require different endpoints based on method (OCR, DigiLocker, etc.)
        This is a basic implementation - may need to be updated based on specific Aadhaar API endpoint
        
        Args:
            aadhaar_number: Aadhaar number (12 digits)
            name: Optional name to verify against Aadhaar
            verification_id: Optional verification ID (auto-generated if not provided)
            user_id: User ID making the request (for logging)
            request_id: Request ID for tracing
            client_ip: Client IP address
            user_agent: User agent string
        
        Returns:
            Verification response dict
        """
        # Note: Aadhaar endpoint may vary - using placeholder based on common pattern
        # May need to use /aadhaar or specific endpoint like /aadhaar/verify
        payload = {
            "aadhaar_number": aadhaar_number.strip()
        }
        if name:
            payload["name"] = name.strip()
        
        # Try aadhaar endpoint - if this doesn't work, may need to check actual endpoint
        return self._make_request("POST", "aadhaar", payload, api_type='aadhaar', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_driving_license(self, dl_number: str, dob: Optional[str] = None, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify Driving License using Cashfree VRS API
        
        Args:
            dl_number: Driving License number
            dob: Date of birth (YYYY-MM-DD format) - REQUIRED
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with status, dl_number, name, address, etc.
        """
        if not verification_id:
            verification_id = self._generate_verification_id("dl")
        
        if not dob:
            raise ValueError("Date of birth (dob) is required for driving license verification")
        
        payload = {
            "verification_id": verification_id,
            "dl_number": dl_number.strip(),
            "dob": dob.strip()
        }
        
        return self._make_request("POST", "driving-license", payload, api_type='driving_license', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_voter_id(self, voter_id: str, name: Optional[str] = None, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify Voter ID (EPIC number) using Cashfree VRS API
        
        Args:
            voter_id: EPIC number (Electoral Photo Identity Card number)
            name: Optional name to verify
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with status, epic_number, name, address, constituency details, etc.
        """
        if not verification_id:
            verification_id = self._generate_verification_id("voter")
        
        payload = {
            "verification_id": verification_id,
            "epic_number": voter_id.strip()
        }
        if name:
            payload["name"] = name.strip()
        
        return self._make_request("POST", "voter-id", payload, api_type='voter_id', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_passport(self, passport_number: str, dob: Optional[str] = None, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify Passport using Cashfree VRS API
        
        Note: Cashfree uses file_number, not passport_number directly
        
        Args:
            passport_number: Passport file number (not the passport number itself)
            dob: Date of birth (YYYY-MM-DD format) - REQUIRED
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with status, file_number, name, dob, etc.
        """
        if not verification_id:
            verification_id = self._generate_verification_id("passport")
        
        if not dob:
            raise ValueError("Date of birth (dob) is required for passport verification")
        
        payload = {
            "verification_id": verification_id,
            "file_number": passport_number.strip(),
            "dob": dob.strip()
        }
        
        return self._make_request("POST", "passport", payload, api_type='passport', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_gst(self, gstin: str, business_name: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify GSTIN using Cashfree VRS API
        
        Args:
            gstin: GST Identification Number (15 characters)
            business_name: Optional business name to verify
        
        Returns:
            Verification response dict with valid, GSTIN, legal_name_of_business, etc.
        """
        payload = {
            "GSTIN": gstin.upper().strip()
        }
        if business_name:
            payload["business_name"] = business_name.strip()[:200]  # Max 200 chars
        
        return self._make_request("POST", "gstin", payload, api_type='gst', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_cin(self, cin: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify CIN (Corporate Identification Number) using Cashfree VRS API
        
        Args:
            cin: CIN number (21 character alphanumeric)
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with status, cin, company_name, director_details, etc.
        """
        if not verification_id:
            verification_id = self._generate_verification_id("cin")
        
        payload = {
            "verification_id": verification_id,
            "cin": cin.upper().strip()
        }
        
        return self._make_request("POST", "cin", payload, api_type='cin', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_document(self, document_type: str, document_number: str, file_path: Optional[str] = None, **kwargs) -> Dict:
        """
        Generic document verification method
        
        Args:
            document_type: Document type (pan, aadhaar, driving_license, etc.)
            document_number: Document number
            file_path: Optional path to document file (for OCR-based verification)
            **kwargs: Additional parameters based on document type
        
        Returns:
            Verification response dict
        """
        document_type = document_type.lower()
        verification_id = kwargs.get("verification_id")
        
        if document_type == "pan":
            return self.verify_pan(document_number, kwargs.get("name"), verification_id)
        elif document_type == "aadhaar":
            return self.verify_aadhaar(document_number, kwargs.get("name"), verification_id)
        elif document_type in ["driving_license", "dl"]:
            return self.verify_driving_license(document_number, kwargs.get("dob"), verification_id)
        elif document_type == "voter_id":
            return self.verify_voter_id(document_number, kwargs.get("name"), verification_id)
        elif document_type == "passport":
            return self.verify_passport(document_number, kwargs.get("dob"), verification_id)
        elif document_type == "gst" or document_type == "gstin":
            return self.verify_gst(document_number, kwargs.get("business_name"))
        elif document_type == "cin":
            return self.verify_cin(document_number, verification_id)
        else:
            raise ValueError(f"Unsupported document type: {document_type}")
    
    # ============================================================================
    # BANK ACCOUNT VERIFICATION
    # ============================================================================
    
    def verify_bank_account(self, account_number: str, ifsc_code: str, name: Optional[str] = None, phone: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify bank account details using Cashfree VRS API V2 (Sync)
        
        Args:
            account_number: Bank account number (6-40 characters, alphanumeric)
            ifsc_code: IFSC code (11 characters, 5th char must be 0)
            name: Optional account holder name for name matching
            phone: Optional phone number associated with account (8-13 digits)
        
        Returns:
            Verification response dict with account_status, name_at_bank, bank_name, etc.
        """
        payload = {
            "bank_account": account_number.strip(),
            "ifsc": ifsc_code.upper().strip()
        }
        if name:
            payload["name"] = name.strip()[:100]  # Max 100 chars
        if phone:
            payload["phone"] = phone.strip()  # 8-13 digits
        
        return self._make_request("POST", "bank-account/sync", payload, api_type='bank', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # CONTACT VERIFICATION APIs
    # ============================================================================
    
    def verify_phone(self, phone_number: str, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify phone number
        
        Note: Phone/Email verification may not be direct APIs in Cashfree Secure ID.
        They might be part of Mobile 360 or other services. This is a placeholder.
        
        Args:
            phone_number: Phone number (with country code, e.g., +91XXXXXXXXXX)
        
        Returns:
            Verification response dict
        """
        # Note: Phone verification might be part of Mobile 360 API
        # This endpoint may not exist - needs verification
        payload = {
            "phone": phone_number.strip()
        }
        # Try phone endpoint - if it doesn't exist, this will need to be updated
        return self._make_request("POST", "phone", payload, api_type='phone', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_email(self, email: str, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify email address
        
        Note: Email verification may not be a direct API in Cashfree Secure ID.
        This is a placeholder implementation.
        
        Args:
            email: Email address to verify
        
        Returns:
            Verification response dict
        """
        # Note: Email verification endpoint may not exist in Cashfree Secure ID
        # This is a placeholder - may need to be removed or updated
        payload = {
            "email": email.strip()
        }
        # Try email endpoint - if it doesn't exist, this will need to be updated
        return self._make_request("POST", "email", payload, api_type='email', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # IFSC VERIFICATION
    # ============================================================================
    
    def verify_ifsc(self, ifsc_code: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify IFSC code using Cashfree VRS API V2
        
        Args:
            ifsc_code: IFSC code (11 characters, 5th char must be 0)
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with bank, branch, city, state, transfer modes, etc.
        """
        if not verification_id:
            verification_id = self._generate_verification_id("ifsc")
        
        payload = {
            "verification_id": verification_id,
            "ifsc": ifsc_code.upper().strip()
        }
        
        return self._make_request("POST", "ifsc", payload, api_type='ifsc', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # VEHICLE RC VERIFICATION
    # ============================================================================
    
    def verify_vehicle_rc(self, vehicle_number: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Verify Vehicle Registration Certificate using Cashfree VRS API
        
        Args:
            vehicle_number: Vehicle registration number (e.g., KA01MW8769)
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with status, reg_no, owner, chassis, engine, etc.
        """
        if not verification_id:
            verification_id = self._generate_verification_id("vrc")
        
        payload = {
            "verification_id": verification_id,
            "vehicle_number": vehicle_number.strip().upper()
        }
        
        return self._make_request("POST", "vehicle-rc", payload, api_type='vehicle_rc', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # BIOMETRIC KYC APIs
    # ============================================================================
    
    def verify_face_liveness(self, image_base64: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Face Liveness Check - Detect live human presence and prevent spoofing
        
        Args:
            image_base64: Base64 encoded image of face
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with liveness confidence score, quality metrics, etc.
        """
        if not verification_id:
            verification_id = self._generate_verification_id("face_live")
        
        payload = {
            "verification_id": verification_id,
            "image": image_base64
        }
        
        return self._make_request("POST", "face-liveness", payload, api_type='face_liveness', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_face_match(self, image1_base64: str, image2_base64: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Face Match - Compare facial features between two images
        
        Args:
            image1_base64: Base64 encoded first image
            image2_base64: Base64 encoded second image (or ID document image)
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with match score, match result, etc.
        """
        if not verification_id:
            verification_id = self._generate_verification_id("face_match")
        
        payload = {
            "verification_id": verification_id,
            "image1": image1_base64,
            "image2": image2_base64
        }
        
        return self._make_request("POST", "face-match", payload, api_type='face_match', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_name_match(self, name1: str, name2: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Name Match - Verify names with variations and fuzzy matching
        
        Args:
            name1: First name to compare
            name2: Second name to compare
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with match score, match result, reason, etc.
        """
        if not verification_id:
            verification_id = self._generate_verification_id("name_match")
        
        payload = {
            "verification_id": verification_id,
            "name1": name1.strip(),
            "name2": name2.strip()
        }
        
        return self._make_request("POST", "name-match", payload, api_type='name_match', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # SMART OCR
    # ============================================================================
    
    def smart_ocr(self, document_type: str, image_base64: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Smart OCR - Extract and verify data from documents using OCR
        
        Supported document types:
        - PAN, Aadhaar, Driving License, Passport, Voter ID, Vehicle RC, 
          Cancelled Cheque, Invoice
        
        Args:
            document_type: Document type (pan, aadhaar, driving_license, passport, 
                          voter_id, vehicle_rc, cancelled_cheque, invoice)
            image_base64: Base64 encoded document image
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with extracted document data
        """
        if not verification_id:
            verification_id = self._generate_verification_id("ocr")
        
        # Map document types to Cashfree format
        doc_type_map = {
            "pan": "PAN",
            "aadhaar": "AADHAAR",
            "driving_license": "DRIVING_LICENSE",
            "driving_licence": "DRIVING_LICENSE",
            "dl": "DRIVING_LICENSE",
            "passport": "PASSPORT",
            "voter_id": "VOTER_ID",
            "vehicle_rc": "VEHICLE_RC",
            "cancelled_cheque": "CANCELLED_CHEQUE",
            "invoice": "INVOICE"
        }
        
        doc_type = doc_type_map.get(document_type.lower(), document_type.upper())
        
        payload = {
            "verification_id": verification_id,
            "document_type": doc_type,
            "image": image_base64
        }
        
        return self._make_request("POST", "smart-ocr", payload, api_type='smart_ocr', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # ADVANCED AADHAAR APIs
    # ============================================================================
    
    def verify_aadhaar_ocr(self, image_base64: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Aadhaar OCR - Extract data from Aadhaar card image using OCR
        
        Args:
            image_base64: Base64 encoded Aadhaar card image
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with extracted Aadhaar data
        """
        if not verification_id:
            verification_id = self._generate_verification_id("aadhaar_ocr")
        
        payload = {
            "verification_id": verification_id,
            "image": image_base64
        }
        
        return self._make_request("POST", "aadhaar/ocr", payload, api_type='aadhaar_ocr', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_aadhaar_masking(self, aadhaar_number: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Aadhaar Masking - Mask Aadhaar number for privacy
        
        Args:
            aadhaar_number: Aadhaar number (12 digits)
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with masked Aadhaar
        """
        if not verification_id:
            verification_id = self._generate_verification_id("aadhaar_mask")
        
        payload = {
            "verification_id": verification_id,
            "aadhaar_number": aadhaar_number.strip()
        }
        
        return self._make_request("POST", "aadhaar/masking", payload, api_type='aadhaar_masking', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def offline_aadhaar_send_otp(self, aadhaar_number: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Offline Aadhaar - Send OTP to registered mobile number
        
        Args:
            aadhaar_number: Aadhaar number (12 digits)
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Response dict with OTP sent status
        """
        if not verification_id:
            verification_id = self._generate_verification_id("offline_aadhaar")
        
        payload = {
            "verification_id": verification_id,
            "aadhaar_number": aadhaar_number.strip()
        }
        
        return self._make_request("POST", "offline-aadhaar/send-otp", payload, api_type='offline_aadhaar_send_otp', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def offline_aadhaar_verify_otp(self, otp: str, verification_id: str, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Offline Aadhaar - Verify OTP and get Aadhaar details
        
        Args:
            otp: OTP received on registered mobile
            verification_id: Verification ID from send_otp response
        
        Returns:
            Verification response dict with Aadhaar details
        """
        payload = {
            "verification_id": verification_id,
            "otp": otp.strip()
        }
        
        return self._make_request("POST", "offline-aadhaar/verify-otp", payload, api_type='offline_aadhaar_verify_otp', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # ADVANCED PAN APIs
    # ============================================================================
    
    def verify_pan_advance(self, pan_number: str, name: Optional[str] = None, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        PAN Advance - Get detailed PAN information including address
        
        Args:
            pan_number: PAN card number (10 characters)
            name: Optional name to verify
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with detailed PAN information including address
        """
        if not verification_id:
            verification_id = self._generate_verification_id("pan_advance")
        
        payload = {
            "verification_id": verification_id,
            "pan": pan_number.upper().strip()
        }
        if name:
            payload["name"] = name.strip()
        
        return self._make_request("POST", "pan/advance", payload, api_type='pan_advance', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_pan_ocr(self, image_base64: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        PAN OCR - Extract data from PAN card image using OCR
        
        Args:
            image_base64: Base64 encoded PAN card image
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with extracted PAN data
        """
        if not verification_id:
            verification_id = self._generate_verification_id("pan_ocr")
        
        payload = {
            "verification_id": verification_id,
            "image": image_base64
        }
        
        return self._make_request("POST", "pan/ocr", payload, api_type='pan_ocr', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_pan_to_gstin(self, pan_number: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        PAN to GSTIN - Get all GSTINs associated with a PAN
        
        Args:
            pan_number: PAN card number (10 characters)
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with list of GSTINs associated with PAN
        """
        if not verification_id:
            verification_id = self._generate_verification_id("pan_gstin")
        
        payload = {
            "verification_id": verification_id,
            "pan": pan_number.upper().strip()
        }
        
        return self._make_request("POST", "pan-to-gstin", payload, api_type='pan_to_gstin', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_pan_bulk(self, pan_entries: list, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Bulk PAN Verification - Verify multiple PANs in a single request
        
        Args:
            pan_entries: List of dicts with 'pan' and optional 'name' keys
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with results for all PANs
        """
        if not verification_id:
            verification_id = self._generate_verification_id("pan_bulk")
        
        entries = []
        for entry in pan_entries:
            pan_entry = {"pan": entry.get('pan', '').upper().strip()}
            if entry.get('name'):
                pan_entry["name"] = entry.get('name').strip()
            entries.append(pan_entry)
        
        payload = {
            "verification_id": verification_id,
            "entries": entries
        }
        
        return self._make_request("POST", "pan/bulk", payload, api_type='pan_bulk', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # DIGILOCKER APIs
    # ============================================================================
    
    def digilocker_create_url(self, redirect_url: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        DigiLocker - Create URL for user to authenticate and share documents
        
        Args:
            redirect_url: URL to redirect after DigiLocker authentication
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Response dict with DigiLocker authentication URL
        """
        if not verification_id:
            verification_id = self._generate_verification_id("digilocker")
        
        payload = {
            "verification_id": verification_id,
            "redirect_url": redirect_url
        }
        
        return self._make_request("POST", "digilocker/verification/create-url", payload, api_type='digilocker_create_url', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def digilocker_get_status(self, verification_id: str, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        DigiLocker - Get verification status
        
        Args:
            verification_id: Verification ID from create_url response
        
        Returns:
            Response dict with verification status and document details
        """
        return self._make_request("GET", f"digilocker/verification/get-status/{verification_id}", None, api_type='digilocker_get_status', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def digilocker_get_document(self, verification_id: str, document_type: str, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        DigiLocker - Get specific document from DigiLocker
        
        Args:
            verification_id: Verification ID from create_url response
            document_type: Document type (aadhaar, driving_license, etc.)
        
        Returns:
            Response dict with document details
        """
        return self._make_request("GET", f"digilocker/verification/get-document/{verification_id}/{document_type}", None, api_type='digilocker_get_document', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # E-SIGN APIs
    # ============================================================================
    
    def esign_create_signature(self, document_base64: str, signers: list, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        E-sign - Create signature request for document
        
        Args:
            document_base64: Base64 encoded document to sign
            signers: List of signer dicts with 'name', 'email', 'phone', 'sign_positions'
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Response dict with signature request details
        """
        if not verification_id:
            verification_id = self._generate_verification_id("esign")
        
        payload = {
            "verification_id": verification_id,
            "document": document_base64,
            "signers": signers
        }
        
        return self._make_request("POST", "e-sign/verification/create-signature", payload, api_type='esign_create_signature', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def esign_get_status(self, verification_id: str, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        E-sign - Get signature status
        
        Args:
            verification_id: Verification ID from create_signature response
        
        Returns:
            Response dict with signature status
        """
        return self._make_request("GET", f"e-sign/verification/get-status/{verification_id}", None, api_type='esign_get_status', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def esign_upload_document(self, document_base64: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        E-sign - Upload document for signing
        
        Args:
            document_base64: Base64 encoded document
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Response dict with uploaded document details
        """
        if not verification_id:
            verification_id = self._generate_verification_id("esign_upload")
        
        payload = {
            "verification_id": verification_id,
            "document": document_base64
        }
        
        return self._make_request("POST", "e-sign/verification/upload-document", payload, api_type='esign_upload_document', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # ADVANCED VERIFICATION APIs
    # ============================================================================
    
    def verify_advance_employment(self, uan: Optional[str] = None, pan: Optional[str] = None, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Advance Employment - Get employment details from EPFO/UAN
        
        Args:
            uan: UAN (Universal Account Number) - 12 digits
            pan: PAN number (alternative to UAN)
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with employment details
        """
        if not verification_id:
            verification_id = self._generate_verification_id("employment")
        
        payload = {
            "verification_id": verification_id
        }
        if uan:
            payload["uan"] = uan.strip()
        if pan:
            payload["pan"] = pan.upper().strip()
        
        return self._make_request("POST", "advance-employment", payload, api_type='advance_employment', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_reverse_penny_drop(self, account_number: str, ifsc_code: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Reverse Penny Drop - Verify bank account by depositing small amount
        
        Args:
            account_number: Bank account number
            ifsc_code: IFSC code
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Verification response dict with transaction status
        """
        if not verification_id:
            verification_id = self._generate_verification_id("rpd")
        
        payload = {
            "verification_id": verification_id,
            "bank_account": account_number.strip(),
            "ifsc": ifsc_code.upper().strip()
        }
        
        return self._make_request("POST", "reverse-penny-drop", payload, api_type='reverse_penny_drop', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def get_reverse_penny_drop_status(self, verification_id: str, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Reverse Penny Drop - Get transaction status
        
        Args:
            verification_id: Verification ID from reverse_penny_drop response
        
        Returns:
            Response dict with transaction status
        """
        return self._make_request("GET", f"reverse-penny-drop/{verification_id}", None, api_type='reverse_penny_drop_status', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_reverse_geocoding(self, latitude: float, longitude: float, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Reverse Geocoding - Get address from coordinates
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Response dict with address details
        """
        if not verification_id:
            verification_id = self._generate_verification_id("geocode")
        
        payload = {
            "verification_id": verification_id,
            "latitude": latitude,
            "longitude": longitude
        }
        
        return self._make_request("POST", "reverse-geocoding", payload, api_type='reverse_geocoding', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    def verify_ip_address(self, ip_address: str, verification_id: Optional[str] = None, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        IP Verification - Verify IP address location and details
        
        Args:
            ip_address: IP address to verify (IPv4)
            verification_id: Optional verification ID (auto-generated if not provided)
        
        Returns:
            Response dict with IP address details and location
        """
        if not verification_id:
            verification_id = self._generate_verification_id("ip")
        
        payload = {
            "verification_id": verification_id,
            "ip": ip_address.strip()
        }
        
        return self._make_request("POST", "ip-verification", payload, api_type='ip_verification', user_id=user_id, request_id=request_id, client_ip=client_ip, user_agent=user_agent)
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def test_connection(self, user_id: Optional[int] = None, request_id: Optional[str] = None, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> Dict:
        """
        Test API connection by making a simple API call
        
        Args:
            user_id: User ID making the request (for logging)
            request_id: Request ID for tracing
            client_ip: Client IP address
            user_agent: User agent string
        
        Returns:
            Connection test response
        """
        try:
            # Check if credentials are configured
            if not self.api_key or not self.api_secret:
                return {
                    "status": "error",
                    "message": "API credentials not configured",
                    "api_key_configured": False,
                    "base_url": self.base_url
                }
            
            # Test connection by making a simple PAN verification call
            # This will test both authentication and API connectivity
            try:
                test_result = self.verify_pan(
                    pan_number="ABCDE1234F",  # Test PAN (will likely fail but tests connection)
                    user_id=user_id,
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent
                )
                
                # If we get a response (even if invalid), connection is working
                return {
                    "status": "success",
                    "message": "Connection successful - API is responding",
                    "api_key_configured": True,
                    "base_url": self.base_url,
                    "api_version": self.api_version,
                    "test_response": test_result
                }
            except Exception as api_error:
                # Even if API call fails, we tested the connection
                error_msg = str(api_error)
                # If it's an authentication error, credentials might be wrong
                # If it's a validation error, connection is working
                if "authentication" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
                    return {
                        "status": "error",
                        "message": f"Connection established but authentication failed: {error_msg}",
                        "api_key_configured": True,
                        "base_url": self.base_url,
                        "api_version": self.api_version
                    }
                else:
                    # Connection works, just validation/API error
                    return {
                        "status": "success",
                        "message": f"Connection successful - API responded (validation error expected): {error_msg[:100]}",
                        "api_key_configured": True,
                        "base_url": self.base_url,
                        "api_version": self.api_version
                    }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Connection test failed: {str(e)}",
                "api_key_configured": bool(self.api_key),
                "base_url": self.base_url
            }
