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
                    elif key in ("voucher_id", "voucherId"):
                        # ParkPe-only; never needed in Hub forensics for Mobikwik
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
    *,
    chain_step: Optional[int] = None,
    log_role: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """
    Create a LogEntry for ParkPe frontend activity so it appears in backend log screen.
    Convention: if an endpoint uses explicit log_parkpe() business logs, set
    request._skip_parkpe_audit_log=True (and DRF request._request too) so audit middleware
    does not add a duplicate generic row for the same request.
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
        trace = (correlation_id or req_id) if (correlation_id or req_id) else None
        if trace and len(str(trace)) > 100:
            trace = str(trace)[:100]
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
        # Always mask PIN, voucher_id, tokens, etc. Mobikwik never receives voucher data;
        # Hub logs must not store voucher PIN or internal voucher ids in plain text.
        mask_sensitive = True
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
            request_id=str(req_id)[:100] if req_id else None,
            response_id=resp_id,
            correlation_id=trace,
            chain_step=chain_step,
            log_role=log_role or ("client" if chain_step == 1 else None),
        )
    except Exception:
        pass


def _truncate_for_log(data: Any, max_len: int = 2000) -> str:
    try:
        s = json.dumps(data, default=str, ensure_ascii=False) if not isinstance(data, str) else data
    except Exception:
        s = str(data) if data is not None else ""
    s = s[:max_len] + ("..." if len(s) > max_len else "")
    return s


def log_instantpay_api_call(
    api_code: str,
    result: Dict[str, Any],
    internal_instantpay_request_id: str,
    *,
    log_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    One LogEntry per Instantpay HTTP flow so /logs/ shows app → Instantpay in series.
    Never raises. correlation_id should match the ParkPe / Hub request when available.
    """
    from portal.models import LogEntry  # local import; instantpay is vendor layer

    log_context = log_context or {}
    correlation = log_context.get("correlation_id") or log_context.get("request_id")
    if correlation and len(str(correlation)) > 100:
        correlation = str(correlation)[:100]
    chain_step = int(log_context.get("chain_step") or 2)
    django_request = log_context.get("request")
    user = log_context.get("user")
    if user is None and django_request and getattr(django_request, "user", None) and django_request.user.is_authenticated:
        user = django_request.user
    ext: Dict[str, Any] = {
        "vendor": "Instantpay",
        "vendor_name": "Instantpay",
        "api_code": api_code,
        "http_status": result.get("status_code"),
        "success": bool(result.get("success")),
        "vendor_status": (str(result.get("vendor_status") or ""))[:200],
        "instantpay_x_request_id": str(internal_instantpay_request_id)[:100],
    }
    if result.get("error"):
        ext["error"] = str(result.get("error"))[:2000]
    if result.get("message"):
        ext["message"] = str(result.get("message"))[:1000]
    if result.get("attempted_path"):
        ext["attempted_path"] = str(result.get("attempted_path"))[:500]
    request_meta = result.get("request_meta")
    if isinstance(request_meta, dict):
        safe_meta: Dict[str, Any] = {}
        for k in (
            "auth_mode",
            "timestamp_sent",
            "auth_code_sha256",
            "auth_code_prefix",
            "auth_code_suffix",
            "header_names",
            "normalized_payload",
        ):
            if request_meta.get(k) is not None:
                safe_meta[k] = request_meta.get(k)
        if safe_meta:
            ext["request_meta"] = safe_meta
    j = result.get("json")
    if isinstance(j, dict):
        ext["response_snippet"] = _truncate_for_log(j, 2000)
    elif result.get("body") is not None:
        ext["response_snippet"] = _truncate_for_log(result.get("body"), 1000)
    level = "INFO" if result.get("success") else "ERROR"
    st = result.get("status_code", "—")
    try:
        LogEntry.objects.create(
            log_level=level,
            category="instantpay",
            message=f"Instantpay {api_code} · HTTP {st}"[:500],
            module_name="portal.services.vendors.instantpay",
            user=user if user and getattr(user, "pk", None) else None,
            client_ip=_get_client_ip(django_request),
            user_agent=_get_user_agent(django_request),
            request_id=correlation,
            correlation_id=correlation,
            chain_step=chain_step,
            log_role="vendor",
            extra_data=ext,
        )
    except Exception:
        pass
