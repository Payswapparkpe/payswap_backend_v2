"""
API Response utility functions
Standardized response formatting for all API endpoints
"""
import uuid
from typing import Optional, Dict, Any, List
from django.http import HttpRequest
from django.utils import timezone
from portal.utils.ip_utils import get_client_ip
from portal.utils.logging_utils import get_request_id, generate_response_id


def format_api_response(
    success: bool = True,
    message: str = "Operation completed successfully",
    data: Optional[Dict[str, Any]] = None,
    errors: Optional[List[Dict[str, Any]]] = None,
    request: Optional[HttpRequest] = None,
    request_id: Optional[str] = None,
    response_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format standard API response
    
    Args:
        success: Whether operation was successful
        message: Response message
        data: Response data (for success)
        errors: List of errors (for failure)
        request: Django request object (for extracting request_id)
        request_id: Request ID (if already extracted)
        response_id: Response ID (if already generated)
    
    Returns:
        Formatted response dictionary
    """
    # Extract/generate IDs
    if not request_id and request:
        request_id = get_request_id(request)
    if not request_id:
        request_id = str(uuid.uuid4())
    
    if not response_id:
        response_id = generate_response_id()
    
    response = {
        'success': success,
        'message': message,
        'request_id': request_id,
        'response_id': response_id,
        'timestamp': timezone.now().isoformat()
    }
    
    if success:
        if data is not None:
            response['data'] = data
    else:
        if errors:
            response['errors'] = errors
        else:
            response['errors'] = [{'message': message}]
    
    return response


def format_api_error(
    message: str,
    errors: Optional[List[Dict[str, Any]]] = None,
    request: Optional[HttpRequest] = None,
    request_id: Optional[str] = None,
    response_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format standard API error response
    
    Args:
        message: Error message
        errors: List of error details
        request: Django request object
        request_id: Request ID (if already extracted)
        response_id: Response ID (if already generated)
    
    Returns:
        Formatted error response dictionary
    """
    return format_api_response(
        success=False,
        message=message,
        errors=errors,
        request=request,
        request_id=request_id,
        response_id=response_id
    )


def extract_request_id(request: HttpRequest) -> str:
    """
    Extract request ID from request headers or generate new one
    
    Args:
        request: Django request object
    
    Returns:
        Request ID string
    """
    request_id = get_request_id(request)
    if not request_id:
        request_id = str(uuid.uuid4())
        request.request_id = request_id
    return request_id
