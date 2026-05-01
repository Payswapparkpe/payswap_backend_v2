"""
Production monitoring: /internal/health/ — DB, Redis.
Internal run-job: POST /internal/run-job/ — run management command (Super Admin only).
Restrict by IP or auth in production.
"""
import json
import time
import hmac
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required


def get_health_payload():
    """
    Run internal health checks (DB, Redis). Returns same dict as GET /internal/health/.
    Used by the endpoint and by Control Tower for summarized health.
    """
    start = time.monotonic()
    payload = {"status": "ok", "checks": {}}

    # DB
    try:
        from django.db import connection
        with connection.cursor() as c:
            c.execute("SELECT 1")
        payload["checks"]["db"] = "ok"
    except Exception as e:
        payload["checks"]["db"] = f"error:{str(e)[:100]}"
        payload["status"] = "degraded"

    # Redis
    try:
        from django.core.cache import cache
        cache.set("health_ping", 1, 5)
        if cache.get("health_ping") != 1:
            payload["checks"]["redis"] = "error:read_back_failed"
            payload["status"] = "degraded"
        else:
            payload["checks"]["redis"] = "ok"
    except Exception as e:
        payload["checks"]["redis"] = f"error:{str(e)[:100]}"
        payload["status"] = "degraded"

    payload["latency_ms"] = round((time.monotonic() - start) * 1000, 2)
    return payload


def _check_internal_token(request) -> bool:
    """Validate X-Internal-Token header against INTERNAL_HEALTH_TOKEN env var."""
    from core.config import payswap_config
    expected = payswap_config.get_internal_health_token()
    if not expected:
        return False
    provided = request.headers.get("X-Internal-Token", "").strip()
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


@method_decorator([require_GET, never_cache], name="dispatch")
class InternalHealthView(View):
    """
    GET /internal/health/
    Requires X-Internal-Token header matching INTERNAL_HEALTH_TOKEN env var.
    Returns: db, redis, latency_ms.
    """

    def get(self, request):
        if not _check_internal_token(request):
            return JsonResponse({"error": "Unauthorized"}, status=401)
        payload = get_health_payload()
        status_code = 200 if payload["status"] == "ok" else 503
        return JsonResponse(payload, status=status_code)


@method_decorator([csrf_protect, login_required, require_http_methods(["POST"])], name="dispatch")
class InternalRunJobView(View):
    """
    POST /internal/run-job/
    Body: {"command": "audit_partners"} (JSON).
    Requires session auth + CSRF. Only Super Admin (or is_super_admin) may call.
    Returns: {"run_id": int, "status": "running"|"success"|"failed", "output_preview": "...", "async": bool}.
    """

    def post(self, request):
        from portal.utils.staff_utils import is_super_admin
        from api.internal.run_job import run_command_sync, ALLOWED_COMMANDS

        if not is_super_admin(request.user):
            return JsonResponse({"success": False, "message": "Access denied"}, status=403)

        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

        command_name = (body.get("command") or request.POST.get("command") or "").strip()
        if not command_name:
            return JsonResponse({"success": False, "message": "Missing 'command'"}, status=400)

        if command_name not in ALLOWED_COMMANDS:
            return JsonResponse({"success": False, "message": f"Command not allowed: {command_name}"}, status=400)

        dry_run = body.get("dry_run") or request.POST.get("dry_run") in ("on", "true", "1")
        success, message, output = run_command_sync(command_name, dry_run=dry_run)
        return JsonResponse({
            "success": success,
            "status": "success" if success else "failed",
            "async": False,
            "message": message,
            "output_preview": output[:500],
        })
