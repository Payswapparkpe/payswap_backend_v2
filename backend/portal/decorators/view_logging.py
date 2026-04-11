"""
View Logging Decorator
Automatically logs all view actions (GET, POST, etc.)
"""
from functools import wraps
from typing import Callable
from django.http import HttpRequest


def log_view_action(action: str = None, resource: str = None):
    """
    Decorator to automatically log view actions
    
    Usage:
        @log_view_action(action='view_dashboard', resource='dashboard')
        def get(self, request, *args, **kwargs):
            ...
    
    Args:
        action: Action name (defaults to view method name)
        resource: Resource type (defaults to view name)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from portal.services.unified_logging_service import UnifiedLoggingService
            
            # Extract request and self (view instance)
            request = None
            view_instance = None
            
            # Try to find request in args
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break
                if hasattr(arg, '__class__') and hasattr(arg, 'request'):
                    view_instance = arg
                    if hasattr(arg, 'request'):
                        request = getattr(arg, 'request', None)
                    break
            
            # If not in args, try kwargs
            if request is None:
                request = kwargs.get('request')
            
            # Determine action name
            action_name = action
            if action_name is None:
                action_name = func.__name__
                if view_instance:
                    action_name = f"{view_instance.__class__.__name__}.{func.__name__}"
            
            # Determine resource name
            resource_name = resource
            if resource_name is None and view_instance:
                resource_name = view_instance.__class__.__name__.replace('View', '').lower()
            
            # Get user
            user = None
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
            
            # Log action start
            unified_logger = UnifiedLoggingService()
            unified_logger.log_user_action(
                action=f"{action_name}_started",
                user=user,
                resource=resource_name,
                status='started',
                extra_data={
                    'method': request.method if request else 'unknown',
                    'view_func': func.__name__
                },
                request=request,
                async_log=True
            )
            
            try:
                # Execute the view function
                result = func(*args, **kwargs)
                
                # Log success
                unified_logger.log_user_action(
                    action=action_name,
                    user=user,
                    resource=resource_name,
                    status='success',
                    extra_data={
                        'method': request.method if request else 'unknown',
                        'view_func': func.__name__
                    },
                    request=request,
                    async_log=True
                )
                
                return result
                
            except Exception as e:
                # Log failure
                unified_logger.log_user_action(
                    action=action_name,
                    user=user,
                    resource=resource_name,
                    status='failed',
                    extra_data={
                        'method': request.method if request else 'unknown',
                        'view_func': func.__name__,
                        'error': str(e)
                    },
                    request=request,
                    async_log=True
                )
                
                # Log error details
                unified_logger.log_error(
                    exception=e,
                    context={
                        'action': action_name,
                        'resource': resource_name,
                        'view_func': func.__name__
                    },
                    user=user,
                    request=request,
                    async_log=True
                )
                
                raise
        
        return wrapper
    return decorator


def log_form_submission(form_name: str = None):
    """
    Decorator specifically for form submission views
    
    Usage:
        @log_form_submission(form_name='user_creation_form')
        def post(self, request, *args, **kwargs):
            ...
    
    Args:
        form_name: Name of the form being submitted
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from portal.services.unified_logging_service import UnifiedLoggingService
            from portal.utils.logging_helper import sanitize_sensitive_data
            
            # Extract request
            request = None
            for arg in args:
                if isinstance(arg, HttpRequest):
                    request = arg
                    break
            
            if request is None:
                request = kwargs.get('request')
            
            # Get user
            user = None
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
            
            # Determine form name
            form_name_str = form_name or 'unknown_form'
            
            # Extract form data (sanitized)
            form_data = {}
            if request and hasattr(request, 'POST'):
                form_data = sanitize_sensitive_data(dict(request.POST))
            
            # Log form submission
            unified_logger = UnifiedLoggingService()
            unified_logger.log_user_action(
                action=f"submit_{form_name_str}",
                user=user,
                resource='form',
                resource_id=form_name_str,
                status='started',
                extra_data={
                    'form_name': form_name_str,
                    'form_data': form_data
                },
                request=request,
                async_log=True
            )
            
            try:
                # Execute the view function
                result = func(*args, **kwargs)
                
                # Log success
                unified_logger.log_user_action(
                    action=f"submit_{form_name_str}",
                    user=user,
                    resource='form',
                    resource_id=form_name_str,
                    status='success',
                    extra_data={'form_name': form_name_str},
                    request=request,
                    async_log=True
                )
                
                return result
                
            except Exception as e:
                # Log failure
                unified_logger.log_user_action(
                    action=f"submit_{form_name_str}",
                    user=user,
                    resource='form',
                    resource_id=form_name_str,
                    status='failed',
                    extra_data={
                        'form_name': form_name_str,
                        'error': str(e)
                    },
                    request=request,
                    async_log=True
                )
                
                raise
        
        return wrapper
    return decorator
