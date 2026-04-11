"""
Logging decorators for automatic logging
"""
from functools import wraps
from typing import Callable, Any
from django.contrib.auth import get_user_model
from portal.utils.logging_helper import get_logger
from portal.tasks.logging_tasks import (
    log_user_action_task,
    log_api_call_task,
    log_security_event_task
)

User = get_user_model()


def log_user_action_decorator(
    action: str,
    resource: str = None,
    async_log: bool = True
):
    """
    Decorator to automatically log user actions
    
    Usage:
        @log_user_action_decorator('create_user', resource='user')
        def create_user(request, ...):
            ...
    
    Args:
        action: Action name
        resource: Resource type (optional)
        async_log: Whether to log asynchronously via Celery
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger('portal.decorators')
            request = None
            user = None
            
            # Try to get request from args or kwargs
            for arg in args:
                if hasattr(arg, 'user'):
                    request = arg
                    user = getattr(arg, 'user', None)
                    break
            
            if not request:
                request = kwargs.get('request')
                if request:
                    user = getattr(request, 'user', None)
            
            # Get resource_id from kwargs or return value
            resource_id = kwargs.get('id') or kwargs.get('pk') or kwargs.get('user_id')
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Determine status
                status = 'success'
                if isinstance(result, dict) and result.get('status') == 'error':
                    status = 'failed'
                
                # Log action
                if async_log:
                    log_user_action_task.delay(
                        action=action,
                        user_id=user.id if user and user.is_authenticated else None,
                        resource=resource,
                        resource_id=str(resource_id) if resource_id else None,
                        status=status,
                        extra_data={'function': func.__name__}
                    )
                else:
                    logger.log_user_action(
                        action=action,
                        user=user if user and user.is_authenticated else None,
                        resource=resource,
                        resource_id=str(resource_id) if resource_id else None,
                        status=status
                    )
                
                return result
            except Exception as e:
                # Log error
                if async_log:
                    log_user_action_task.delay(
                        action=action,
                        user_id=user.id if user and user.is_authenticated else None,
                        resource=resource,
                        resource_id=str(resource_id) if resource_id else None,
                        status='failed',
                        extra_data={'function': func.__name__, 'error': str(e)}
                    )
                else:
                    logger.error(
                        f"Error in {func.__name__}: {str(e)}",
                        user=user if user and user.is_authenticated else None,
                        traceback=str(e)
                    )
                raise
        
        return wrapper
    return decorator


def log_api_call_decorator(
    service: str,
    async_log: bool = True
):
    """
    Decorator to automatically log API calls
    
    Usage:
        @log_api_call_decorator('kaleyra')
        def send_otp(phone, otp):
            ...
    
    Args:
        service: Service name
        async_log: Whether to log asynchronously via Celery
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            logger = get_logger('portal.decorators')
            
            start_time = time.time()
            status_code = None
            error = None
            
            try:
                result = func(*args, **kwargs)
                response_time = time.time() - start_time
                
                # Try to extract status code from result
                if isinstance(result, dict):
                    status_code = result.get('status_code') or result.get('status')
                
                # Log API call
                if async_log:
                    log_api_call_task.delay(
                        service=service,
                        endpoint=func.__name__,
                        method='POST',
                        status_code=status_code or 200,
                        response_time=response_time,
                        extra_data={'function': func.__name__}
                    )
                else:
                    logger.log_api_call(
                        service=service,
                        endpoint=func.__name__,
                        method='POST',
                        status_code=status_code or 200,
                        response_time=response_time
                    )
                
                return result
            except Exception as e:
                response_time = time.time() - start_time
                error = str(e)
                
                # Log error
                if async_log:
                    log_api_call_task.delay(
                        service=service,
                        endpoint=func.__name__,
                        method='POST',
                        status_code=500,
                        response_time=response_time,
                        extra_data={'function': func.__name__, 'error': error}
                    )
                else:
                    logger.error(
                        f"API call failed: {service}/{func.__name__}",
                        extra_data={'error': error},
                        traceback=error
                    )
                raise
        
        return wrapper
    return decorator
