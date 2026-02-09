"""
Celery task to write APILog asynchronously (non-blocking).
"""
from celery import shared_task
from django.utils import timezone


@shared_task(name="api_management.write_api_log", bind=True, max_retries=2)
def write_api_log_task(
    self,
    api_registry_id,
    request_id,
    response_id,
    principal_type,
    user_id,
    api_key_id,
    status_code,
    duration_ms,
    client_ip,
    user_agent,
    request_meta=None,
    response_meta=None,
    error_type=None,
    error_message=None,
):
    from .models import APILog, APIRegistry

    try:
        api_registry = None
        if api_registry_id:
            try:
                api_registry = APIRegistry.objects.get(pk=api_registry_id)
            except APIRegistry.DoesNotExist:
                pass

        from portal.utils.logging_helper import sanitize_sensitive_data
        request_meta = sanitize_sensitive_data(request_meta or {})
        response_meta = sanitize_sensitive_data(response_meta or {})

        APILog.objects.create(
            api_registry=api_registry,
            request_id=request_id,
            response_id=response_id,
            principal_type=principal_type,
            user_id=user_id,
            api_key_id=api_key_id,
            status_code=status_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
            user_agent=(user_agent or "")[:500],
            request_meta=request_meta,
            response_meta=response_meta,
            error_type=error_type,
            error_message=error_message,
        )
        return {"success": True, "request_id": request_id}
    except Exception as e:
        raise self.retry(exc=e, countdown=5)
