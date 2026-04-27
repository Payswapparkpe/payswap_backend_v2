"""
ParkPe action audit middleware.

Creates LogEntry rows for ParkPe API request/response so every action is traceable
service-wise, including failures.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict

from django.utils.deprecation import MiddlewareMixin

from portal.models import LogEntry


_MAX_BODY_LEN = 2000


class ParkPeActionAuditMiddleware(MiddlewareMixin):
    """Log ParkPe API actions with service-specific category."""

    def process_request(self, request):
        request._parkpe_audit_start = time.time()
        return None

    def process_response(self, request, response):
        try:
            # Endpoints with explicit business logs can opt out to avoid duplicate audit rows.
            if getattr(request, "_skip_parkpe_audit_log", False):
                return response
            path = getattr(request, "path", "") or ""
            if path.startswith("/api/v1/logging/track-click/"):
                return response
            category = self._resolve_category(path)
            if not category:
                return response

            method = getattr(request, "method", "GET")
            status_code = getattr(response, "status_code", 0)
            success = 200 <= int(status_code) < 400

            request_payload = self._extract_request_payload(request)
            response_payload = self._extract_response_payload(response)
            elapsed_ms = None
            start = getattr(request, "_parkpe_audit_start", None)
            if isinstance(start, (int, float)):
                elapsed_ms = int((time.time() - start) * 1000)

            mask_sensitive = category not in ("parkpe_bbps", "parkpe_fastag")
            extra_data: Dict[str, Any] = {
                "source": "ParkPe",
                "api_url": path,
                "request_method": method,
                "request_body": self._sanitize(request_payload, mask_sensitive=mask_sensitive),
                "response_status": status_code,
                "response_body": self._sanitize(response_payload, mask_sensitive=mask_sensitive),
            }
            if elapsed_ms is not None:
                extra_data["duration_ms"] = elapsed_ms

            message = f"{method} {path} {'success' if success else 'failed'}"
            LogEntry.objects.create(
                log_level="INFO" if success else "ERROR",
                category=category,
                message=message[:500],
                module_name="api.parkpe.audit",
                url=path[:500] if path else None,
                request_id=getattr(request, "request_id", None),
                response_id=getattr(request, "response_id", None),
                user=(
                    request.user
                    if getattr(request, "user", None) is not None
                    and getattr(request.user, "is_authenticated", False)
                    else None
                ),
                client_ip=self._get_client_ip(request),
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:1000],
                extra_data=extra_data,
            )
        except Exception:
            # Never block API response due to audit logging failure.
            pass
        return response

    @staticmethod
    def _resolve_category(path: str) -> str | None:
        if not path.startswith("/api/"):
            return None
        if path.startswith("/api/auth/"):
            return "parkpe_auth"
        if path.startswith("/api/bbps/"):
            return "parkpe_bbps"
        if path.startswith("/api/voucher/"):
            return "parkpe_voucher"
        if path.startswith("/api/payment/"):
            return "parkpe_payment"
        if path.startswith("/api/connect/"):
            return "parkpe_connect"
        if path.startswith("/api/dashboard/"):
            return "parkpe_dashboard"
        if path.startswith("/api/fastag/"):
            return "parkpe_fastag"
        if path.startswith("/api/challan/"):
            return "parkpe_challan"
        return "parkpe_general"

    @staticmethod
    def _extract_request_payload(request):
        method = (getattr(request, "method", "GET") or "GET").upper()
        if method in ("GET", "DELETE"):
            try:
                return dict(request.GET)
            except Exception:
                return {}
        try:
            body = getattr(request, "data", None)
            if body is not None:
                return body
        except Exception:
            pass
        try:
            raw = request.body.decode("utf-8")
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    @staticmethod
    def _extract_response_payload(response):
        try:
            if hasattr(response, "data"):
                return response.data
        except Exception:
            pass
        try:
            content = getattr(response, "content", b"")
            if not content:
                return ""
            text = content.decode("utf-8", errors="ignore")
            ctype = (response.get("Content-Type", "") or "").lower()
            if "application/json" in ctype:
                try:
                    return json.loads(text)
                except Exception:
                    return text
            return text
        except Exception:
            return ""

    @staticmethod
    def _sanitize(data: Any, mask_sensitive: bool = True) -> str:
        try:
            if isinstance(data, dict):
                masked = dict(data)
                if mask_sensitive:
                    for k in list(masked.keys()):
                        key = str(k).lower()
                        if any(s in key for s in ("pin", "password", "secret", "token", "otp")):
                            masked[k] = "***"
                value = json.dumps(masked, default=str, ensure_ascii=False)
            elif isinstance(data, (list, tuple)):
                value = json.dumps(data, default=str, ensure_ascii=False)
            else:
                value = str(data or "")
        except Exception:
            value = str(data or "")
        return (value[:_MAX_BODY_LEN] + "...") if len(value) > _MAX_BODY_LEN else value

    @staticmethod
    def _get_client_ip(request) -> str | None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
