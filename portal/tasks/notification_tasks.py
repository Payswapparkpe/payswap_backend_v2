"""
Celery tasks for notification operations (SMS and Email)
"""
from celery import shared_task
from typing import Optional, Dict, Any
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from core.config import payswap_config
from portal.services.vendors.kaleyra import KaleyraClient
from portal.utils.phone_utils import normalize_phone_number, format_phone_for_kaleyra
from portal.utils.logging_helper import get_logger, sanitize_sensitive_data

logger = get_logger('portal.tasks.notifications')


@shared_task(name='portal.tasks.send_sms', bind=True, max_retries=3)
def send_sms_task(
    self,
    phone_number: str,
    message: str,
    user_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Celery task to send SMS asynchronously via Kaleyra
    
    Args:
        phone_number: Phone number (will be normalized to 91XXXXXXXXXX)
        message: SMS message content
        user_id: Optional user ID for logging
        context: Optional context for logging
    
    Returns:
        Dict with success status and details
    """
    context = context or {}
    try:
        # Normalize phone number (91XXXXXXXXXX format, no +)
        normalized_phone = normalize_phone_number(phone_number)
        
        # Log SMS attempt (with masked phone number)
        masked_phone = f"{normalized_phone[:4]}****{normalized_phone[-4:]}"
        logger.info(
            f'Sending SMS to {masked_phone}',
            extra={
                'action': 'send_sms',
                'user_id': user_id,
                'phone_masked': masked_phone,
                'message_length': len(message),
                **sanitize_sensitive_data(context)
            }
        )
        
        # Send SMS via Kaleyra
        kaleyra_client = KaleyraClient()
        # Kaleyra requires + prefix, so format it
        kaleyra_phone = format_phone_for_kaleyra(normalized_phone)
        result = kaleyra_client.send_sms(kaleyra_phone, message, message_type="TXN")
        
        # Check success
        if isinstance(result, dict):
            status = result.get('status', '').lower()
            if status in ['queued', 'sent', 'success', 'submitted'] or 'id' in result:
                logger.info(
                    f'SMS sent successfully to {masked_phone}',
                    extra={
                        'action': 'send_sms_success',
                        'user_id': user_id,
                        'phone_masked': masked_phone,
                        'kaleyra_status': status,
                        **sanitize_sensitive_data(context)
                    }
                )
                return {
                    'success': True,
                    'message': 'SMS sent successfully',
                    'phone_masked': masked_phone,
                    'kaleyra_response': sanitize_sensitive_data(result)
                }
        
        # If we get here, SMS might not have been sent
        logger.warning(
            f'SMS may not have been sent to {masked_phone}',
            extra={
                'action': 'send_sms_warning',
                'user_id': user_id,
                'phone_masked': masked_phone,
                'kaleyra_response': sanitize_sensitive_data(result),
                **sanitize_sensitive_data(context)
            }
        )
        return {
            'success': False,
            'message': 'SMS sending status unclear',
            'phone_masked': masked_phone
        }
        
    except ValueError as e:
        # Invalid phone number format
        logger.error(
            f'Invalid phone number format: {str(e)}',
            extra={
                'action': 'send_sms_error',
                'user_id': user_id,
                'error': str(e),
                'phone_input': phone_number[:4] + '****' if len(phone_number) > 4 else '****',
                **sanitize_sensitive_data(context)
            }
        )
        return {
            'success': False,
            'message': f'Invalid phone number: {str(e)}',
            'error': 'invalid_phone_format'
        }
    except Exception as e:
        # Log error and retry
        masked_phone = phone_number[:4] + '****' + phone_number[-4:] if len(phone_number) > 8 else '****'
        logger.error(
            f'Error sending SMS to {masked_phone}: {str(e)}',
            extra={
                'action': 'send_sms_error',
                'user_id': user_id,
                'error': str(e),
                'phone_masked': masked_phone,
                'retry_count': self.request.retries,
                **sanitize_sensitive_data(context)
            },
            exc_info=True
        )
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(name='portal.tasks.send_email', bind=True, max_retries=3)
def send_email_task(
    self,
    to_email: str,
    subject: str,
    template_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    plain_message: Optional[str] = None,
    user_id: Optional[int] = None,
    extra_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Celery task to send email asynchronously
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        template_name: Optional Django template name for HTML email
        context: Optional template context
        plain_message: Optional plain text message (if no template)
        user_id: Optional user ID for logging
        extra_context: Optional extra context for logging
    
    Returns:
        Dict with success status and details
    """
    context = context or {}
    extra_context = extra_context or {}
    
    try:
        # Mask email for logging
        email_parts = to_email.split('@')
        masked_email = f"{email_parts[0][:2]}***@{email_parts[1]}" if len(email_parts) == 2 else "***@***"
        
        logger.info(
            f'Sending email to {masked_email}',
            extra={
                'action': 'send_email',
                'user_id': user_id,
                'email_masked': masked_email,
                'subject': subject,
                'has_template': template_name is not None,
                **sanitize_sensitive_data(extra_context)
            }
        )
        
        # Prepare email content
        html_message = None
        message = plain_message or "Please view this email in an HTML-enabled email client."
        
        if template_name:
            try:
                html_message = render_to_string(template_name, context)
            except Exception as e:
                logger.warning(
                    f'Failed to render email template {template_name}: {str(e)}',
                    extra={
                        'action': 'send_email_template_error',
                        'user_id': user_id,
                        'email_masked': masked_email,
                        'template': template_name,
                        'error': str(e)
                    }
                )
        
        # Send email
        send_mail(
            subject=subject,
            message=message,
            from_email=payswap_config.SMTP_DEFAULT_FROM,
            recipient_list=[to_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(
            f'Email sent successfully to {masked_email}',
            extra={
                'action': 'send_email_success',
                'user_id': user_id,
                'email_masked': masked_email,
                'subject': subject,
                **sanitize_sensitive_data(extra_context)
            }
        )
        
        return {
            'success': True,
            'message': 'Email sent successfully',
            'email_masked': masked_email,
            'subject': subject
        }
        
    except Exception as e:
        # Log error and retry
        email_parts = to_email.split('@')
        masked_email = f"{email_parts[0][:2]}***@{email_parts[1]}" if len(email_parts) == 2 else "***@***"
        
        logger.error(
            f'Error sending email to {masked_email}: {str(e)}',
            extra={
                'action': 'send_email_error',
                'user_id': user_id,
                'error': str(e),
                'email_masked': masked_email,
                'subject': subject,
                'retry_count': self.request.retries,
                **sanitize_sensitive_data(extra_context)
            },
            exc_info=True
        )
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(name='portal.tasks.send_otp_sms', bind=True, max_retries=3)
def send_otp_sms_task(
    self,
    phone_number: str,
    otp_code: str,
    user_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Celery task to send OTP via SMS
    
    Args:
        phone_number: Phone number (will be normalized)
        otp_code: OTP code to send
        user_id: Optional user ID for logging
        context: Optional context for logging
    
    Returns:
        Dict with success status and details
    """
    context = context or {}
    message = f"Your Payswap verification code is {otp_code}. Valid for 5 minutes."
    
    # Use the general send_sms_task
    return send_sms_task(
        phone_number=phone_number,
        message=message,
        user_id=user_id,
        context={**context, 'otp_length': len(otp_code), 'is_otp': True}
    )
