"""
OTP Service using unified notification service with Celery
Supports dual delivery (email + SMS) for signup
"""
import random
import secrets
import string
from typing import Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from portal.services.notification_service_v2 import NotificationServiceV2
from portal.utils.mfa_utils import store_otp_in_cache, verify_otp_from_cache
from portal.utils.phone_utils import normalize_phone_number
from portal.utils.logging_helper import get_logger
from portal.tasks.otp_dual_delivery_task import send_otp_dual_delivery_task

logger = get_logger('portal.services.otp')


class OTPService:
    """OTP service for SMS OTP using unified notification service"""
    
    def __init__(self):
        self.notification_service = NotificationServiceV2()
        self.otp_length = 6
        self.otp_expiry = 300  # 5 minutes
    
    def generate_otp(self) -> str:
        """
        Generate random OTP using secure secrets module
        
        Returns:
            6-digit OTP string
        """
        return ''.join([str(secrets.randbelow(10)) for _ in range(self.otp_length)])
    
    def send_otp(self, phone_number: str, user_id: Optional[int] = None, async_send: bool = True) -> tuple[bool, Optional[str]]:
        """
        Generate and send OTP via SMS using unified notification service
        
        Args:
            phone_number: Phone number (will be normalized to 91XXXXXXXXXX format)
            user_id: Optional user ID for logging
            async: Whether to send asynchronously (default: True)
        
        Returns:
            Tuple of (success, otp_code or error_message)
        """
        # TEMPORARY: Full details for debugging - no masking
        logger.info(
            f'OTP send_otp() called - Phone: {phone_number} | User ID: {user_id} | Async: {async_send}',
            user=None,
            extra_data={
                'action': 'otp_send_attempt',
                'user_id': user_id,
                'phone_input': phone_number,  # Full phone number
                'async_send': async_send
            }
        )
        
        # Normalize phone number to ensure consistent format for rate limiting
        try:
            normalized_phone = normalize_phone_number(phone_number)
            logger.info(
                f'OTP - Phone normalized: {normalized_phone}',
                user=None,
                extra_data={'action': 'otp_phone_normalized', 'normalized_phone': normalized_phone, 'original_phone': phone_number}
            )
        except ValueError as e:
            logger.error(
                f'OTP - Invalid phone number: {str(e)}',
                user=None,
                extra_data={'action': 'otp_invalid_phone', 'user_id': user_id, 'error': str(e)}
            )
            return False, f"Invalid phone number: {str(e)}"
        
        rate_limit_key = f"otp_rate_limit:{normalized_phone}"
        request_count = cache.get(rate_limit_key, 0)
        
        logger.info(
            f'OTP - Rate limit check: {request_count}/3 attempts',
            user=None,
            extra_data={
                'action': 'otp_rate_limit_check',
                'request_count': request_count,
                'rate_limit_key': rate_limit_key,
                'phone_masked': normalized_phone[:4] + '****'
            }
        )
        
        if request_count >= 3:
            logger.warning(
                f'OTP - Rate limit exceeded for {normalized_phone[:4]}****',
                user=None,
                extra_data={
                    'action': 'otp_rate_limit_exceeded',
                    'user_id': user_id,
                    'phone_masked': normalized_phone[:4] + '****',
                    'request_count': request_count
                }
            )
            return False, "Maximum OTP requests reached. Please try again later."
        
        # Generate OTP
        otp = self.generate_otp()
        logger.info(
            f'OTP - Generated: {otp}',
            user=None,
            extra_data={
                'action': 'otp_generated',
                'user_id': user_id,
                'phone_full': normalized_phone,  # Full phone number
                'otp_code': otp,  # Full OTP code
                'otp_length': len(otp)
            }
        )
        
        # Store OTP in cache using normalized phone
        store_otp_in_cache(normalized_phone, otp, self.otp_expiry)
        logger.info(
            f'OTP - Stored in cache for {normalized_phone} | OTP: {otp}',
            user=None,
            extra_data={
                'action': 'otp_stored_cache',
                'phone_full': normalized_phone,  # Full phone number
                'otp_code': otp,  # Full OTP code
                'expiry_seconds': self.otp_expiry
            }
        )
        
        # Update rate limit
        cache.set(rate_limit_key, request_count + 1, timeout=600)  # 10 minutes window
        logger.info(
            f'OTP - Rate limit updated: {request_count + 1}/3',
            user=None,
            extra_data={'action': 'otp_rate_limit_updated', 'new_count': request_count + 1}
        )
        
        # In DEBUG mode, send OTP synchronously so it works without a Celery worker
        effective_async = async_send and not getattr(settings, 'DEBUG', False)
        if getattr(settings, 'DEBUG', False) and async_send:
            logger.info(
                f'OTP - DEBUG=True: sending OTP synchronously (no Celery required)',
                user=None,
                extra_data={'action': 'otp_sync_in_debug', 'phone_full': normalized_phone}
            )

        # Send OTP via unified notification service
        try:
            logger.info(
                f'OTP - Calling notification_service.send_otp() | Phone: {normalized_phone} | OTP: {otp}',
                user=None,
                extra_data={
                    'action': 'otp_calling_notification_service',
                    'phone_full': normalized_phone,  # Full phone number
                    'otp_code': otp,  # Full OTP code
                    'async_send': effective_async
                }
            )
            
            result = self.notification_service.send_otp(
                phone_number=normalized_phone,
                otp_code=otp,
                user_id=user_id,
                async_send=effective_async
            )
            
            logger.info(
                f'OTP - Notification service result: {result}',
                user=None,
                extra_data={
                    'action': 'otp_notification_service_result',
                    'result': result,  # Complete result
                    'phone_full': normalized_phone,  # Full phone number
                    'otp_code': otp  # Full OTP code
                }
            )
            
            if result.get('success'):
                logger.info(
                    f'OTP - ✅ Sent successfully to {normalized_phone} | OTP: {otp}',
                    user=None,
                    extra_data={
                        'action': 'otp_sent_success',
                        'user_id': user_id,
                        'phone_full': normalized_phone,  # Full phone number
                        'async_send': async_send,
                        'otp_code': otp,  # Full OTP code
                        'result': result
                    }
                )
                return True, otp
            else:
                error_msg = result.get('message', 'Failed to send OTP. Please try again.')
                logger.error(
                    f'OTP - ❌ Failed to send: {error_msg} | Phone: {normalized_phone} | OTP: {otp}',
                    user=None,
                    extra_data={
                        'action': 'otp_send_failed',
                        'user_id': user_id,
                        'phone_full': normalized_phone,  # Full phone number
                        'otp_code': otp,  # Full OTP code
                        'error': error_msg,
                        'result': result  # Complete result
                    }
                )
                return False, error_msg
        except Exception as e:
            logger.error(
                f'OTP - ❌ Exception sending OTP: {str(e)} | Phone: {normalized_phone} | OTP: {otp}',
                user=None,
                extra_data={
                    'action': 'otp_send_exception',
                    'user_id': user_id,
                    'phone_full': normalized_phone,  # Full phone number
                    'otp_code': otp,  # Full OTP code
                    'error': str(e),
                    'exception_type': type(e).__name__
                },
                traceback=str(e)
            )
            return False, f"Error sending OTP: {str(e)}"
    
    def send_otp_dual(
        self,
        email: str,
        phone_number: str,
        user_id: Optional[int] = None,
        async_send: bool = True,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Generate and send same OTP to both email and SMS simultaneously
        
        Args:
            email: Recipient email address
            phone_number: Recipient phone number (will be normalized)
            user_id: Optional user ID for logging
            async_send: Whether to send asynchronously (default: True)
            request_id: Request ID for tracing
            client_ip: Client IP address
            user_agent: User agent string
            session_id: Session ID
        
        Returns:
            Tuple of (success, otp_code or error_message)
        """
        # Normalize phone number
        try:
            normalized_phone = normalize_phone_number(phone_number)
        except ValueError as e:
            logger.error(f'Invalid phone number for dual OTP: {str(e)}', user=None, extra_data={'user_id': user_id})
            return False, f"Invalid phone number: {str(e)}"
        
        # TEMPORARY: Rate limiting disabled for debugging
        # TODO: Re-enable rate limiting after debugging
        phone_rate_key = f"otp_rate_limit:{normalized_phone}"
        email_rate_key = f"otp_rate_limit:{email}"
        
        phone_attempts = cache.get(phone_rate_key, 0)
        email_attempts = cache.get(email_rate_key, 0)
        
        logger.info(
            f'OTP Dual - Rate limit check (DISABLED): Phone {phone_attempts}/3, Email {email_attempts}/3',
            user=None,
            extra_data={
                'action': 'otp_dual_rate_limit_check',
                'phone_attempts': phone_attempts,
                'email_attempts': email_attempts,
                'rate_limit_disabled': True
            }
        )
        
        # TEMPORARY: Rate limit check disabled
        # if phone_attempts >= 3 or email_attempts >= 3:
        #     logger.warning(
        #         f'OTP rate limit exceeded for {normalized_phone[:4]}**** or {email[:2]}***',
        #         user=None,
        #         extra_data={'user_id': user_id}
        #     )
        #     return False, "Maximum OTP requests reached. Please try again later."
        
        # Generate OTP
        otp = self.generate_otp()
        
        # Store OTP in cache for both phone and email
        store_otp_in_cache(normalized_phone, otp, self.otp_expiry)
        store_otp_in_cache(email, otp, self.otp_expiry)
        
        # Update rate limits
        cache.set(phone_rate_key, phone_attempts + 1, timeout=600)  # 10 minutes
        cache.set(email_rate_key, email_attempts + 1, timeout=600)  # 10 minutes
        
        # Send OTP to both channels simultaneously
        try:
            if async_send:
                result = send_otp_dual_delivery_task.delay(
                    otp_code=otp,
                    email=email,
                    phone_number=normalized_phone,
                    user_id=user_id,
                    context={'is_otp': True, 'dual_delivery': True},
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                logger.info(
                    f'OTP dual delivery queued for {normalized_phone[:4]}**** and {email[:2]}***',
                    user=None,
                    extra_data={'user_id': user_id, 'async_send': True}
                )
                return True, otp
            else:
                result = send_otp_dual_delivery_task(
                    otp_code=otp,
                    email=email,
                    phone_number=normalized_phone,
                    user_id=user_id,
                    context={'is_otp': True, 'dual_delivery': True},
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                if result.get('success'):
                    logger.info(
                        f'OTP sent to both channels for {normalized_phone[:4]}**** and {email[:2]}***',
                        user=None,
                        extra_data={'user_id': user_id, 'async_send': False}
                    )
                    return True, otp
                else:
                    return False, result.get('message', 'Failed to send OTP')
        except Exception as e:
            logger.error(
                f'Error sending dual OTP: {str(e)}',
                user=None,
                extra_data={'user_id': user_id},
                traceback=str(e)
            )
            return False, f"Error sending OTP: {str(e)}"
    
    def verify_otp(self, phone_number: str, otp_code: str) -> bool:
        """
        Verify OTP code (from phone or email)
        
        Args:
            phone_number: Phone number or email (will be normalized if phone)
            otp_code: OTP code to verify
        
        Returns:
            True if OTP is valid, False otherwise
        """
        # Try phone number first
        try:
            normalized_phone = normalize_phone_number(phone_number)
            if verify_otp_from_cache(normalized_phone, otp_code):
                return True
        except ValueError:
            pass
        
        # Try email (if phone normalization failed, might be email)
        if '@' in phone_number:
            if verify_otp_from_cache(phone_number, otp_code):
                return True
        
        return False
