from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from portal.models import (
    ConnectCallLog,
    ConnectMessage,
    ConnectModerationAction,
    ConnectQrOnboardLog,
    ConnectReport,
    ConnectScanLog,
    ConnectThread,
    LogEntry,
    Profile,
    User,
)


def _is_connect_admin(user):
    if not user or not user.is_authenticated:
        return False
    role_code = str(getattr(user, "role_code", "")).lower()
    return bool(user.is_superuser or user.is_staff or role_code in ("super_admin", "admin"))


class ConnectOpsCenterView(TemplateView):
    template_name = "portal/connect/ops_center.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_connect_admin(request.user):
            messages.error(request, "Access denied. Admin role required.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        since_24h = now - timedelta(hours=24)
        since_7d = now - timedelta(days=7)

        ctx["calls_24h"] = ConnectCallLog.objects.filter(created_at__gte=since_24h).count()
        ctx["calls_success_24h"] = ConnectCallLog.objects.filter(created_at__gte=since_24h, success=True).count()
        ctx["scans_24h"] = ConnectScanLog.objects.filter(created_at__gte=since_24h).count()
        ctx["reports_pending"] = ConnectReport.objects.filter(status="pending").count()
        ctx["blocked_users"] = Profile.objects.filter(connect_blocked_until__gt=now).count()
        ctx["active_threads_7d"] = ConnectThread.objects.filter(updated_at__gte=since_7d).count()

        ctx["high_risk_logs"] = LogEntry.objects.filter(
            timestamp__gte=since_24h,
            category="connect_vehicle",
            message__icontains="blocked_by_risk_engine",
        ).order_by("-timestamp")[:50]
        ctx["recent_reports"] = ConnectReport.objects.select_related(
            "reporter_user", "reported_user", "thread"
        ).order_by("-created_at")[:100]
        ctx["moderation_actions"] = ConnectModerationAction.objects.select_related(
            "actor_user", "target_user"
        ).order_by("-created_at")[:100]
        ctx["top_targeted_owners"] = (
            ConnectCallLog.objects.filter(created_at__gte=since_24h, owner_id__isnull=False)
            .values("owner_id")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )

        # Recent QR scans (raw ConnectScanLog) — same source as scans_24h count; visible for ops verification
        ctx["recent_scans"] = (
            ConnectScanLog.objects.select_related("vehicle", "scanned_by")
            .order_by("-created_at")[:100]
        )

        ctx["recent_onboards"] = (
            ConnectQrOnboardLog.objects.select_related("user", "vehicle")
            .order_by("-created_at")[:80]
        )
        ctx["recent_calls"] = ConnectCallLog.objects.order_by("-created_at")[:80]
        ctx["recent_messages"] = (
            ConnectMessage.objects.select_related("thread", "sender", "thread__vehicle")
            .filter(message_type="text")
            .order_by("-created_at")[:80]
        )

        ctx["policy"] = {
            "CONNECT_CALL_MAX_PER_USER_HOUR": getattr(settings, "CONNECT_CALL_MAX_PER_USER_HOUR", 8),
            "CONNECT_CALL_MAX_PER_PHONE_HOUR": getattr(settings, "CONNECT_CALL_MAX_PER_PHONE_HOUR", 12),
            "CONNECT_CALL_MAX_PER_OWNER_HOUR": getattr(settings, "CONNECT_CALL_MAX_PER_OWNER_HOUR", 15),
            "CONNECT_CALL_MAX_PER_FINGERPRINT_HOUR": getattr(settings, "CONNECT_CALL_MAX_PER_FINGERPRINT_HOUR", 10),
            "CONNECT_CALL_MAX_UNIQUE_QR_PER_HOUR": getattr(settings, "CONNECT_CALL_MAX_UNIQUE_QR_PER_HOUR", 5),
            "CONNECT_CHAT_MAX_PER_USER_HOUR": getattr(settings, "CONNECT_CHAT_MAX_PER_USER_HOUR", 80),
            "CONNECT_CHAT_MAX_PER_THREAD_HOUR": getattr(settings, "CONNECT_CHAT_MAX_PER_THREAD_HOUR", 35),
            "CONNECT_CHAT_MAX_PER_RECIPIENT_HOUR": getattr(settings, "CONNECT_CHAT_MAX_PER_RECIPIENT_HOUR", 45),
            "CONNECT_CHAT_MAX_BODY_LENGTH": getattr(settings, "CONNECT_CHAT_MAX_BODY_LENGTH", 500),
            "CONNECT_PROFANITY_CUSTOM_FILE": getattr(settings, "CONNECT_PROFANITY_CUSTOM_FILE", None) or "(unset)",
            "CONNECT_PROFANITY_CUSTOM_FILE_HI": getattr(settings, "CONNECT_PROFANITY_CUSTOM_FILE_HI", None)
            or "(unset)",
            "CONNECT_PROFANITY_AUTO_BLOCK_THRESHOLD": getattr(settings, "CONNECT_PROFANITY_AUTO_BLOCK_THRESHOLD", 0),
            "CONNECT_PROFANITY_AUTO_BLOCK_MINUTES": getattr(settings, "CONNECT_PROFANITY_AUTO_BLOCK_MINUTES", 60),
        }

        req = self.request
        tq = (req.GET.get("timeline_qr") or "").strip()
        tu_raw = (req.GET.get("timeline_user") or "").strip()
        th_raw = (req.GET.get("timeline_hours") or "").strip()
        ctx["timeline_qr_query"] = tq
        ctx["timeline_user_query"] = tu_raw
        ctx["timeline_events"] = []
        ctx["timeline_error"] = None
        try:
            timeline_hours = int(th_raw) if th_raw else 168
        except ValueError:
            timeline_hours = 168
            ctx["timeline_error"] = "Timeline hours must be a number (default 168)."
        timeline_hours = max(1, min(timeline_hours, 720))
        ctx["timeline_hours_value"] = timeline_hours

        from portal.services.connect_ops_timeline import fetch_connect_timeline

        if tq:
            ctx["timeline_events"] = fetch_connect_timeline(
                qr_code=tq, user_id=None, hours=timeline_hours, limit=200
            )
        elif tu_raw:
            try:
                uid = int(tu_raw)
                ctx["timeline_events"] = fetch_connect_timeline(
                    qr_code=None, user_id=uid, hours=timeline_hours, limit=200
                )
            except ValueError:
                ctx["timeline_error"] = "User ID must be an integer."

        return ctx


@require_POST
@login_required
def connect_moderation_action_view(request):
    if not _is_connect_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)

    target_user_id = request.POST.get("target_user_id")
    action = str(request.POST.get("action") or "").strip().lower()
    reason = str(request.POST.get("reason") or "").strip()
    try:
        block_hours = max(1, int(request.POST.get("block_hours") or 24))
    except ValueError:
        block_hours = 24

    if not target_user_id or action not in {
        ConnectModerationAction.ACTION_WARN,
        ConnectModerationAction.ACTION_TEMP_BLOCK,
        ConnectModerationAction.ACTION_PERM_BLOCK,
        ConnectModerationAction.ACTION_UNBLOCK,
    }:
        return JsonResponse({"success": False, "message": "Invalid moderation action."}, status=400)

    target_user = get_object_or_404(User, id=target_user_id)
    profile = getattr(target_user, "profile", None)
    now = timezone.now()

    if action == ConnectModerationAction.ACTION_WARN and profile:
        profile.connect_warning_count = max(0, int(getattr(profile, "connect_warning_count", 0) or 0) + 1)
        profile.save(update_fields=["connect_warning_count"])
    elif action == ConnectModerationAction.ACTION_TEMP_BLOCK and profile:
        profile.connect_blocked_until = now + timedelta(hours=block_hours)
        profile.save(update_fields=["connect_blocked_until"])
    elif action == ConnectModerationAction.ACTION_PERM_BLOCK and profile:
        profile.connect_blocked_until = now + timedelta(days=3650)
        profile.save(update_fields=["connect_blocked_until"])
    elif action == ConnectModerationAction.ACTION_UNBLOCK and profile:
        profile.connect_blocked_until = None
        profile.save(update_fields=["connect_blocked_until"])

    ConnectModerationAction.objects.create(
        actor_user=request.user,
        target_user=target_user,
        action=action,
        reason=reason,
        metadata={"block_hours": block_hours},
    )
    return JsonResponse({"success": True})


