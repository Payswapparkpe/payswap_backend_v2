"""
Unified Logging Service
Single service for all logging operations in the project
Routes everything through write_logs_task for consistency
"""
from typing import Optional, Dict, Any, Union
from django.http import HttpRequest, HttpResponse
from django.contrib.auth import get_user_model
import json
import traceback
import time

User = get_user_model()


class UnifiedLoggingService:
    """
    Unified logging service that provides a single interface for all logging needs
    
    Features:
    - Automatic context extraction (IP, user agent, session, request ID)
    - Request/response body capture and sanitization
    - Consistent routing through write_logs_task
    - Support for user actions, API calls, service operations, errors
    """
    
    # Maximum size for request/response bodies (10KB)
    MAX_BODY_SIZE = 10 * 1024  # 10KB
    
    def __init__(self):
        """Initialize the unified logging service"""
        pass
    
    def _extract_context(self, request: Optional[HttpRequest] = None) -> Dict[str, Any]:
        """
        Extract context information from request
        
        Args:
            request: Django request object
            
        Returns:
            Dictionary with context information
        """
        from portal.utils.logging_utils import get_request_id, generate_response_id
        from portal.utils.ip_utils import get_client_ip, get_user_agent, get_session_id
        
        context = {
            'request_id': None,
            'response_id': generate_response_id(),
            'client_ip': None,
            'user_agent': None,
            'session_id': None,
            'url': None,
            'user_id': None,
        }
        
        if request:
            context['request_id'] = get_request_id(request)
            context['client_ip'] = get_client_ip(request)
            context['user_agent'] = get_user_agent(request)
            context['session_id'] = get_session_id(request)
            context['url'] = request.path if hasattr(request, 'path') else None
            
            # Extract user ID
            if hasattr(request, 'user') and request.user.is_authenticated:
                context['user_id'] = request.user.id
        
        return context
    
    def _sanitize_body(self, body: Union[str, bytes, dict], max_size: Optional[int] = None) -> Optional[str]:
        """
        Sanitize and truncate request/response body
        
        Args:
            body: Body content (string, bytes, or dict)
            max_size: Maximum size in bytes (defaults to MAX_BODY_SIZE)
            
        Returns:
            Sanitized body string or None
        """
        from portal.utils.logging_helper import sanitize_sensitive_data
        
        if body is None:
            return None
        
        max_size = max_size or self.MAX_BODY_SIZE
        
        # Convert to string if bytes
        if isinstance(body, bytes):
            try:
                body = body.decode('utf-8', errors='ignore')
            except Exception:
                return '[Binary content]'
        
        # Convert dict to JSON string
        if isinstance(body, dict):
            try:
                # Sanitize dict first
                body = sanitize_sensitive_data(body)
                body = json.dumps(body, default=str, ensure_ascii=False)
            except Exception:
                body = str(body)
        
        # Ensure it's a string
        body = str(body)
        
        # Truncate if too large
        if len(body) > max_size:
            body = body[:max_size] + f'... [truncated, total size: {len(body)} bytes]'
        
        # Parse and sanitize JSON if applicable
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                parsed = sanitize_sensitive_data(parsed)
                body = json.dumps(parsed, default=str, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            # Not JSON, just sanitize as string
            pass
        
        return body
    
    def _extract_request_body(self, request: HttpRequest) -> Optional[str]:
        """
        Extract and sanitize request body
        
        Args:
            request: Django request object
            
        Returns:
            Sanitized request body string or None
        """
        if not request:
            return None
        
        # Only capture body for POST/PUT/PATCH/DELETE
        if request.method not in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return None
        
        try:
            # Try to read request body
            if hasattr(request, 'body'):
                body = request.body
                return self._sanitize_body(body)
            
            # Try request.POST for form data
            if hasattr(request, 'POST') and request.POST:
                body_dict = dict(request.POST)
                return self._sanitize_body(body_dict)
            
            # Try request.data for DRF
            if hasattr(request, 'data') and request.data:
                return self._sanitize_body(dict(request.data))
        
        except Exception as e:
            return f'[Error extracting request body: {str(e)}]'
        
        return None
    
    def _extract_response_body(self, response: HttpResponse) -> Optional[str]:
        """
        Extract and sanitize response body
        
        Args:
            response: Django/DRF response object
            
        Returns:
            Sanitized response body string or None
        """
        if not response:
            return None
        
        try:
            # Try DRF response data
            if hasattr(response, 'data'):
                return self._sanitize_body(response.data)
            
            # Try response content
            if hasattr(response, 'content'):
                content = response.content
                # Only capture if content-type is text/JSON
                content_type = response.get('Content-Type', '')
                if any(t in content_type.lower() for t in ['json', 'text', 'html']):
                    return self._sanitize_body(content)
        
        except Exception as e:
            return f'[Error extracting response body: {str(e)}]'
        
        return None
    
    def log_request_response(
        self,
        request: HttpRequest,
        response: HttpResponse,
        request_body: Optional[str] = None,
        response_body: Optional[str] = None,
        log_level: str = 'INFO'
    ):
        """
        Log HTTP request and response with bodies
        
        Args:
            request: Django request object
            response: Django response object
            request_body: Pre-extracted request body (optional)
            response_body: Pre-extracted response body (optional)
            log_level: Log level (defaults to INFO)
        """
        from portal.tasks.write_logs_task import write_logs_task
        
        # Extract context
        context = self._extract_context(request)
        
        # Extract bodies if not provided
        if request_body is None:
            request_body = self._extract_request_body(request)
        
        if response_body is None:
            response_body = self._extract_response_body(response)
        
        # Build extra data
        extra_data = {
            'method': request.method,
            'status_code': response.status_code if response else None,
            'request_body': request_body,
            'response_body': response_body,
        }
        
        # Add query parameters
        if hasattr(request, 'GET') and request.GET:
            extra_data['query_params'] = dict(request.GET)
        
        # Build message
        message = f"{request.method} {context['url']}"
        if response:
            message += f" - {response.status_code}"
        
        # Log via write_logs_task
        write_logs_task.delay(
            log_level=log_level,
            message=message,
            module_name='portal.services.unified_logging',
            url=context['url'],
            request_id=context['request_id'],
            response_id=context['response_id'],
            user_id=context['user_id'],
            extra_data=extra_data,
            client_ip=context['client_ip'],
            user_agent=context['user_agent'],
            session_id=context['session_id']
        )
    
    def log_user_action(
        self,
        action: str,
        user: Optional[Any] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = 'success',
        extra_data: Optional[Dict[str, Any]] = None,
        request: Optional[HttpRequest] = None,
        async_log: bool = True
    ):
        """
        Log user action
        
        Args:
            action: Action name (e.g., 'create_user', 'update_profile')
            user: User object or None
            resource: Resource type (e.g., 'user', 'profile', 'wallet')
            resource_id: Resource ID
            status: Action status ('success', 'failed', 'pending')
            extra_data: Additional data dictionary
            request: Django request object (for context)
            async_log: Whether to log asynchronously (default True)
        """
        from portal.tasks.write_logs_task import write_logs_task
        
        # Extract context
        context = self._extract_context(request)
        
        # Extract user ID
        user_id = context['user_id']
        if user and hasattr(user, 'id'):
            user_id = user.id
        
        # Build action data
        action_data = {
            'action': action,
            'resource': resource,
            'resource_id': resource_id,
            'status': status,
        }
        
        if extra_data:
            action_data.update(extra_data)
        
        # Determine log level
        log_level = 'INFO' if status == 'success' else 'WARNING'
        
        # Build message
        message = f"User action: {action}"
        if resource:
            message += f" on {resource}"
        if resource_id:
            message += f" (ID: {resource_id})"
        message += f" - {status}"
        
        # Log via write_logs_task
        if async_log:
            write_logs_task.delay(
                log_level=log_level,
                message=message,
                module_name='portal.services.unified_logging',
                url=context['url'],
                request_id=context['request_id'],
                response_id=context['response_id'],
                user_id=user_id,
                extra_data=action_data,
                client_ip=context['client_ip'],
                user_agent=context['user_agent'],
                session_id=context['session_id']
            )
        else:
            write_logs_task(
                log_level=log_level,
                message=message,
                module_name='portal.services.unified_logging',
                url=context['url'],
                request_id=context['request_id'],
                response_id=context['response_id'],
                user_id=user_id,
                extra_data=action_data,
                client_ip=context['client_ip'],
                user_agent=context['user_agent'],
                session_id=context['session_id']
            )
    
    def log_api_call(
        self,
        service: str,
        endpoint: str,
        method: str = 'POST',
        request_payload: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
        response_time: Optional[float] = None,
        user: Optional[Any] = None,
        request: Optional[HttpRequest] = None,
        error_message: Optional[str] = None,
        async_log: bool = True
    ):
        """
        Log external API call
        
        Args:
            service: Service name (e.g., 'kaleyra', 'cashfree', 'leegality')
            endpoint: API endpoint
            method: HTTP method
            request_payload: Request payload (will be sanitized)
            response_data: Response data (will be sanitized)
            status_code: HTTP status code
            response_time: Response time in seconds
            user: User object or None
            request: Django request object (for context)
            error_message: Error message if failed
            async_log: Whether to log asynchronously (default True)
        """
        from portal.tasks.write_logs_task import write_logs_task
        from portal.utils.logging_helper import sanitize_sensitive_data
        
        # Extract context
        context = self._extract_context(request)
        
        # Extract user ID
        user_id = context['user_id']
        if user and hasattr(user, 'id'):
            user_id = user.id
        
        # Build API data
        api_data = {
            'service': service,
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'response_time_ms': response_time * 1000 if response_time else None,
        }
        
        # Add request payload (sanitized)
        if request_payload:
            api_data['request_payload'] = sanitize_sensitive_data(request_payload)
        
        # Add response data (sanitized)
        if response_data:
            api_data['response_data'] = sanitize_sensitive_data(response_data)
        
        # Add error message if present
        if error_message:
            api_data['error_message'] = error_message
        
        # Determine log level
        if error_message or (status_code and status_code >= 400):
            log_level = 'ERROR'
        else:
            log_level = 'INFO'
        
        # Build message
        message = f"API call: {method} {service}/{endpoint}"
        if status_code:
            message += f" - {status_code}"
        if response_time:
            message += f" ({response_time:.2f}s)"
        if error_message:
            message += f" - {error_message}"
        
        # Log via write_logs_task
        if async_log:
            write_logs_task.delay(
                log_level=log_level,
                message=message,
                module_name=f'portal.services.vendors.{service}',
                url=context['url'],
                request_id=context['request_id'],
                response_id=context['response_id'],
                user_id=user_id,
                extra_data=api_data,
                client_ip=context['client_ip'],
                user_agent=context['user_agent'],
                session_id=context['session_id']
            )
        else:
            write_logs_task(
                log_level=log_level,
                message=message,
                module_name=f'portal.services.vendors.{service}',
                url=context['url'],
                request_id=context['request_id'],
                response_id=context['response_id'],
                user_id=user_id,
                extra_data=api_data,
                client_ip=context['client_ip'],
                user_agent=context['user_agent'],
                session_id=context['session_id']
            )
    
    def log_service_operation(
        self,
        service_name: str,
        operation: str,
        user: Optional[Any] = None,
        status: str = 'success',
        extra_data: Optional[Dict[str, Any]] = None,
        request: Optional[HttpRequest] = None,
        async_log: bool = True
    ):
        """
        Log service operation
        
        Args:
            service_name: Service name (e.g., 'VoucherService', 'TicketService')
            operation: Operation name (e.g., 'create_voucher', 'assign_ticket')
            user: User object or None
            status: Operation status ('started', 'success', 'failed')
            extra_data: Additional data dictionary
            request: Django request object (for context)
            async_log: Whether to log asynchronously (default True)
        """
        from portal.tasks.write_logs_task import write_logs_task
        
        # Extract context
        context = self._extract_context(request)
        
        # Extract user ID
        user_id = context['user_id']
        if user and hasattr(user, 'id'):
            user_id = user.id
        
        # Build operation data
        operation_data = {
            'service': service_name,
            'operation': operation,
            'status': status,
        }
        
        if extra_data:
            operation_data.update(extra_data)
        
        # Determine log level
        if status == 'failed':
            log_level = 'ERROR'
        elif status == 'started':
            log_level = 'DEBUG'
        else:
            log_level = 'INFO'
        
        # Build message
        message = f"Service operation: {service_name}.{operation} - {status}"
        
        # Log via write_logs_task
        if async_log:
            write_logs_task.delay(
                log_level=log_level,
                message=message,
                module_name=f'portal.services.{service_name.lower()}',
                url=context['url'],
                request_id=context['request_id'],
                response_id=context['response_id'],
                user_id=user_id,
                extra_data=operation_data,
                client_ip=context['client_ip'],
                user_agent=context['user_agent'],
                session_id=context['session_id']
            )
        else:
            write_logs_task(
                log_level=log_level,
                message=message,
                module_name=f'portal.services.{service_name.lower()}',
                url=context['url'],
                request_id=context['request_id'],
                response_id=context['response_id'],
                user_id=user_id,
                extra_data=operation_data,
                client_ip=context['client_ip'],
                user_agent=context['user_agent'],
                session_id=context['session_id']
            )
    
    def log_error(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        user: Optional[Any] = None,
        request: Optional[HttpRequest] = None,
        async_log: bool = True
    ):
        """
        Log error/exception
        
        Args:
            exception: Exception object
            context: Context dictionary (operation details, parameters, etc.)
            user: User object or None
            request: Django request object (for context)
            async_log: Whether to log asynchronously (default True)
        """
        from portal.tasks.write_logs_task import write_logs_task
        
        # Extract context
        req_context = self._extract_context(request)
        
        # Extract user ID
        user_id = req_context['user_id']
        if user and hasattr(user, 'id'):
            user_id = user.id
        
        # Get traceback
        tb_str = traceback.format_exc()
        
        # Build error data
        error_data = {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'traceback': tb_str,
        }
        
        if context:
            error_data['context'] = context
        
        # Build message
        message = f"Error: {type(exception).__name__} - {str(exception)}"
        
        # Log via write_logs_task
        if async_log:
            write_logs_task.delay(
                log_level='ERROR',
                message=message,
                module_name='portal.services.unified_logging',
                url=req_context['url'],
                request_id=req_context['request_id'],
                response_id=req_context['response_id'],
                user_id=user_id,
                extra_data=error_data,
                client_ip=req_context['client_ip'],
                user_agent=req_context['user_agent'],
                session_id=req_context['session_id']
            )
        else:
            write_logs_task(
                log_level='ERROR',
                message=message,
                module_name='portal.services.unified_logging',
                url=req_context['url'],
                request_id=req_context['request_id'],
                response_id=req_context['response_id'],
                user_id=user_id,
                extra_data=error_data,
                client_ip=req_context['client_ip'],
                user_agent=req_context['user_agent'],
                session_id=req_context['session_id']
            )


# Convenience function for getting an instance
def get_unified_logger() -> UnifiedLoggingService:
    """Get an instance of the unified logging service"""
    return UnifiedLoggingService()
