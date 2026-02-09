"""
Celery tasks for notification operations (SMS and Email)
"""
import traceback
from celery import shared_task
from django.utils import timezone
from typing import Optional, Dict, Any
from django.core.mail import send_mail, get_connection
from django.template.loader import render_to_string
from django.conf import settings
from core.config import payswap_config
from portal.services.vendors.kaleyra import KaleyraClient
from portal.utils.phone_utils import normalize_phone_number, format_phone_for_kaleyra
from portal.utils.logging_helper import get_logger, sanitize_sensitive_data
from portal.models import EmailQueue

logger = get_logger('portal.tasks.notifications')
email_logger = get_logger('portal.email')


@shared_task(
    name='portal.tasks.process_email_queue',
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=5,
)
def process_email_queue_task(self, queue_id: int) -> Dict[str, Any]:
    """
    Process one EmailQueue row by ID. Durable: task ack only after success;
    worker crash re-queues; failures retry with backoff. Never lose email.
    """
    from portal.models import EmailQueue
    from portal.services.email_queue_service import send_email_from_queue_row

    try:
        row = EmailQueue.objects.filter(pk=queue_id).first()
        if not row:
            email_logger.warning('process_email_queue: row not found', extra={'action': 'email_queue_missing', 'queue_id': queue_id})
            return {'success': False, 'reason': 'not_found'}
        if row.status == EmailQueue.STATUS_SENT:
            email_logger.info('process_email_queue: already sent', extra={'action': 'email_queue_already_sent', 'queue_id': queue_id})
            return {'success': True, 'reason': 'already_sent'}

        success, err = send_email_from_queue_row(row)
        if success:
            row.status = EmailQueue.STATUS_SENT
            row.sent_at = timezone.now()
            row.save(update_fields=['status', 'sent_at'])
            email_logger.info('Email sent from queue', extra={'action': 'email_sent', 'queue_id': queue_id})
            return {'success': True, 'queue_id': queue_id}
        # Failure: persist and retry or mark FAILED
        row.retry_count = (row.retry_count or 0) + 1
        row.last_error = (err or '')[:2000]
        row.save(update_fields=['retry_count', 'last_error'])
        email_logger.warning(
            'Email send failed, will retry',
            extra={'action': 'email_retry', 'queue_id': queue_id, 'retry_count': row.retry_count, 'error': (err or '')[:200]},
        )
        if self.request.retries >= self.max_retries - 1:
            row.status = EmailQueue.STATUS_FAILED
            row.save(update_fields=['status'])
            email_logger.error('Email queue marked FAILED after retries', extra={'action': 'email_failed', 'queue_id': queue_id})
            return {'success': False, 'queue_id': queue_id, 'error': err}
        raise self.retry(exc=Exception(err or 'Send failed'))
    except Exception as e:
        if self.request.retries >= self.max_retries - 1:
            try:
                row = EmailQueue.objects.filter(pk=queue_id).first()
                if row and row.status != EmailQueue.STATUS_SENT:
                    row.status = EmailQueue.STATUS_FAILED
                    row.last_error = (str(e))[:2000]
                    row.retry_count = (row.retry_count or 0) + 1
                    row.save(update_fields=['status', 'last_error', 'retry_count'])
                    email_logger.error('Email queue marked FAILED after exception', extra={'action': 'email_failed', 'queue_id': queue_id})
            except Exception:
                pass
        raise


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
            extra_data={
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
                    extra_data={
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
            extra_data={
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
            extra_data={
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
            extra_data={
                'action': 'send_sms_error',
                'user_id': user_id,
                'error': str(e),
                'phone_masked': masked_phone,
                'retry_count': self.request.retries,
                **sanitize_sensitive_data(context)
            },
            traceback=traceback.format_exc()
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
    extra_context: Optional[Dict[str, Any]] = None,
    use_parkpe: bool = False,
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
        
        voucher_tag = ' [VOUCHER]' if use_parkpe else ''
        logger.info(
            f'[EMAIL{voucher_tag}] Sending to {masked_email} | subject={subject[:50]}... | template={template_name or "none"}',
            extra_data={
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
                voucher_tag = ' [VOUCHER]' if use_parkpe else ''
                logger.warning(
                    f'[EMAIL{voucher_tag}] Template render failed: {template_name} | {e}',
                    extra_data={
                        'action': 'send_email_template_error',
                        'user_id': user_id,
                        'email_masked': masked_email,
                        'template': template_name,
                        'error': str(e)
                    }
                )
        
        # Connection: Parkpe SMTP for voucher system, else default
        connection = None
        from_email = payswap_config.SMTP_DEFAULT_FROM
        if use_parkpe:
            if payswap_config.is_parkpe_smtp_configured():
                parkpe_config = payswap_config.get_email_config_parkpe()
                # Use ParkpeSMTPBackend so TLS uses certifi CA bundle (fixes CERTIFICATE_VERIFY_FAILED on macOS)
                connection = get_connection(
                    backend='portal.mail_backends.ParkpeSMTPBackend',
                    host=parkpe_config["EMAIL_HOST"],
                    port=parkpe_config["EMAIL_PORT"],
                    username=parkpe_config["EMAIL_HOST_USER"],
                    password=parkpe_config["EMAIL_HOST_PASSWORD"],
                    use_tls=parkpe_config["EMAIL_USE_TLS"],
                    fail_silently=False,
                )
                from_email = parkpe_config["DEFAULT_FROM_EMAIL"]
                logger.info(
                    f'[VOUCHER] Email using Parkpe SMTP | host={parkpe_config["EMAIL_HOST"]} port={parkpe_config["EMAIL_PORT"]}',
                    extra_data={'action': 'send_email_parkpe', 'email_masked': masked_email}
                )
            else:
                logger.warning(
                    '[VOUCHER] Parkpe SMTP NOT configured (set SMTP_HOST_Parkpe, SMTP_USER_Parkpe, SMTP_PASSWORD_Parkpe in .env). Using default SMTP.',
                    extra_data={'action': 'send_email_parkpe_fallback', 'email_masked': masked_email}
                )
        
        # Send email
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[to_email],
            html_message=html_message,
            fail_silently=False,
            connection=connection,
        )
        
        voucher_tag = ' [VOUCHER]' if use_parkpe else ''
        logger.info(
            f'[EMAIL{voucher_tag}] Sent OK to {masked_email}',
            extra_data={
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
        
        voucher_tag = ' [VOUCHER]' if use_parkpe else ''
        logger.error(
            f'[EMAIL{voucher_tag}] Error sending to {masked_email}: {e}',
            extra_data={
                'action': 'send_email_error',
                'user_id': user_id,
                'error': str(e),
                'email_masked': masked_email,
                'subject': subject,
                'retry_count': self.request.retries,
                **sanitize_sensitive_data(extra_context)
            },
            traceback=traceback.format_exc()
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
    Celery task to send OTP via SMS - DIRECTLY calls KaleyraClient.send_otp()
    
    Args:
        phone_number: Phone number (will be normalized)
        otp_code: OTP code to send
        user_id: Optional user ID for logging
        context: Optional context for logging
    
    Returns:
        Dict with success status and details
    """
    from portal.services.vendors.kaleyra import KaleyraClient
    from portal.utils.phone_utils import normalize_phone_number
    from portal.tasks.write_logs_task import write_logs_task
    
    context = context or {}
    module_name = 'portal.tasks.send_otp_sms'
    
    try:
        # Normalize phone number (91XXXXXXXXXX format, no +)
        normalized_phone = normalize_phone_number(phone_number)
        masked_phone = f"{normalized_phone[:4]}****{normalized_phone[-4:]}"
        
        # Log OTP send attempt
        write_logs_task.delay(
            log_level='INFO',
            message=f'OTP SMS Task - Calling KaleyraClient.send_otp() | Phone: {masked_phone} | OTP: {otp_code}',
            module_name=module_name,
            url=None,
            request_id=None,
            response_id=None,
            user_id=user_id,
            extra_data={
                'action': 'otp_sms_task_start',
                'phone_masked': masked_phone,
                'otp_code': otp_code,
                **context
            },
            client_ip=None,
            user_agent=None,
            session_id=None
        )
        
        # DIRECTLY call KaleyraClient.send_otp() - this has all the logging and template_id
        kaleyra_client = KaleyraClient()
        success = kaleyra_client.send_otp(normalized_phone, otp_code)
        
        if success:
            write_logs_task.delay(
                log_level='INFO',
                message=f'OTP SMS Task - Success | Phone: {masked_phone} | OTP: {otp_code}',
                module_name=module_name,
                url=None,
                request_id=None,
                response_id=None,
                user_id=user_id,
                extra_data={
                    'action': 'otp_sms_task_success',
                    'phone_masked': masked_phone,
                    'otp_code': otp_code
                },
                client_ip=None,
                user_agent=None,
                session_id=None
            )
            return {
                'success': True,
                'message': 'OTP sent successfully',
                'phone_masked': masked_phone
            }
        else:
            write_logs_task.delay(
                log_level='WARNING',
                message=f'OTP SMS Task - Failed | Phone: {masked_phone} | OTP: {otp_code}',
                module_name=module_name,
                url=None,
                request_id=None,
                response_id=None,
                user_id=user_id,
                extra_data={
                    'action': 'otp_sms_task_failed',
                    'phone_masked': masked_phone,
                    'otp_code': otp_code
                },
                client_ip=None,
                user_agent=None,
                session_id=None
            )
            return {
                'success': False,
                'message': 'OTP sending failed',
                'phone_masked': masked_phone
            }
            
    except Exception as e:
        # Log error and retry
        masked_phone = phone_number[:4] + '****' + phone_number[-4:] if len(phone_number) > 8 else '****'
        write_logs_task.delay(
            log_level='ERROR',
            message=f'OTP SMS Task - Error: {str(e)} | Phone: {masked_phone}',
            module_name=module_name,
            url=None,
            request_id=None,
            response_id=None,
            user_id=user_id,
            extra_data={
                'action': 'otp_sms_task_error',
                'error': str(e),
                'phone_masked': masked_phone,
                'retry_count': self.request.retries
            },
            client_ip=None,
            user_agent=None,
            session_id=None
        )
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