@login_required
def connect_ops_analytics_view(request):
    if not _is_connect_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)

    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    calls_total = ConnectCallLog.objects.filter(created_at__gte=since_24h).count()
    calls_success = ConnectCallLog.objects.filter(created_at__gte=since_24h, success=True).count()
    blocked_risk = LogEntry.objects.filter(
        timestamp__gte=since_24h,
        category="connect_vehicle",
        message__icontains="blocked_by_risk_engine",
    ).count()
    reports_pending = ConnectReport.objects.filter(status="pending").count()
    reports_24h = ConnectReport.objects.filter(created_at__gte=since_24h).count()
    unique_reported_24h = ConnectReport.objects.filter(created_at__gte=since_24h).values("reported_user_id").distinct().count()
    scans_24h = ConnectScanLog.objects.filter(created_at__gte=since_24h).count()
    scans_7d = ConnectScanLog.objects.filter(created_at__gte=since_7d).count()
    threads_7d = ConnectThread.objects.filter(updated_at__gte=since_7d).count()
    active_blocks = Profile.objects.filter(connect_blocked_until__gt=now).count()

    return JsonResponse(
        {
            "success": True,
            "metrics": {
                "calls_total_24h": calls_total,
                "calls_success_24h": calls_success,
                "call_success_rate_24h": round((calls_success / calls_total) * 100, 2) if calls_total else 0.0,
                "risk_blocks_24h": blocked_risk,
                "reports_pending": reports_pending,
                "reports_24h": reports_24h,
                "unique_reported_users_24h": unique_reported_24h,
                "scans_24h": scans_24h,
                "scans_7d": scans_7d,
                "active_threads_7d": threads_7d,
                "active_blocks": active_blocks,
            },
            "top_reported_users_7d": list(
                ConnectReport.objects.filter(created_at__gte=since_7d)
                .values("reported_user_id")
                .annotate(total=Count("id"))
                .order_by("-total")[:10]
            ),
            "top_targeted_owners_24h": list(
                ConnectCallLog.objects.filter(created_at__gte=since_24h)
                .exclude(owner_id__isnull=True)
                .values("owner_id")
                .annotate(total=Count("id"), failed=Count("id", filter=Q(success=False)))
                .order_by("-total")[:10]
            ),
        }
    )
