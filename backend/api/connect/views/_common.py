"""
Shared logging and constants for Connect views. No URL or view logic.
"""
import logging

from portal.tasks.write_logs_task import write_logs_task

logger = logging.getLogger("api.connect.vehicle")

CONNECT_SCANNER_OTP_RATE_LIMIT_KEY = "connect_scanner_otp:"
# OTP limit per phone number (10-minute rolling window)
CONNECT_SCANNER_OTP_RATE_LIMIT_COUNT = 5
CONNECT_SCANNER_OTP_RATE_LIMIT_WINDOW = 600  # 10 minutes

CONNECT_CALL_TOKEN_PREFIX = "connect_call_token:"
CONNECT_CALL_TOKEN_TTL = 300  # seconds (5 minutes; tokens are one-use so longer TTL is safe)


def vehicle_log(request, log_level: str, message: str, extra_data: dict | None = None):
    """Emit to Python logger and to DB so it appears at /logs/. Runs sync so logs show even without Celery."""
    extra = extra_data or {}
    extra["category"] = "connect_vehicle"
    level_name = str(log_level or "INFO").upper()
    log_method = getattr(logger, level_name.lower(), logger.info)
    log_method(message, extra=extra)
    kwargs = dict(
        log_level=level_name,
        message=message,
        module_name="api.connect.vehicle",
        url=getattr(request, "path", None) if request else None,
        user_id=getattr(request.user, "pk", None) if request and getattr(request, "user", None) else None,
        extra_data=extra,
    )
    try:
        write_logs_task.apply(kwargs=kwargs)
    except Exception:
        write_logs_task.delay(**kwargs)
