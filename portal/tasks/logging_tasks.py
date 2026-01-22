"""
Celery tasks for logging operations
"""
from celery import shared_task
from django.contrib.auth import get_user_model
from typing import Optional, Dict, Any
from portal.utils.logging_helper import SecureLogger, get_logger

User = get_user_model()


@shared_task(name='portal.tasks.log_user_action')
def log_user_action_task(
    action: str,
    user_id: Optional[int] = None,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: str = 'success',
    extra_data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
):
    """
    Celery task to log user action asynchronously
    
    Args:
        action: Action performed
        user_id: User ID
        resource: Resource type
        resource_id: Resource ID
        status: Action status
        extra_data: Additional data
        request_id: Request ID for tracing
    """
    logger = get_logger('portal.tasks')
    
    try:
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User with ID {user_id} not found for logging", request_id=request_id)
        
        logger.log_user_action(
            action=action,
            user=user,
            resource=resource,
            resource_id=resource_id,
            status=status,
            extra_data=extra_data,
            request_id=request_id
        )
        
        return {'status': 'success', 'action': action}
    except Exception as e:
        logger.error(
            f"Error logging user action: {str(e)}",
            extra_data={'action': action, 'error': str(e)},
            request_id=request_id,
            traceback=str(e)
        )
        raise


@shared_task(name='portal.tasks.log_api_call')
def log_api_call_task(
    service: str,
    endpoint: str,
    method: str = 'POST',
    status_code: Optional[int] = None,
    response_time: Optional[float] = None,
    user_id: Optional[int] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
):
    """
    Celery task to log API call asynchronously
    
    Args:
        service: Service name
        endpoint: API endpoint
        method: HTTP method
        status_code: Response status code
        response_time: Response time in seconds
        user_id: User ID (optional)
        extra_data: Additional data
        request_id: Request ID for tracing
    """
    logger = get_logger('portal.tasks')
    
    try:
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        logger.log_api_call(
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time,
            user=user,
            extra_data=extra_data,
            request_id=request_id
        )
        
        return {'status': 'success', 'service': service, 'endpoint': endpoint}
    except Exception as e:
        logger.error(
            f"Error logging API call: {str(e)}",
            extra_data={'service': service, 'endpoint': endpoint, 'error': str(e)},
            request_id=request_id,
            traceback=str(e)
        )
        raise


@shared_task(name='portal.tasks.log_security_event')
def log_security_event_task(
    event_type: str,
    message: str,
    user_id: Optional[int] = None,
    severity: str = 'medium',
    extra_data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
):
    """
    Celery task to log security event asynchronously
    
    Args:
        event_type: Event type
        message: Event message
        user_id: User ID (optional)
        severity: Severity level
        extra_data: Additional data
        request_id: Request ID for tracing
    """
    logger = get_logger('portal.tasks')
    
    try:
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        logger.log_security_event(
            event_type=event_type,
            message=message,
            user=user,
            severity=severity,
            extra_data=extra_data,
            request_id=request_id
        )
        
        return {'status': 'success', 'event_type': event_type}
    except Exception as e:
        logger.error(
            f"Error logging security event: {str(e)}",
            extra_data={'event_type': event_type, 'error': str(e)},
            request_id=request_id,
            traceback=str(e)
        )
        raise


@shared_task(name='portal.tasks.log_generic')
def log_generic_task(
    level: str,
    message: str,
    user_id: Optional[int] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    traceback: Optional[str] = None
):
    """
    Generic Celery task to log any message asynchronously
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        user_id: User ID (optional)
        extra_data: Additional data
        request_id: Request ID for tracing
        traceback: Traceback string (optional)
    """
    logger = get_logger('portal.tasks')
    
    try:
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(
            message=message,
            user=user,
            extra_data=extra_data,
            request_id=request_id
        )
        
        return {'status': 'success', 'level': level}
    except Exception as e:
        # Fallback to basic logging if secure logger fails
        logger.error(
            f"Error in generic log task: {str(e)}",
            extra_data={'level': level, 'error': str(e)},
            request_id=request_id,
            traceback=traceback or str(e)
        )
        raise


@shared_task(name='portal.tasks.batch_log_cleanup')
def batch_log_cleanup_task(days_to_keep: int = 30):
    """
    Celery task to clean up old logs (if stored in database)
    
    Args:
        days_to_keep: Number of days to keep logs
    """
    logger = get_logger('portal.tasks')
    
    try:
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        # This is a placeholder - implement based on your log storage
        # If logs are stored in database, delete old entries
        # If logs are in files, archive or delete old files
        
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Example: If you have a Log model
        # from portal.models import Log
        # deleted_count = Log.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        logger.info(
            f"Log cleanup completed: keeping logs from last {days_to_keep} days",
            extra_data={'days_to_keep': days_to_keep, 'cutoff_date': cutoff_date.isoformat()}
        )
        
        return {'status': 'success', 'days_to_keep': days_to_keep}
    except Exception as e:
        logger.error(
            f"Error in log cleanup task: {str(e)}",
            traceback=str(e)
        )
        raise
