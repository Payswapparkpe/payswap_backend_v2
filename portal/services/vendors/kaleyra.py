"""
Kaleyra SMS API client for India
Based on official Kaleyra API documentation:
- Endpoint: POST https://api.kaleyra.io/v1/messages
- Authentication: api-key header
- Format: JSON payload with to, sender, type, body, template_id
"""
import httpx
from typing import Optional, List
from core.config import payswap_config
from portal.utils.phone_utils import format_phone_for_kaleyra, normalize_phone_number


class KaleyraClient:
    """Kaleyra SMS API client for India region"""
    
    def __init__(self):
        self.api_key = payswap_config.get_kaleyra_api_key()
        self.sid = payswap_config.KALEYRA_SID
        # Sender ID/Header - Use PYSWAP (not SID) as the sender name in SMS
        # SID is only used for account identification, not as sender
        self.sender_id = payswap_config.KALEYRA_HEADER_PAYSWAP or 'PYSWAP'
        # OTP Template ID (mandatory for India - DLT compliance)
        self.otp_template_id = payswap_config.KALEYRA_OTP_TEMPLATE_ID
        # Kaleyra API endpoint - Use base URL from .env
        # Base URL from .env: https://api.in.kaleyra.io/ (or api.in.kaleyra.io)
        # Full endpoint should be: https://api.in.kaleyra.io/v1/{SID}/sms
        base_url_from_config = payswap_config.KALEYRA_BASE_URL
        
        # Normalize base URL
        if not base_url_from_config or base_url_from_config == "":
            # Default if not set
            base_url_from_config = "https://api.in.kaleyra.io"
        elif not base_url_from_config.startswith('http'):
            # Add https:// if protocol missing
            base_url_from_config = f"https://{base_url_from_config}"
        
        # Remove trailing slash
        base_url_from_config = base_url_from_config.rstrip('/')
        
        # Construct full base URL with /v1/{SID}
        # Format: https://api.in.kaleyra.io/v1/{SID}
        self.base_url = f"{base_url_from_config}/v1/{self.sid}"
    
    def send_sms(
        self, 
        to: str, 
        message: str, 
        message_type: str = "TXN",
        sender: Optional[str] = None,
        template_id: Optional[str] = None
    ) -> dict:
        """
        Send SMS via Kaleyra API (India)
        
        Args:
            to: Phone number (will be normalized to +91XXXXXXXXXX format)
            message: SMS message content
            message_type: Message type - "TXN" for transactional, "MKT" for marketing (default: "TXN")
            sender: Sender ID/Header (defaults to PYSWAP, not SID)
        
        Returns:
            API response dict
        
        Raises:
            ValueError: If phone number is invalid
            Exception: If API call fails
        """
        # Normalize phone number to 91XXXXXXXXXX format (no + prefix)
        try:
            # Normalize to 91XXXXXXXXXX format (no +)
            normalized = normalize_phone_number(to)
            # Kaleyra API requires format: 91XXXXXXXXXX (without + prefix)
            normalized_phone = normalized.lstrip('+') if normalized.startswith('+') else normalized
        except ValueError as e:
            raise ValueError(f"Invalid phone number format: {str(e)}")
        
        # Use PYSWAP as sender ID (header) - not SID
        # SID is only used for account identification, not as sender
        sender_id = sender or self.sender_id
        
        # Kaleyra API endpoint: POST /sms (India-specific with SID)
        url = f"{self.base_url}/sms"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Request body according to Kaleyra API documentation
        data = {
            "to": normalized_phone,  # Format: 91XXXXXXXXXX (no + prefix)
            "sender": sender_id,  # Approved sender ID
            "type": message_type,  # TXN for transactional, PROMO for promotional
            "body": message  # SMS content
        }
        
        # Add template_id if provided (mandatory for India - DLT compliance)
        if template_id:
            data["template_id"] = template_id
        
        # TEMPORARY: Full details for debugging - no masking
        from portal.utils.logging_utils import SecureLogger
        from portal.tasks.write_logs_task import write_logs_task
        logger = SecureLogger('portal.services.vendors.kaleyra')
        
        request_log_data = {
                'action': 'kaleyra_sms_request',
                'url': url,
                'method': 'POST',
                'headers': {
                    'api-key': str(self.api_key),  # Full API key for debugging
                    'Content-Type': headers.get('Content-Type')
                },
                'payload': data,  # Complete payload
                'payload_full': {
                    'to': normalized_phone,  # Full phone number
                    'sender': sender_id,
                    'type': message_type,
                    'body': message,  # Full message
                    'template_id': template_id
                },
                'sender_id': sender_id,
                'phone_full': normalized_phone,  # Full phone number
                'phone_normalized': normalized_phone,
                'message_full': message,  # Full message content
                'message_length': len(message),
                'message_type': message_type,
                'template_id': template_id,
                'base_url': self.base_url,
                'sid': self.sid
            }
        
        logger.info(
            f'Kaleyra SMS Request - POST {url} | Phone: {normalized_phone} | Sender: {sender_id} | Message: {message[:50]}...',
            user=None,
            extra_data=request_log_data
        )
        
        write_logs_task.delay(
            log_level='INFO',
            message=f'Kaleyra SMS Request - POST {url} | Phone: {normalized_phone} | Sender: {sender_id} | Type: {message_type} | Message: {message}',
            module_name='portal.services.vendors.kaleyra',
            url=None,
            request_id=None,
            response_id=None,
            user_id=None,
            extra_data=request_log_data,
            client_ip=None,
            user_agent=None,
            session_id=None
        )
        
        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=headers, timeout=10)
                response_status = response.status_code
                
                # Log response
                try:
                    result = response.json()
                    response_body = result
                    response_text = None
                except:
                    result = {}
                    response_body = None
                    response_text = response.text
                
                response_log_data = {
                    'action': 'kaleyra_sms_response',
                    'status_code': response_status,
                    'response_headers': dict(response.headers),
                    'response_body': response_body,
                    'response_text': response_text if response_text else None,  # Full response text
                    'success': response_status == 200,
                    'request_url': url,
                    'request_payload': data
                }
                
                if response_status == 200:
                    logger.info(
                        f'Kaleyra SMS Response - Success | Status: {response_status} | Response: {result}',
                        user=None,
                        extra_data=response_log_data
                    )
                else:
                    logger.warning(
                        f'Kaleyra SMS Response - Error | Status: {response_status} | Response: {result if result else response_text}',
                        user=None,
                        extra_data=response_log_data
                    )
                
                write_logs_task.delay(
                    log_level='INFO' if response_status == 200 else 'WARNING',
                    message=f'Kaleyra SMS Response - Status: {response_status} | Phone: {normalized_phone} | Response: {str(result) if result else response_text if response_text else "No response"}',
                    module_name='portal.services.vendors.kaleyra',
                    url=None,
                    request_id=None,
                    response_id=None,
                    user_id=None,
                    extra_data=response_log_data,
                    client_ip=None,
                    user_agent=None,
                    session_id=None
                )
                
                response.raise_for_status()
                return result
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            
            # Log error
            error_log_data = {
                'action': 'kaleyra_sms_error',
                'status_code': e.response.status_code,
                'error': error_detail,
                'response_text': e.response.text if hasattr(e.response, 'text') else None,  # Full error response
                'request_url': url,
                'request_payload': data
            }
            
            logger.error(
                f'Kaleyra SMS Error - Status: {e.response.status_code} | Error: {error_detail}',
                user=None,
                extra_data=error_log_data,
                traceback=str(e)
            )
            
            write_logs_task.delay(
                log_level='ERROR',
                message=f'Kaleyra SMS Error - Status: {e.response.status_code} | Error: {error_detail}',
                module_name='portal.services.vendors.kaleyra',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data=error_log_data,
                client_ip=None,
                user_agent=None,
                session_id=None,
                traceback=str(e)
            )
            
            raise Exception(f"Kaleyra API error: {error_detail}")
        except Exception as e:
            # Log exception
            error_log_data = {
                'action': 'kaleyra_sms_exception',
                'error': str(e),
                'request_url': url,
                'request_payload': data
            }
            
            logger.error(
                f'Kaleyra SMS Exception: {str(e)}',
                user=None,
                extra_data=error_log_data,
                traceback=str(e)
            )
            
            write_logs_task.delay(
                log_level='ERROR',
                message=f'Kaleyra SMS Exception: {str(e)}',
                module_name='portal.services.vendors.kaleyra',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data=error_log_data,
                client_ip=None,
                user_agent=None,
                session_id=None,
                traceback=str(e)
            )
            
            raise Exception(f"Kaleyra API error: {str(e)}")
    
    def send_otp(self, phone_number: str, otp: str) -> bool:
        """
        Send OTP via SMS using template ID with variables
        
        According to Kaleyra API docs:
        - Endpoint: POST https://api.kaleyra.io/v1/messages
        - type: "OTP" (not "TXN")
        - Use variables: {"var1": "otp_code"} (not body field)
        - Template uses {#var#} which maps to var1
        
        Args:
            phone_number: Phone number (will be normalized to 91XXXXXXXXXX)
            otp: OTP code
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Normalize phone number to 91XXXXXXXXXX format (no + prefix)
            normalized = normalize_phone_number(phone_number)
            # Kaleyra API requires format: 91XXXXXXXXXX (without + prefix)
            normalized_phone = normalized.lstrip('+') if normalized.startswith('+') else normalized
            
            # Kaleyra API endpoint: Use /messages for template-based OTP (JSON API)
            # Correct format: https://api.in.kaleyra.io/v1/{SID}/messages
            # This is the recommended endpoint for template-based OTP with variables
            url = f"{self.base_url}/messages"
            headers = {
                "api-key": str(self.api_key),
                "Content-Type": "application/json"
            }
            
            # Request body according to Kaleyra API documentation for template-based OTP
            # DLT template_id: 1007640321725099860 | Header: PYSWAP
            # Template: "Dear User, Your one time password for Payswap registration is {#var#}. Please do not share this OTP any one. Powered by PAYSWAP."
            template_body = f"Dear User, Your one time password for Payswap registration is {otp}. Please do not share this OTP any one. Powered by PAYSWAP."
            
            data = {
                "to": normalized_phone,  # Format: 91XXXXXXXXXX (no + prefix)
                "sender": self.sender_id,  # PYSWAP (approved sender ID / header)
                "type": "OTP",  # OTP type (not TXN)
                "template_id": self.otp_template_id,  # DLT template ID (mandatory for India)
                "body": template_body,  # MANDATORY: Exact template text with OTP injected
                "variables": {
                    "var1": otp  # Template uses {#var#} which maps to var1
                }
            }
            
            # TEMPORARY: Full details for debugging - no masking
            from portal.tasks.write_logs_task import write_logs_task
            
            # Log complete request details - NO MASKING
            request_log_data = {
                'action': 'kaleyra_otp_request',
                'url': url,
                'method': 'POST',
                'headers': {
                    'api-key': str(self.api_key),  # Full API key
                    'Content-Type': headers.get('Content-Type')
                },
                'payload': data,  # Complete payload
                'payload_full': {
                    'to': normalized_phone,  # Full phone number
                    'sender': self.sender_id,
                    'type': 'OTP',  # OTP type
                    'template_id': self.otp_template_id,
                    'body': template_body,  # Full template text with OTP
                    'variables': {'var1': otp}  # Template variable
                },
                'template_id': self.otp_template_id,
                'sender_id': self.sender_id,
                'phone_full': normalized_phone,  # Full phone number
                'phone_normalized': normalized_phone,
                'otp_code': otp,  # Full OTP code
                'variable_name': 'var1',  # Template variable name
                'base_url': self.base_url
            }
            
            # Log via write_logs_task for database storage - FULL DETAILS
            write_logs_task.delay(
                log_level='INFO',
                message=f'Kaleyra OTP SMS Request - POST {url} | Phone: {normalized_phone} | OTP: {otp} | Template: {self.otp_template_id} | Sender: {self.sender_id} | Type: OTP | Variable: var1={otp}',
                module_name='portal.services.vendors.kaleyra',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data=request_log_data,
                client_ip=None,
                user_agent=None,
                session_id=None
            )
            
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=headers, timeout=10)
                
                # Log complete response
                response_status = response.status_code
                try:
                    result = response.json()
                    response_body = result
                    response_text = None
                    # Extract message_id from response (important for DLR tracking)
                    message_id = result.get('id') if isinstance(result, dict) else None
                except:
                    result = {}
                    response_body = None
                    response_text = response.text
                    message_id = None
                
                # Determine success before logging (202 is also success)
                is_success = response_status in [200, 202]
                if isinstance(result, dict):
                    # Additional checks for success
                    if 'id' in result or 'message_id' in result:
                        is_success = True
                    if 'data' in result and isinstance(result.get('data'), list):
                        if len(result.get('data', [])) > 0:
                            is_success = True
                
                # Log response details
                response_log_data = {
                    'action': 'kaleyra_otp_response',
                    'status_code': response_status,
                    'response_headers': dict(response.headers),  # All headers
                    'response_body': response_body,  # Complete JSON response
                    'response_text': response_text if response_text else None,  # Full response text
                    'message_id': message_id,  # Important: Save this for DLR tracking
                    'success': is_success,  # 200 or 202 means success
                    'request_url': url,
                    'request_payload': data,  # Complete request payload
                    'otp_code': otp,  # Full OTP code
                    'phone_full': normalized_phone  # Full phone number
                }
                
                # Response logging is done via write_logs_task below
                
                # Also log via write_logs_task for database storage - FULL DETAILS
                response_msg = f'Kaleyra OTP SMS Response - Status: {response_status} | Phone: {normalized_phone} | OTP: {otp}'
                if message_id:
                    response_msg += f' | Message ID: {message_id}'
                response_msg += f' | Response: {str(result) if result else response_text if response_text else "No response"}'
                
                # 200 or 202 means success
                log_level = 'INFO' if is_success else 'WARNING'
                write_logs_task.delay(
                    log_level=log_level,
                    message=response_msg,
                    module_name='portal.services.vendors.kaleyra',
                    url=None,
                    request_id=None,
                    response_id=None,
                    user_id=None,
                    extra_data=response_log_data,
                    client_ip=None,
                    user_agent=None,
                    session_id=None
                )
                
                # Don't raise for status - check manually
                # 202 Accepted means message was queued successfully
                # 200 OK also means success
                
                # Check for success indicators (use is_success from above)
                success = is_success
                
                # Final result logging is done via write_logs_task above
                
                return success
        except httpx.HTTPStatusError as e:
            # Log HTTP errors with complete details
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            
            # Get url and data from exception context or use defaults
            request_url = getattr(e, 'request', {}).url if hasattr(e, 'request') else (url if 'url' in locals() else 'unknown')
            request_payload = data if 'data' in locals() else {}
            
            error_log_data = {
                'action': 'kaleyra_otp_error',
                'status_code': e.response.status_code,
                'error': error_detail,
                'response_headers': dict(e.response.headers) if hasattr(e.response, 'headers') else None,
                'response_text': e.response.text if hasattr(e.response, 'text') else None,  # Full error response
                'request_url': request_url,
                'request_payload': request_payload
            }
            
            # Log error via write_logs_task
            error_log_data['traceback'] = str(e)
            write_logs_task.delay(
                log_level='ERROR',
                message=f'Kaleyra OTP SMS Error - Status: {e.response.status_code} | Error: {error_detail}',
                module_name='portal.services.vendors.kaleyra',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data=error_log_data,
                client_ip=None,
                user_agent=None,
                session_id=None
            )
            
            return False
        except Exception as e:
            # Log all other errors with complete details
            # Get url and data from local context or use defaults
            request_url = url if 'url' in locals() else 'unknown'
            request_payload = data if 'data' in locals() else {}
            
            error_log_data = {
                'action': 'kaleyra_otp_exception',
                'error': str(e),
                'exception_type': type(e).__name__,
                'request_url': request_url,
                'request_payload': request_payload
            }
            
            # Log exception via write_logs_task
            error_log_data['traceback'] = str(e)
            write_logs_task.delay(
                log_level='ERROR',
                message=f'Kaleyra OTP SMS Exception: {str(e)}',
                module_name='portal.services.vendors.kaleyra',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data=error_log_data,
                client_ip=None,
                user_agent=None,
                session_id=None
            )
            
            return False
    
    def send_template_sms(
        self,
        phone_number: str,
        template_id: str,
        template_content: str,
        variables: List[str],
        message_type: str = "TXN"
    ) -> dict:
        """
        Send SMS using DLT template with variables
        
        Args:
            phone_number: Phone number (will be normalized to 91XXXXXXXXXX)
            template_id: DLT Template ID
            template_content: Template content with {#var#} placeholders
            variables: List of variable values to replace {#var#} in order
            message_type: Message type - "TXN" for transactional, "OTP" for OTP (default: "TXN")
        
        Returns:
            API response dict
        """
        try:
            # Normalize phone number to 91XXXXXXXXXX format (no + prefix)
            normalized = normalize_phone_number(phone_number)
            normalized_phone = normalized
            
            # Kaleyra API endpoint
            url = f"{self.base_url}/messages"
            headers = {
                "api-key": str(self.api_key),
                "Content-Type": "application/json"
            }
            
            # Build template body by replacing {#var#} with actual values
            template_body = template_content
            var_dict = {}
            for i, var_value in enumerate(variables, start=1):
                var_key = f"var{i}"
                var_dict[var_key] = var_value
                # Replace first occurrence of {#var#} with the value
                template_body = template_body.replace('{#var#}', var_value, 1)
            
            # If there are remaining {#var#} placeholders, replace with empty or last value
            while '{#var#}' in template_body:
                template_body = template_body.replace('{#var#}', variables[-1] if variables else '', 1)
            
            data = {
                "to": normalized_phone,
                "sender": self.sender_id,
                "type": message_type,
                "template_id": template_id,
                "body": template_body,
                "variables": var_dict
            }
            
            # Logging
            from portal.utils.logging_utils import SecureLogger
            from portal.tasks.write_logs_task import write_logs_task
            logger = SecureLogger('portal.services.vendors.kaleyra')
            
            request_log_data = {
                'action': 'kaleyra_template_sms_request',
                'url': url,
                'method': 'POST',
                'headers': {
                    'api-key': str(self.api_key),
                    'Content-Type': headers.get('Content-Type')
                },
                'payload': data,
                'template_id': template_id,
                'template_content': template_content,
                'variables': variables,
                'phone_full': normalized_phone,
                'message_type': message_type
            }
            
            logger.info(
                f'Kaleyra Template SMS Request - POST {url} | Phone: {normalized_phone} | Template: {template_id}',
                user=None,
                extra_data=request_log_data
            )
            
            write_logs_task.delay(
                log_level='INFO',
                message=f'Kaleyra Template SMS Request - POST {url} | Phone: {normalized_phone} | Template: {template_id} | Variables: {variables}',
                module_name='portal.services.vendors.kaleyra',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data=request_log_data,
                client_ip=None,
                user_agent=None,
                session_id=None
            )
            
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=headers, timeout=10)
                response_status = response.status_code
                
                # Log response
                try:
                    result = response.json()
                    response_body = result
                    response_text = None
                    message_id = result.get('id') if isinstance(result, dict) else None
                except:
                    result = {}
                    response_body = None
                    response_text = response.text
                    message_id = None
                
                is_success = response_status in [200, 202]
                if isinstance(result, dict):
                    if 'id' in result or 'message_id' in result:
                        is_success = True
                    if 'data' in result and isinstance(result.get('data'), list):
                        if len(result.get('data', [])) > 0:
                            is_success = True
                
                response_log_data = {
                    'action': 'kaleyra_template_sms_response',
                    'status_code': response_status,
                    'response_headers': dict(response.headers),
                    'response_body': response_body,
                    'response_text': response_text if response_text else None,
                    'message_id': message_id,
                    'success': is_success,
                    'request_url': url,
                    'request_payload': data,
                    'template_id': template_id
                }
                
                if is_success:
                    logger.info(
                        f'Kaleyra Template SMS Response - Success | Status: {response_status} | Template: {template_id} | Message ID: {message_id}',
                        user=None,
                        extra_data=response_log_data
                    )
                else:
                    logger.warning(
                        f'Kaleyra Template SMS Response - Error | Status: {response_status} | Template: {template_id} | Response: {result if result else response_text}',
                        user=None,
                        extra_data=response_log_data
                    )
                
                write_logs_task.delay(
                    log_level='INFO' if is_success else 'WARNING',
                    message=f'Kaleyra Template SMS Response - Status: {response_status} | Phone: {normalized_phone} | Template: {template_id} | Message ID: {message_id} | Response: {str(result) if result else response_text if response_text else "No response"}',
                    module_name='portal.services.vendors.kaleyra',
                    url=None,
                    request_id=None,
                    response_id=None,
                    user_id=None,
                    extra_data=response_log_data,
                    client_ip=None,
                    user_agent=None,
                    session_id=None
                )
                
                response.raise_for_status()
                return result
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            
            error_log_data = {
                'action': 'kaleyra_template_sms_error',
                'status_code': e.response.status_code,
                'error': error_detail,
                'response_text': e.response.text if hasattr(e.response, 'text') else None,
                'request_url': url if 'url' in locals() else 'unknown',
                'request_payload': data if 'data' in locals() else {},
                'template_id': template_id if 'template_id' in locals() else None
            }
            
            logger.error(
                f'Kaleyra Template SMS Error - Status: {e.response.status_code} | Error: {error_detail}',
                user=None,
                extra_data=error_log_data,
                traceback=str(e)
            )
            
            write_logs_task.delay(
                log_level='ERROR',
                message=f'Kaleyra Template SMS Error - Status: {e.response.status_code} | Error: {error_detail}',
                module_name='portal.services.vendors.kaleyra',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data=error_log_data,
                client_ip=None,
                user_agent=None,
                session_id=None,
                traceback=str(e)
            )
            
            raise Exception(f"Kaleyra Template SMS API error: {error_detail}")
        except Exception as e:
            error_log_data = {
                'action': 'kaleyra_template_sms_exception',
                'error': str(e),
                'request_url': url if 'url' in locals() else 'unknown',
                'request_payload': data if 'data' in locals() else {},
                'template_id': template_id if 'template_id' in locals() else None
            }
            
            logger.error(
                f'Kaleyra Template SMS Exception: {str(e)}',
                user=None,
                extra_data=error_log_data,
                traceback=str(e)
            )
            
            write_logs_task.delay(
                log_level='ERROR',
                message=f'Kaleyra Template SMS Exception: {str(e)}',
                module_name='portal.services.vendors.kaleyra',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data=error_log_data,
                client_ip=None,
                user_agent=None,
                session_id=None,
                traceback=str(e)
            )
            
            raise Exception(f"Kaleyra Template SMS API error: {str(e)}")

    def click_to_call(
        self,
        from_number: str,
        to_number: str,
        bridge_number: Optional[str] = None,
    ) -> dict:
        """
        Initiate a masked click-to-call: 'from' is called first, then 'to'; both connect via bridge.
        Kaleyra API: POST /v1/<SID>/voice/click-to-call (application/x-www-form-urlencoded).
        """
        try:
            from_norm = normalize_phone_number(from_number).lstrip('+')
            to_norm = normalize_phone_number(to_number).lstrip('+')
        except ValueError as e:
            raise ValueError(f"Invalid phone number: {e}") from e

        url = f"{self.base_url}/voice/click-to-call"
        headers = {
            "api-key": str(self.api_key),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"from": from_norm, "to": to_norm}
        if bridge_number:
            data["bridge"] = normalize_phone_number(bridge_number).lstrip('+')

        with httpx.Client() as client:
            response = client.post(url, data=data, headers=headers, timeout=15)
            result = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            response.raise_for_status()
            return result
