"""
Unified notification dispatcher task
Routes notifications to appropriate channels (SMS, Email, or both)
"""
from celery import shared_task
from typing import Optional, Dict, Any, List
from portal.tasks.sms_task import send_sms_task
from portal.tasks.email_task import send_email_task
from portal.tasks.otp_dual_delivery_task import send_otp_dual_delivery_task


@shared_task(name='portal.tasks.send_notification')
def send_notification_task(
    notification_type: str,
    channels: List[str],  # ['sms', 'email', 'both']
    message: str,
    subject: Optional[str] = None,
    to_email: Optional[str] = None,
    phone_number: Optional[str] = None,
    template_name: Optional[str] = None,
    template_context: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
    use_parkpe: bool = False,
) -> Dict[str, Any]:
    """
    Unified notification dispatcher
    Routes to SMS, Email, or both based on channels parameter
    
    Args:
        notification_type: Type of notification (e.g., 'otp', 'alert', 'transaction')
        channels: List of channels ['sms', 'email', 'both']
        message: Message content
        subject: Email subject (required for email)
        to_email: Recipient email
        phone_number: Recipient phone
        template_name: Optional email template
        template_context: Optional template context
        user_id: Optional user ID
        context: Optional context
        request_id: Request ID
        client_ip: Client IP
        user_agent: User agent
        session_id: Session ID
    
    Returns:
        Dict with success status and task IDs
    """
    context = context or {}
    task_ids = []
    errors = []
    
    # Send SMS if requested
    if 'sms' in channels or 'both' in channels:
        if phone_number:
            try:
                task = send_sms_task.delay(
                    phone_number=phone_number,
                    message=message,
                    user_id=user_id,
                    context={**context, 'notification_type': notification_type},
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                task_ids.append({'channel': 'sms', 'task_id': task.id})
            except Exception as e:
                errors.append({'channel': 'sms', 'error': str(e)})
        else:
            errors.append({'channel': 'sms', 'error': 'phone_number required'})
    
    # Send Email if requested
    if 'email' in channels or 'both' in channels:
        if to_email:
            try:
                task = send_email_task.delay(
                    to_email=to_email,
                    subject=subject or 'Notification from Payswap',
                    template_name=template_name,
                    context=template_context or {},
                    plain_message=message,
                    user_id=user_id,
                    extra_context={**context, 'notification_type': notification_type},
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id,
                    use_parkpe=use_parkpe,
                )
                task_ids.append({'channel': 'email', 'task_id': task.id})
            except Exception as e:
                errors.append({'channel': 'email', 'error': str(e)})
        else:
            errors.append({'channel': 'email', 'error': 'to_email required'})
    
    return {
        'success': len(errors) == 0,
        'message': f'Notification sent via {", ".join(channels)}',
        'task_ids': task_ids,
        'errors': errors if errors else None
    }
