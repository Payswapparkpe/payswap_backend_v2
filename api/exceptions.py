"""
Custom DRF exception handler and API exceptions.
Standardized API error shape for all API responses.
"""
import uuid

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException

from portal.utils.response_utils import format_api_error
from portal.utils.logging_utils import get_request_id, generate_response_id


class VendorNotAssigned(APIException):
    """Raised when partner has no vendor assigned for the requested service_code. Returns 400."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "No vendor assigned for this service. Contact admin to assign a vendor."
    default_code = "vendor_not_assigned"


def api_exception_handler(exc, context):
    """
    Call DRF default handler first, then convert response to standardized format.
    """
    request = context.get("request")
    request_id = get_request_id(request) if request else str(uuid.uuid4())
    response_id = generate_response_id()

    # VendorNotAssigned → 400 with error code
    if isinstance(exc, VendorNotAssigned):
        message = getattr(exc, "detail", exc.default_detail)
        if hasattr(message, "__iter__") and not isinstance(message, str):
            message = message[0] if message else exc.default_detail
        message = str(message)
        data = format_api_error(
            message=message,
            errors=[{"message": message}],
            request=request,
            request_id=request_id,
            response_id=response_id,
        )
        data["error"] = "vendor_not_assigned"
        return Response(data, status=status.HTTP_400_BAD_REQUEST, headers={
            "X-Request-ID": request_id,
            "X-Response-ID": response_id,
        })

    response = exception_handler(exc, context)
    if response is None:
        return Response(
            format_api_error(
                message="An unexpected server error occurred.",
                errors=[{"message": "Internal server error"}],
                request=request,
                request_id=request_id,
                response_id=response_id,
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={"X-Request-ID": request_id, "X-Response-ID": response_id},
        )

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
