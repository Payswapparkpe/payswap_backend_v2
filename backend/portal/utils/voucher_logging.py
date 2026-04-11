"""
VoucherX Logging Helper
Provides centralized logging for all VoucherX operations
"""
from typing import Optional, Dict, Any
import traceback


def log_voucher_operation(
    operation: str,
    log_level: str,
    message: str,
    user_id: Optional[int] = None,
    request=None,
    extra_data: Optional[Dict[str, Any]] = None,
    exception: Optional[Exception] = None
):
    """
    Helper function to log VoucherX operations using the centralized logging system
    
    Args:
        operation: Operation type (e.g., 'voucher_issued', 'batch_created', 'client_created')
        log_level: Log level (INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        user_id: User ID (optional)
        request: Django request object for extracting context (optional)
        extra_data: Additional data to log (optional)
        exception: Exception object if error occurred (optional)
    """
    from portal.tasks.write_logs_task import write_logs_task
    
    # Initialize context data
    context_data = {}
    
    # Extract request context if request is provided
    if request:
        try:
            from portal.utils.logging_helper import (
                get_client_ip, get_user_agent, get_session_id, get_request_id
            )
            context_data = {
                'url': request.path if hasattr(request, 'path') else None,
                'client_ip': get_client_ip(request),
                'user_agent': get_user_agent(request),
                'session_id': get_session_id(request),
                'request_id': get_request_id(request),
            }
        except Exception:
            # If context extraction fails, continue without it
            pass
    
    # Build extra data
    extra = {
        'operation': operation,
        'category': 'gift_voucher',  # Explicitly set category for all VoucherX operations
        **(extra_data or {}),
    }
    
    # Add exception details if present
    if exception:
        extra['exception_type'] = type(exception).__name__
        extra['exception_message'] = str(exception)
        extra['traceback'] = traceback.format_exc()
    
    # Determine module name based on operation
    # This helps categorize logs in the system
    if 'service' in operation or any(x in operation for x in ['issued', 'redeemed', 'validated', 'exported']):
        module_name = 'portal.services.voucher'
    elif 'batch' in operation:
        module_name = 'portal.tasks.voucher'
    elif 'client' in operation:
        module_name = 'portal.services.voucher_client'
    elif 'api' in operation:
        module_name = 'api.v1.voucher'
    else:
        module_name = 'portal.views.voucherx'
    
    # Call write_logs_task asynchronously
    try:
        write_logs_task.delay(
            log_level=log_level.upper(),
            message=message,
            module_name=module_name,
            url=context_data.get('url'),
            request_id=context_data.get('request_id'),
            user_id=user_id,
            extra_data=extra,
            client_ip=context_data.get('client_ip'),
            user_agent=context_data.get('user_agent'),
            session_id=context_data.get('session_id')
        )
    except Exception as log_error:
        # If async logging fails, try to log the error itself
        # This prevents the logging system from breaking the main flow
        import logging
        logger = logging.getLogger('portal.utils.voucher_logging')
        logger.error(f'Failed to log voucher operation: {str(log_error)}')
