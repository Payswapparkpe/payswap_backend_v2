"""
Custom DRF exception handler that returns standardized API error shape
(portal.utils.response_utils.format_api_error) for all API responses.
"""
import uuid

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

from portal.utils.response_utils import format_api_error
from portal.utils.logging_utils import get_request_id, generate_response_id


def api_management_exception_handler(exc, context):
    """
    Call DRF default handler first, then convert response to standardized format.
    """
    response = exception_handler(exc, context)
    request = context.get("request")

    if response is None:
        return response

    request_id = get_request_id(request) if request else str(uuid.uuid4())
    response_id = generate_response_id()

    message = "An error occurred"
    errors = []
    if hasattr(exc, "detail"):
        detail = exc.detail
        if isinstance(detail, list):
            errors = [{"message": str(d)} for d in detail]
            message = errors[0]["message"] if errors else message
        elif isinstance(detail, dict):
            errors = [{"field": k, "message": str(v)} for k, v in detail.items()]
            message = detail.get("message", str(detail)) if isinstance(detail.get("message"), str) else str(detail)
        else:
            message = str(detail)
            errors = [{"message": message}]

    data = format_api_error(
        message=message,
        errors=errors or [{"message": message}],
        request=request,
        request_id=request_id,
        response_id=response_id,
    )

    return Response(data, status=response.status_code, headers={
        "X-Request-ID": request_id,
        "X-Response-ID": response_id,
    })
