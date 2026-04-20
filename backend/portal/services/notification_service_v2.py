"""
Unified Notification Service with Celery Tasks
This service provides a single interface for sending SMS and Email notifications
across the entire application with secure logging and async processing.
"""
from typing import Optional, Dict, Any, List
from django.template.loader import render_to_string
from portal.tasks.notification_tasks import (
    send_sms_task,
    send_email_task,
    send_otp_sms_task
)
from portal.models import ApiVendor, VendorApi
from portal.utils.phone_utils import normalize_phone_number
from portal.utils.logging_helper import get_logger
import traceback

logger = get_logger('portal.services.notifications')


def _is_vendor_api_enabled(vendor_code: str, api_code: str) -> bool:
    vendor = ApiVendor.objects.filter(code=vendor_code, is_active=True).first()
    if not vendor:
        return False
    return VendorApi.objects.filter(vendor=vendor, api_code=api_code, is_active=True).exists()


class NotificationServiceV2:
    """
    Unified notification service for SMS and Email
    All notifications are sent asynchronously via Celery tasks
    """
    
    @staticmethod
    def send_sms(
        phone_number: str,
        message: str,
        user_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        async_send: bool = True
    ) -> Dict[str, Any]:
        """
        Send SMS notification
        
        Args:
            phone_number: Phone number (will be normalized to 91XXXXXXXXXX)
            message: SMS message content
            user_id: Optional user ID for logging
            context: Optional context for logging
            async_send: Whether to send asynchronously (default: True)
        
        Returns:
            Dict with task ID (if async_send) or result (if sync)
        """
        try:
            if not _is_vendor_api_enabled("kaleyra", "sms"):
                return {
                    'success': False,
                    'error': 'AD400',
                    'message': 'AD400',
                }

            # Validate and normalize phone number
            normalized_phone = normalize_phone_number(phone_number)
            
            if async_send:
                # Send asynchronously via Celery
                task = send_sms_task.delay(
                    phone_number=normalized_phone,
                    message=message,
                    user_id=user_id,
                    context=context or {}
                )
                return {
                    'success': True,
                    'async': True,
                    'task_id': task.id,
                    'message': 'SMS queued for sending'
                }
            else:
                # Send synchronously (for testing or critical messages)
                result = send_sms_task(
                    phone_number=normalized_phone,
                    message=message,
                    user_id=user_id,
                    context=context or {}
                )
                return result
                
        except ValueError as e:
            logger.error(f'Invalid phone number: {str(e)}', extra={'user_id': user_id})
            return {
                'success': False,
                'error': 'invalid_phone_format',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f'Error queuing SMS: {str(e)}', extra_data={'user_id': user_id}, traceback=traceback.format_exc())
            return {
                'success': False,
                'error': 'queue_error',
                'message': str(e)
            }
    
    @staticmethod
    def send_email(
        to_email: str,
        subject: str,
        template_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        plain_message: Optional[str] = None,
        user_id: Optional[int] = None,
        async_send: bool = True,
        use_parkpe: bool = False,
    ) -> Dict[str, Any]:
        """
        Send email notification.
        use_parkpe=True uses Parkpe SMTP (voucher system; Zoho etc.).

        Args:
            to_email: Recipient email address
            subject: Email subject
            template_name: Optional Django template name for HTML email
            context: Optional template context
            plain_message: Optional plain text message (if no template)
            user_id: Optional user ID for logging
            async_send: Whether to send asynchronously (default: True)
            use_parkpe: Use Parkpe SMTP for voucher emails (default: False)

        Returns:
            Dict with task ID (if async_send) or result (if sync)
        """
        try:
            extra = {'has_template': template_name is not None, 'use_parkpe': use_parkpe}
            if async_send:
                # Send asynchronously via Celery
                task = send_email_task.delay(
                    to_email=to_email,
                    subject=subject,
                    template_name=template_name,
                    context=context or {},
                    plain_message=plain_message,
                    user_id=user_id,
                    extra_context=extra,
                    use_parkpe=use_parkpe,
                )
                return {
                    'success': True,
                    'async': True,
                    'task_id': task.id,
                    'message': 'Email queued for sending'
                }
            else:
                # Send synchronously (for testing or critical messages)
                result = send_email_task(
                    to_email=to_email,
                    subject=subject,
                    template_name=template_name,
                    context=context or {},
                    plain_message=plain_message,
                    user_id=user_id,
                    extra_context=extra,
                    use_parkpe=use_parkpe,
                )
                return result
                
        except Exception as e:
            logger.error(f'Error queuing email: {str(e)}', extra_data={'user_id': user_id}, traceback=traceback.format_exc())
            return {
                'success': False,
                'error': 'queue_error',
                'message': str(e)
            }
    
    @staticmethod
    def send_otp(
        phone_number: str,
        otp_code: str,
        user_id: Optional[int] = None,
        async_send: bool = True
    ) -> Dict[str, Any]:
        """
        Send OTP via SMS
        
        Args:
            phone_number: Phone number (will be normalized)
            otp_code: OTP code to send
            user_id: Optional user ID for logging
            async_send: Whether to send asynchronously (default: True)
        
        Returns:
            Dict with task ID (if async_send) or result (if sync)
        """
        try:
            if not _is_vendor_api_enabled("kaleyra", "sms"):
                return {
                    'success': False,
                    'error': 'AD400',
                    'message': 'AD400',
                }

            # Validate and normalize phone number
            normalized_phone = normalize_phone_number(phone_number)
            
            if async_send:
                # Send asynchronously via Celery
                task = send_otp_sms_task.delay(
                    phone_number=normalized_phone,
                    otp_code=otp_code,
                    user_id=user_id,
                    context={'is_otp': True}
                )
                return {
                    'success': True,
                    'async': True,
                    'task_id': task.id,
                    'message': 'OTP queued for sending'
                }
            else:
                # Send synchronously
                result = send_otp_sms_task(
                    phone_number=normalized_phone,
                    otp_code=otp_code,
                    user_id=user_id,
                    context={'is_otp': True}
                )
                return result
                
        except ValueError as e:
            logger.error(f'Invalid phone number for OTP: {str(e)}', extra={'user_id': user_id})
            return {
                'success': False,
                'error': 'invalid_phone_format',
                'message': str(e)
            }
        except Exception as e:
            logger.error(f'Error queuing OTP: {str(e)}', extra_data={'user_id': user_id}, traceback=traceback.format_exc())
            return {
                'success': False,
                'error': 'queue_error',
                'message': str(e)
            }
    
    @staticmethod
    def send_bulk_sms(
        phone_numbers: List[str],
        message: str,
        user_id: Optional[int] = None,
        async_send: bool = True
    ) -> Dict[str, Any]:
        """
        Send SMS to multiple recipients
        
        Args:
            phone_numbers: List of phone numbers
            message: SMS message content
            user_id: Optional user ID for logging
            async_send: Whether to send asynchronously (default: True)
        
        Returns:
            Dict with task IDs and summary
        """
        task_ids = []
        errors = []
        
        for phone in phone_numbers:
            try:
                result = NotificationServiceV2.send_sms(
                    phone_number=phone,
                    message=message,
                    user_id=user_id,
                    async_send=async_send
                )
                if result.get('success'):
                    if async_send:
                        task_ids.append(result.get('task_id'))
                else:
                    errors.append({'phone': phone[:4] + '****', 'error': result.get('message')})
            except Exception as e:
                errors.append({'phone': phone[:4] + '****', 'error': str(e)})
        
        return {
            'success': len(errors) == 0,
            'total': len(phone_numbers),
            'queued': len(task_ids),
            'errors': len(errors),
            'task_ids': task_ids,
            'error_details': errors
        }
    
    @staticmethod
    def send_bulk_email(
        to_emails: List[str],
        subject: str,
        template_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        plain_message: Optional[str] = None,
        user_id: Optional[int] = None,
        async_send: bool = True
    ) -> Dict[str, Any]:
        """
        Send email to multiple recipients
        
        Args:
            to_emails: List of email addresses
            subject: Email subject
            template_name: Optional Django template name
            context: Optional template context
            plain_message: Optional plain text message
            user_id: Optional user ID for logging
            async_send: Whether to send asynchronously (default: True)
        
        Returns:
            Dict with task IDs and summary
        """
        task_ids = []
        errors = []
        
        for email in to_emails:
            try:
                result = NotificationServiceV2.send_email(
                    to_email=email,
                    subject=subject,
                    template_name=template_name,
                    context=context,
                    plain_message=plain_message,
                    user_id=user_id,
                    async_send=async_send
                )
                if result.get('success'):
                    if async_send:
                        task_ids.append(result.get('task_id'))
                else:
                    email_parts = email.split('@')
                    masked = f"{email_parts[0][:2]}***@{email_parts[1]}" if len(email_parts) == 2 else "***@***"
                    errors.append({'email': masked, 'error': result.get('message')})
            except Exception as e:
                email_parts = email.split('@')
                masked = f"{email_parts[0][:2]}***@{email_parts[1]}" if len(email_parts) == 2 else "***@***"
                errors.append({'email': masked, 'error': str(e)})
        
        return {
            'success': len(errors) == 0,
            'total': len(to_emails),
            'queued': len(task_ids),
            'errors': len(errors),
            'task_ids': task_ids,
            'error_details': errors
        }
