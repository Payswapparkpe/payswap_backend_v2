"""
Durable email queue service.
- Always enqueue here; never send email directly from request/transaction.
- EmailQueue is the source of truth; Celery task and resend_pending_emails both consume from it.
"""
import logging
from typing import Optional, Dict, Any, Tuple

from django.core.mail import send_mail, get_connection

from core.config import payswap_config
from portal.models import EmailQueue

logger = logging.getLogger('portal.email')


def enqueue_email(
    to_email: str,
    subject: str,
    body_html: Optional[str] = None,
    body_text: Optional[str] = None,
    related_entity: Optional[Dict[str, Any]] = None,
    use_parkpe_smtp: bool = False,
) -> EmailQueue:
    """
    Create an EmailQueue row. Caller must then trigger process_email_queue_task.delay(row.id).
    Never send email directly from request/transaction.
    """
    body_text = body_text or (body_html and body_html[:500]) or 'Please view in an HTML client.'
    row = EmailQueue.objects.create(
        to_email=to_email,
        subject=subject,
        body_html=body_html or '',
        body_text=body_text,
        status=EmailQueue.STATUS_PENDING,
        related_entity=related_entity,
        use_parkpe_smtp=use_parkpe_smtp,
    )
    masked = _mask_email(to_email)
    logger.info(
        'Email enqueued',
        extra={
            'action': 'email_enqueued',
            'queue_id': row.id,
            'email_masked': masked,
            'subject': subject[:80],
        },
    )
    return row


def send_email_from_queue_row(row: EmailQueue) -> Tuple[bool, Optional[str]]:
    """
    Send one EmailQueue row (Django send_mail). Used by Celery task and resend_pending_emails.
    Returns (success, error_message).
    Does NOT update row status; caller updates SENT/FAILED and retry_count/last_error.
    """
    masked = _mask_email(row.to_email)
    connection = None
    from_email = payswap_config.SMTP_DEFAULT_FROM
    if row.use_parkpe_smtp and payswap_config.is_parkpe_smtp_configured():
        parkpe_config = payswap_config.get_email_config_parkpe()
        connection = get_connection(
            backend='portal.mail_backends.ParkpeSMTPBackend',
            host=parkpe_config['EMAIL_HOST'],
            port=parkpe_config['EMAIL_PORT'],
            username=parkpe_config['EMAIL_HOST_USER'],
            password=parkpe_config['EMAIL_HOST_PASSWORD'],
            use_tls=parkpe_config['EMAIL_USE_TLS'],
            fail_silently=False,
        )
        from_email = parkpe_config['DEFAULT_FROM_EMAIL']

    try:
        send_mail(
            subject=row.subject,
            message=row.body_text or 'Please view in an HTML client.',
            from_email=from_email,
            recipient_list=[row.to_email],
            html_message=row.body_html or None,
            fail_silently=False,
            connection=connection,
        )
        logger.info(
            'Email sent',
            extra={
                'action': 'email_sent',
                'queue_id': row.id,
                'email_masked': masked,
            },
        )
        return True, None
    except Exception as e:
        err = str(e)
        logger.warning(
            'Email send failed',
            extra={
                'action': 'email_failed',
                'queue_id': row.id,
                'email_masked': masked,
                'error': err,
            },
        )
        return False, err


def _mask_email(email: str) -> str:
    parts = email.split('@')
    if len(parts) == 2:
        return f"{parts[0][:2]}***@{parts[1]}"
    return '***@***'
