"""
ParkPe log system – write LogEntry so backend log screen shows ParkPe frontend activity.
Categories: parkpe_auth, parkpe_bbps, parkpe_voucher.
Logs can include request (method + body/params) and response so backend log screen shows what was sent and received.
"""
import json
from typing import Any, Dict, Optional

from portal.models import LogEntry

# Max length for request/response body stored in extra_data (avoid huge payloads)
MAX_LOG_BODY_LEN = 1500
PARKPE_LOG_CATEGORIES = (
    "parkpe_auth",
    "parkpe_bbps",
    "parkpe_voucher",
    "parkpe_payment",
    "parkpe_connect",
    "parkpe_dashboard",
    "parkpe_fastag",
    "parkpe_challan",
    "parkpe_general",
)


def _get_client_ip(request) -> Optional[str]:
    try:
        from portal.utils.ip_utils import get_client_ip
        return get_client_ip(request) if request else None
    except Exception:
        return None


def _get_user_agent(request) -> Optional[str]:
    try:
        from portal.utils.ip_utils import get_user_agent
        return get_user_agent(request) if request else None
    except Exception:
        return None


def _sanitize_body_for_log(data: Any, max_len: int = MAX_LOG_BODY_LEN, *, mask_sensitive: bool = True) -> str:
    """Convert request/response to string for log; optionally mask sensitive keys; truncate."""
    if data is None:
        return ""
    try:
        if isinstance(data, dict):
            copy = dict(data)
            if mask_sensitive:
                for key in list(copy.keys()):
                    k = key.lower() if isinstance(key, str) else ""
                    if "pin" in k or "password" in k or "secret" in k or "token" in k:
                        copy[key] = "***"
                    elif key in ("consumerId", "customer_id", "consumer_id", "connectionId"):
                        v = copy[key]
                        if isinstance(v, str) and len(v) > 4:
                            copy[key] = "*" * (len(v) - 4) + v[-4:]
                        else:
                            copy[key] = "***"
            try:
                s = json.dumps(copy, default=str, ensure_ascii=False)
            except Exception:
                s = str(copy)
        else:
            s = json.dumps(data, default=str, ensure_ascii=False) if not isinstance(data, str) else str(data)
    except Exception:
        s = str(data) if data is not None else ""
    return (s[:max_len] + "...") if len(s) > max_len else s


def log_parkpe(
    category: str,
    message: str,
    success: bool,
    request=None,
    extra_data: Optional[Dict[str, Any]] = None,
    log_level: Optional[str] = None,
    url_path: Optional[str] = None,
    request_method: Optional[str] = None,
    request_body: Any = None,
    response_status: Optional[int] = None,
    response_body: Any = None,
    request_id: Optional[str] = None,
    response_id: Optional[str] = None,
) -> None:
    """
    Create a LogEntry for ParkPe frontend activity so it appears in backend log screen.
    category: one of PARKPE_LOG_CATEGORIES
    message: short description (e.g. "Categories", "Fetch bill", "Login success")
    success: True for success, False for failure
    request: Django request (for user, url, client_ip, user_agent, request_id)
    extra_data: optional dict (non-sensitive only)
    request_method: e.g. "GET", "POST"
    request_body: request payload (GET params or POST body) – will be sanitized and truncated
    response_status: HTTP status code of response
    response_body: response payload – will be truncated
    request_id: optional; if not set, taken from request.request_id (middleware)
    response_id: optional; for tracing
    """
    if category not in PARKPE_LOG_CATEGORIES:
        category = "parkpe_general"
    try:
        req_id = request_id if request_id is not None else (getattr(request, "request_id", None) if request else None)
        resp_id = response_id if response_id is not None else (getattr(request, "response_id", None) if request else None)
        extra = dict(extra_data or {}, source="ParkPe")
        if category == "parkpe_bbps" and message:
            msg_lower = message.lower()
            if "fetch bill" in msg_lower:
                extra["api_name"] = "Fetch Bill"
            elif "pay" in msg_lower and "cart" not in msg_lower:
                extra["api_name"] = "Pay Bill"
            elif "payment status" in msg_lower or "status fetch" in msg_lower:
                extra["api_name"] = "Payment Status"
            elif "categor" in msg_lower:
                extra["api_name"] = "Categories"
            elif "operator" in msg_lower or "biller" in msg_lower:
                extra["api_name"] = "Get Operators"
            elif "favorite" in msg_lower or "saved-bill" in msg_lower:
                extra["api_name"] = "Favorites / Saved Bills"
            else:
                extra["api_name"] = message[:40] if len(message) > 40 else message
        if request and getattr(request, "path", None):
            extra["api_url"] = request.path
        if request_method:
            extra["request_method"] = request_method
        # BBPS / FASTag debugging requires raw values in logs (no masking).
        mask_sensitive = category not in ("parkpe_bbps", "parkpe_fastag")
        if request_body is not None:
            extra["request_body"] = _sanitize_body_for_log(request_body, mask_sensitive=mask_sensitive)
        if response_status is not None:
            extra["response_status"] = response_status
        if response_body is not None:
            extra["response_body"] = _sanitize_body_for_log(response_body, mask_sensitive=mask_sensitive)
        level = log_level or ("INFO" if success else "ERROR")
        LogEntry.objects.create(
            log_level=level,
            category=category,
            message=(message or "ParkPe")[:500],
            module_name="api.parkpe",
            url=(url_path or (request.path if request else None))[:500] if (url_path or request) else None,
            user=request.user if request and getattr(request, "user", None) and request.user.is_authenticated else None,
            client_ip=_get_client_ip(request),
            user_agent=_get_user_agent(request),
            extra_data=extra,
            request_id=req_id,
            response_id=resp_id,
        )
    except Exception:
        pass
