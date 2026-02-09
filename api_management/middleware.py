"""
Middleware to record API request/response and enqueue APILog write (async).
Only runs for /api/ requests.
"""
import time

from .registry import get_registry_for_request
from .tasks import write_api_log_task
from .models import APILog


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR") or ""


class APILoggingMiddleware:
    """
    Measures latency and enqueues APILog write via Celery for /api/ requests.
    Attaches request._api_management_start_time in process_request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            request._api_management_start_time = time.time()
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            self._enqueue_log(request, response)
        return response

    def _enqueue_log(self, request, response):
        start = getattr(request, "_api_management_start_time", None)
        duration_ms = (time.time() - start) * 1000.0 if start else None

        registry = get_registry_for_request(request)
        api_registry_id = registry.pk if registry else None

        request_id = getattr(request, "request_id", None) or request.META.get("HTTP_X_REQUEST_ID")
        response_id = response.get("X-Response-ID") if hasattr(response, "get") else None

        principal_type = APILog.PRINCIPAL_ANON
        user_id = None
        api_key_id = None
        if getattr(request, "user", None) and request.user.is_authenticated:
            principal_type = APILog.PRINCIPAL_USER
            user_id = request.user.pk
        elif getattr(request, "api_key_obj", None):
            principal_type = APILog.PRINCIPAL_API_KEY
            api_key_id = request.api_key_obj.pk
        elif getattr(request, "api_key", None):
            principal_type = APILog.PRINCIPAL_API_KEY
            api_key_id = request.api_key.pk

        client_ip = get_client_ip(request)
        user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:500]

        write_api_log_task.delay(
            api_registry_id=api_registry_id,
            request_id=request_id or "",
            response_id=response_id or "",
            principal_type=principal_type,
            user_id=user_id,
            api_key_id=api_key_id,
            status_code=getattr(response, "status_code", None),
            duration_ms=duration_ms,
            client_ip=client_ip,
            user_agent=user_agent,
            request_meta={},
            response_meta={},
            error_type=None,
            error_message=None,
        )
