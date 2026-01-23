"""
SMS sending task using utils
"""
from celery import shared_task
from typing import Optional, Dict, Any
from portal.services.vendors.kaleyra import KaleyraClient
from portal.utils.phone_utils import normalize_phone_number, format_phone_for_kaleyra
from portal.tasks.write_logs_task import write_logs_task
from portal.utils.ip_utils import mask_ip


@shared_task(name='portal.tasks.send_sms', bind=True, max_retries=3)
def send_sms_task(
    self,
    phone_number: str,
    message: str,
    user_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Celery task to send SMS asynchronously via Kaleyra
    
    Args:
        phone_number: Phone number (will be normalized to 91XXXXXXXXXX)
        message: SMS message content
        user_id: Optional user ID for logging
        context: Optional context for logging
        request_id: Request ID for tracing
        client_ip: Client IP address
        user_agent: User agent string
        session_id: Session ID
    
    Returns:
        Dict with success status and details
    """
    context = context or {}
    module_name = 'portal.tasks.sms_task'
    
    try:
        # Normalize phone number (91XXXXXXXXXX format, no +)
        normalized_phone = normalize_phone_number(phone_number)
        masked_phone = f"{normalized_phone[:4]}****{normalized_phone[-4:]}"
        
        # Log SMS attempt
        write_logs_task.delay(
            log_level='INFO',
            message=f'Sending SMS to {masked_phone}',
            module_name=module_name,
            url=None,
            request_id=request_id,
            response_id=None,
            user_id=user_id,
            extra_data={
                'action': 'send_sms',
                'phone_masked': masked_phone,
                'message_length': len(message),
                **context
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
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
                # Log success
                write_logs_task.delay(
                    log_level='INFO',
                    message=f'SMS sent successfully to {masked_phone}',
                    module_name=module_name,
                    url=None,
                    request_id=request_id,
                    response_id=None,
                    user_id=user_id,
                    extra_data={
                        'action': 'send_sms_success',
                        'phone_masked': masked_phone,
                        'kaleyra_status': status
                    },
                    client_ip=client_ip,
                    user_agent=user_agent,
                    session_id=session_id
                )
                return {
                    'success': True,
                    'message': 'SMS sent successfully',
                    'phone_masked': masked_phone
                }
        
        # If we get here, SMS might not have been sent
        write_logs_task.delay(
            log_level='WARNING',
            message=f'SMS may not have been sent to {masked_phone}',
            module_name=module_name,
            url=None,
            request_id=request_id,
            response_id=None,
            user_id=user_id,
            extra_data={
                'action': 'send_sms_warning',
                'phone_masked': masked_phone,
                'kaleyra_response': result
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        return {
            'success': False,
            'message': 'SMS sending status unclear',
            'phone_masked': masked_phone
        }
        
    except ValueError as e:
        # Invalid phone number format
        write_logs_task.delay(
            log_level='ERROR',
            message=f'Invalid phone number format: {str(e)}',
            module_name=module_name,
            url=None,
            request_id=request_id,
            response_id=None,
            user_id=user_id,
            extra_data={
                'action': 'send_sms_error',
                'error': str(e),
                'phone_input': phone_number[:4] + '****' if len(phone_number) > 4 else '****'
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        return {
            'success': False,
            'message': f'Invalid phone number: {str(e)}',
            'error': 'invalid_phone_format'
        }
    except Exception as e:
        # Log error and retry
        masked_phone = phone_number[:4] + '****' + phone_number[-4:] if len(phone_number) > 8 else '****'
        write_logs_task.delay(
            log_level='ERROR',
            message=f'Error sending SMS to {masked_phone}: {str(e)}',
            module_name=module_name,
            url=None,
            request_id=request_id,
            response_id=None,
            user_id=user_id,
            extra_data={
                'action': 'send_sms_error',
                'error': str(e),
                'phone_masked': masked_phone,
                'retry_count': self.request.retries
            },
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
