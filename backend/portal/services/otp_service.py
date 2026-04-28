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
from portal.utils.phone_utils import normalize_phone_number, mask_phone_number
from portal.utils.logging_helper import get_logger

# Mask for logs: never log OTP or full phone/email. Use this for all log extra_data.
def _mask_phone_for_log(phone: str) -> str:
    if not phone:
        return "****"
    return mask_phone_number(phone, show_last_digits=4)


def _mask_email_for_log(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}" if len(local) > 1 else f"***@{domain}"
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
        # Security: never log full phone or OTP. Mask all PII in logs.
        logger.info(
            'OTP send_otp() called',
            user=None,
            extra_data={
                'action': 'otp_send_attempt',
                'user_id': user_id,
                'phone_masked': _mask_phone_for_log(phone_number),
                'async_send': async_send
            }
        )
        
        # Normalize phone number to ensure consistent format for rate limiting
        try:
            normalized_phone = normalize_phone_number(phone_number)
            logger.info(
                'OTP - Phone normalized',
                user=None,
                extra_data={'action': 'otp_phone_normalized', 'phone_masked': _mask_phone_for_log(normalized_phone)}
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
        OTP_SEND_LIMIT = getattr(settings, 'OTP_SEND_RATE_LIMIT', 3)
        logger.info(
            'OTP - Rate limit check',
            user=None,
            extra_data={
                'action': 'otp_rate_limit_check',
                'request_count': request_count,
                'phone_masked': _mask_phone_for_log(normalized_phone)
            }
        )
        if request_count >= OTP_SEND_LIMIT:
            logger.warning(
                'OTP - Rate limit exceeded',
                user=None,
                extra_data={
                    'action': 'otp_rate_limit_exceeded',
                    'user_id': user_id,
                    'phone_masked': _mask_phone_for_log(normalized_phone),
                    'request_count': request_count
                }
            )
            return False, "Maximum OTP requests reached. Please try again later."
        # Generate OTP (never log the value)
        otp = self.generate_otp()
        logger.info(
            'OTP - Generated',
            user=None,
            extra_data={
                'action': 'otp_generated',
                'user_id': user_id,
                'phone_masked': _mask_phone_for_log(normalized_phone),
                'otp_length': len(otp)
            }
        )
        
        # Store OTP in cache using normalized phone
        store_otp_in_cache(normalized_phone, otp, self.otp_expiry)
        logger.info(
            'OTP - Stored in cache',
            user=None,
            extra_data={
                'action': 'otp_stored_cache',
                'phone_masked': _mask_phone_for_log(normalized_phone),
                'expiry_seconds': self.otp_expiry
            }
        )
        
        # Update rate limit
        cache.set(rate_limit_key, request_count + 1, timeout=600)  # 10 minutes window
        logger.info(
            'OTP - Rate limit updated',
            user=None,
            extra_data={'action': 'otp_rate_limit_updated', 'new_count': request_count + 1}
        )
        
        # In DEBUG mode, send OTP synchronously so it works without a Celery worker
        effective_async = async_send and not getattr(settings, 'DEBUG', False)
        if getattr(settings, 'DEBUG', False) and async_send:
            logger.info(
                'OTP - DEBUG=True: sending OTP synchronously (no Celery required)',
                user=None,
                extra_data={'action': 'otp_sync_in_debug', 'phone_masked': _mask_phone_for_log(normalized_phone)}
            )

        # Send OTP via unified notification service (never log OTP)
        try:
            logger.info(
                'OTP - Calling notification_service.send_otp()',
                user=None,
                extra_data={
                    'action': 'otp_calling_notification_service',
                    'phone_masked': _mask_phone_for_log(normalized_phone),
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
                'OTP - Notification service result',
                user=None,
                extra_data={
                    'action': 'otp_notification_service_result',
                    'success': result.get('success'),
                    'phone_masked': _mask_phone_for_log(normalized_phone)
                }
            )
            
            if result.get('success'):
                logger.info(
                    'OTP - Sent successfully',
                    user=None,
                    extra_data={
                        'action': 'otp_sent_success',
                        'user_id': user_id,
                        'phone_masked': _mask_phone_for_log(normalized_phone),
                        'async_send': async_send
                    }
                )
                return True, otp
            else:
                error_code = result.get('error')
                error_msg = result.get('message', 'Failed to send OTP. Please try again.')
                if error_code == 'AD400':
                    error_msg = 'AD400'
                logger.error(
                    'OTP - Failed to send',
                    user=None,
                    extra_data={
                        'action': 'otp_send_failed',
                        'user_id': user_id,
                        'phone_masked': _mask_phone_for_log(normalized_phone),
                        'error': error_msg
                    }
                )
                # So you see the reason in Django runserver console when OTP does not arrive
                import sys
                print(f"[OTP] Send failed: {error_msg}", file=sys.stderr)
                return False, error_msg
        except Exception as e:
            logger.error(
                'OTP - Exception sending OTP',
                user=None,
                extra_data={
                    'action': 'otp_send_exception',
                    'user_id': user_id,
                    'phone_masked': _mask_phone_for_log(normalized_phone),
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
        
        phone_rate_key = f"otp_rate_limit:{normalized_phone}"
        email_rate_key = f"otp_rate_limit:{email}"
        phone_attempts = cache.get(phone_rate_key, 0)
        email_attempts = cache.get(email_rate_key, 0)
        
        logger.info(
            'OTP Dual - Rate limit check',
            user=None,
            extra_data={
                'action': 'otp_dual_rate_limit_check',
                'phone_attempts': phone_attempts,
                'email_attempts': email_attempts,
                'phone_masked': _mask_phone_for_log(normalized_phone),
                'email_masked': _mask_email_for_log(email)
            }
        )
        
        OTP_SEND_LIMIT = getattr(settings, 'OTP_SEND_RATE_LIMIT', 3)
        if phone_attempts >= OTP_SEND_LIMIT or email_attempts >= OTP_SEND_LIMIT:
            logger.warning(
                'OTP dual rate limit exceeded',
                user=None,
                extra_data={
                    'user_id': user_id,
                    'phone_masked': _mask_phone_for_log(normalized_phone),
                    'email_masked': _mask_email_for_log(email)
                }
            )
            return False, "Maximum OTP requests reached. Please try again later."
        
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
                    'OTP dual delivery queued',
                    user=None,
                    extra_data={
                        'user_id': user_id,
                        'async_send': True,
                        'phone_masked': _mask_phone_for_log(normalized_phone),
                        'email_masked': _mask_email_for_log(email)
                    }
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
                        'OTP sent to both channels',
                        user=None,
                        extra_data={
                            'user_id': user_id,
                            'async_send': False,
                            'phone_masked': _mask_phone_for_log(normalized_phone),
                            'email_masked': _mask_email_for_log(email)
                        }
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
    
    # VAPT-004: per-identity failure counter and lockout
    OTP_VERIFY_FAIL_MAX = 10
    OTP_VERIFY_FAIL_TTL = 1800  # 30 minutes

    def verify_otp(self, phone_number: str, otp_code: str) -> Tuple[bool, Optional[str]]:
        """
        Verify OTP code (from phone or email). VAPT-004: per-identity lockout after N failures.
        
        Returns:
            (True, None) if valid; (False, None) if invalid; (False, "locked") if lockout.
        """
        identity = None
        # Try phone number first
        try:
            normalized_phone = normalize_phone_number(phone_number)
            identity = normalized_phone
            fail_key = f"otp_verify_fail:{identity}"
            fail_count = cache.get(fail_key, 0)
            if fail_count >= self.OTP_VERIFY_FAIL_MAX:
                return (False, "locked")
            if verify_otp_from_cache(normalized_phone, otp_code):
                cache.delete(fail_key)
                return (True, None)
            cache.set(fail_key, fail_count + 1, timeout=self.OTP_VERIFY_FAIL_TTL)
            return (False, None)
        except ValueError:
            pass
        
        # Try email (if phone normalization failed, might be email)
        if '@' in phone_number:
            identity = phone_number
            fail_key = f"otp_verify_fail:{identity}"
            fail_count = cache.get(fail_key, 0)
            if fail_count >= self.OTP_VERIFY_FAIL_MAX:
                return (False, "locked")
            if verify_otp_from_cache(phone_number, otp_code):
                cache.delete(fail_key)
                return (True, None)
            cache.set(fail_key, fail_count + 1, timeout=self.OTP_VERIFY_FAIL_TTL)
            return (False, None)
        
        return (False, None)
