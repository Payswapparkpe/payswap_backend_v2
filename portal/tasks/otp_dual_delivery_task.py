"""
OTP dual delivery task - sends same OTP to both email and SMS simultaneously
"""
from celery import shared_task
from typing import Optional, Dict, Any
from portal.tasks.sms_task import send_sms_task
from portal.tasks.email_task import send_email_task
from portal.utils.phone_utils import normalize_phone_number


@shared_task(name='portal.tasks.send_otp_dual', bind=True, max_retries=3)
def send_otp_dual_delivery_task(
    self,
    otp_code: str,
    email: str,
    phone_number: str,
    user_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send same OTP code to both email and SMS simultaneously via Celery tasks
    
    Args:
        otp_code: OTP code to send (same for both channels)
        email: Recipient email address
        phone_number: Recipient phone number (will be normalized)
        user_id: Optional user ID for logging
        context: Optional context for logging
        request_id: Request ID for tracing
        client_ip: Client IP address
        user_agent: User agent string
        session_id: Session ID
    
    Returns:
        Dict with success status and task IDs
    """
    context = context or {}
    module_name = 'portal.tasks.otp_dual_delivery'
    
    try:
        # Normalize phone number
        normalized_phone = normalize_phone_number(phone_number)
        
        # Prepare OTP message (same for both channels)
        otp_message = f"Your Payswap verification code is {otp_code}. Valid for 5 minutes."
        
        # Email subject
        email_subject = "Your Payswap Verification Code"
        
        # Send to both channels simultaneously
        sms_task = send_sms_task.delay(
            phone_number=normalized_phone,
            message=otp_message,
            user_id=user_id,
            context={**context, 'is_otp': True, 'otp_length': len(otp_code)},
            request_id=request_id,
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        
        email_task = send_email_task.delay(
            to_email=email,
            subject=email_subject,
            plain_message=otp_message,
            user_id=user_id,
            extra_context={**context, 'is_otp': True, 'otp_length': len(otp_code)},
            request_id=request_id,
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        
        return {
            'success': True,
            'message': 'OTP sent to both email and SMS',
            'sms_task_id': sms_task.id,
            'email_task_id': email_task.id,
            'otp_code': otp_code  # For testing only, remove in production
        }
        
    except ValueError as e:
        # Invalid phone number format
        return {
            'success': False,
            'message': f'Invalid phone number: {str(e)}',
            'error': 'invalid_phone_format'
        }
    except Exception as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
