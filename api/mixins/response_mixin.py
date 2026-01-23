"""
API Response Mixin
Provides standardized response methods for all API views
"""
from rest_framework.response import Response
from rest_framework import status
from typing import Optional, Dict, Any, List
from portal.utils.response_utils import format_api_response, format_api_error
from portal.utils.logging_utils import get_request_id, generate_response_id
from portal.utils.ip_utils import get_client_ip, get_user_agent, get_session_id
from portal.tasks.write_logs_task import write_logs_task


class StandardResponseMixin:
    """
    Mixin for standardized API responses
    All API views should inherit from this mixin
    """
    
    def success_response(
        self,
        message: str = "Operation completed successfully",
        data: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_200_OK,
        request=None
    ) -> Response:
        """
        Return standardized success response
        
        Args:
            message: Success message
            data: Response data
            status_code: HTTP status code
            request: Request object (for extracting IDs)
        
        Returns:
            DRF Response object
        """
        request_id = get_request_id(request) if request else None
        response_id = generate_response_id()
        
        response_data = format_api_response(
            success=True,
            message=message,
            data=data,
            request=request,
            request_id=request_id,
            response_id=response_id
        )
        
        # Log successful API response
        if request:
            write_logs_task.delay(
                log_level='INFO',
                message=f'API success: {message}',
                module_name=self.__class__.__module__,
                url=request.path,
                request_id=request_id,
                response_id=response_id,
                user_id=request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                extra_data={'action': 'api_success', 'status_code': status_code},
                client_ip=get_client_ip(request),
                user_agent=get_user_agent(request),
                session_id=get_session_id(request)
            )
        
        response = Response(response_data, status=status_code)
        if request_id:
            response['X-Request-ID'] = request_id
        response['X-Response-ID'] = response_id
        return response
    
    def error_response(
        self,
        message: str = "An error occurred",
        errors: Optional[List[Dict[str, Any]]] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        request=None
    ) -> Response:
        """
        Return standardized error response
        
        Args:
            message: Error message
            errors: List of error details
            status_code: HTTP status code
            request: Request object (for extracting IDs)
        
        Returns:
            DRF Response object
        """
        request_id = get_request_id(request) if request else None
        response_id = generate_response_id()
        
        response_data = format_api_error(
            message=message,
            errors=errors,
            request=request,
            request_id=request_id,
            response_id=response_id
        )
        
        # Log API error
        if request:
            write_logs_task.delay(
                log_level='ERROR',
                message=f'API error: {message}',
                module_name=self.__class__.__module__,
                url=request.path,
                request_id=request_id,
                response_id=response_id,
                user_id=request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                extra_data={
                    'action': 'api_error',
                    'status_code': status_code,
                    'errors': errors
                },
                client_ip=get_client_ip(request),
                user_agent=get_user_agent(request),
                session_id=get_session_id(request)
            )
        
        response = Response(response_data, status=status_code)
        if request_id:
            response['X-Request-ID'] = request_id
        response['X-Response-ID'] = response_id
        return response
