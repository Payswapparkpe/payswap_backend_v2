"""
Email sending task using utils
"""
from celery import shared_task
from typing import Optional, Dict, Any
from django.core.mail import send_mail, get_connection
from django.template.loader import render_to_string
from django.conf import settings
from core.config import payswap_config
from portal.tasks.write_logs_task import write_logs_task


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
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
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
        request_id: Request ID for tracing
        client_ip: Client IP address
        user_agent: User agent string
        session_id: Session ID
    
    Returns:
        Dict with success status and details
    """
    context = context or {}
    extra_context = extra_context or {}
    module_name = 'portal.tasks.email_task'
    
    try:
        # Mask email for logging
        email_parts = to_email.split('@')
        masked_email = f"{email_parts[0][:2]}***@{email_parts[1]}" if len(email_parts) == 2 else "***@***"
        
        # Log email attempt
        write_logs_task.delay(
            log_level='INFO',
            message=f'Sending email to {masked_email}',
            module_name=module_name,
            url=None,
            request_id=request_id,
            response_id=None,
            user_id=user_id,
            extra_data={
                'action': 'send_email',
                'email_masked': masked_email,
                'subject': subject,
                'has_template': template_name is not None,
                **extra_context
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        
        # Prepare email content
        html_message = None
        message = plain_message or "Please view this email in an HTML-enabled email client."
        
        if template_name:
            try:
                html_message = render_to_string(template_name, context)
            except Exception as e:
                write_logs_task.delay(
                    log_level='WARNING',
                    message=f'Failed to render email template {template_name}: {str(e)}',
                    module_name=module_name,
                    url=None,
                    request_id=request_id,
                    response_id=None,
                    user_id=user_id,
                    extra_data={
                        'action': 'send_email_template_error',
                        'email_masked': masked_email,
                        'template': template_name,
                        'error': str(e)
                    },
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
        
        # Connection: Parkpe SMTP for voucher system, else default
        connection = None
        from_email = payswap_config.SMTP_DEFAULT_FROM
        if use_parkpe and payswap_config.is_parkpe_smtp_configured():
            parkpe_config = payswap_config.get_email_config_parkpe()
            connection = get_connection(
                backend=parkpe_config["EMAIL_BACKEND"],
                host=parkpe_config["EMAIL_HOST"],
                port=parkpe_config["EMAIL_PORT"],
                username=parkpe_config["EMAIL_HOST_USER"],
                password=parkpe_config["EMAIL_HOST_PASSWORD"],
                use_tls=parkpe_config["EMAIL_USE_TLS"],
                fail_silently=False,
            )
            from_email = parkpe_config["DEFAULT_FROM_EMAIL"]

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
        
        # Log success
        write_logs_task.delay(
            log_level='INFO',
            message=f'Email sent successfully to {masked_email}',
            module_name=module_name,
            url=None,
            request_id=request_id,
            response_id=None,
            user_id=user_id,
            extra_data={
                'action': 'send_email_success',
                'email_masked': masked_email,
                'subject': subject
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
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
        
        write_logs_task.delay(
            log_level='ERROR',
            message=f'Error sending email to {masked_email}: {str(e)}',
            module_name=module_name,
            url=None,
            request_id=request_id,
            response_id=None,
            user_id=user_id,
            extra_data={
                'action': 'send_email_error',
                'error': str(e),
                'email_masked': masked_email,
                'subject': subject,
                'retry_count': self.request.retries
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
