from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from portal.models import (
    ConnectCallLog,
    ConnectReport,
    ConnectScanLog,
    FleetWorkspaceInterest,
    NotificationDeliveryLog,
    ParkPePaymentOrder,
    ParkPePaymentGatewayConfig,
    ParkPeServiceConfig,
    ParkPeVoucherTransaction,
    Profile,
    Role,
    ServiceVoucherRefundCase,
    User,
    UserSettingsAuditLog,
    UserNotification,
)


def _is_parkpe_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    role = str(getattr(user, "role_code", "")).lower()
    return bool(user.is_superuser or user.is_staff or role in ("super_admin", "admin"))


class ParkPeControlCenterView(TemplateView):
    template_name = "portal/parkpe/control_center.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_parkpe_admin(request.user):
            messages.error(request, "Access denied. Admin role required.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        since_24h = now - timedelta(hours=24)
        since_7d = now - timedelta(days=7)

        txn_24h = ParkPeVoucherTransaction.objects.filter(created_at__gte=since_24h)
        ctx["voucher_txn_24h"] = txn_24h.count()
        ctx["voucher_volume_24h"] = txn_24h.aggregate(total=Sum("amount")).get("total") or 0

        orders_24h = ParkPePaymentOrder.objects.filter(created_at__gte=since_24h)
        ctx["payment_orders_24h"] = orders_24h.count()
        ctx["payment_success_24h"] = orders_24h.filter(status="SUCCESS").count()
        ctx["payment_pending_24h"] = orders_24h.filter(status__in=["PENDING", "INITIATED"]).count()
        ctx["payment_failed_24h"] = orders_24h.filter(status="FAILED").count()

        ctx["connect_calls_24h"] = ConnectCallLog.objects.filter(created_at__gte=since_24h).count()
        ctx["connect_reports_pending"] = ConnectReport.objects.filter(status="pending").count()
        ctx["connect_scans_24h"] = ConnectScanLog.objects.filter(created_at__gte=since_24h).count()
        ctx["connect_blocks_active"] = Profile.objects.filter(connect_blocked_until__gt=now).count()

        ctx["notifications_unread"] = UserNotification.objects.filter(is_read=False).count()
        ctx["notification_failures_24h"] = NotificationDeliveryLog.objects.filter(
            created_at__gte=since_24h, status=NotificationDeliveryLog.STATUS_FAILED
        ).count()

        ctx["service_configs_enabled"] = ParkPeServiceConfig.objects.filter(is_active=True).count()
        ctx["gateway_configs_enabled"] = ParkPePaymentGatewayConfig.objects.filter(enabled=True).count()

        ctx["top_connect_reported_7d"] = list(
            ConnectReport.objects.filter(created_at__gte=since_7d)
            .values("reported_user_id")
            .annotate(total=Count("id"))
            .order_by("-total")[:8]
        )
        ctx["top_payment_services_7d"] = list(
            ParkPeVoucherTransaction.objects.filter(created_at__gte=since_7d)
            .values("service_code")
            .annotate(total=Count("id"))
            .order_by("-total")[:8]
        )
        ctx["service_voucher_refund_open"] = ServiceVoucherRefundCase.objects.filter(
            status=ServiceVoucherRefundCase.STATUS_OPEN
        ).count()
        return ctx


class ParkPeFleetAccessRequestsView(TemplateView):
    """Portal UI for Fleet workspace interest — same actions as Django admin, without /admin/."""

    template_name = "portal/parkpe/fleet_access_requests.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_parkpe_admin(request.user):
            messages.error(request, "Access denied. Admin role required.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "").strip().lower()
        raw_id = request.POST.get("interest_id")
        try:
            interest_id = int(raw_id)
        except (TypeError, ValueError):
            messages.error(request, "Invalid request.")
            return redirect("parkpe_fleet_access_requests")

        try:
            obj = FleetWorkspaceInterest.objects.select_related("user").get(pk=interest_id)
        except FleetWorkspaceInterest.DoesNotExist:
            messages.error(request, "Request not found.")
            return redirect("parkpe_fleet_access_requests")

        if obj.status != FleetWorkspaceInterest.STATUS_PENDING:
            messages.warning(request, "This request is no longer pending.")
            return redirect("parkpe_fleet_access_requests")

        if action == "reject":
            obj.status = FleetWorkspaceInterest.STATUS_REJECTED
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
            if not obj.rejection_reason:
                obj.rejection_reason = "Rejected in ParkPe Fleet access console."
            obj.save()
            messages.success(request, f"Rejected fleet access request #{obj.id}.")
            return redirect("parkpe_fleet_access_requests")

        if action == "approve":
            code = (obj.assigned_role_code or "fleet_operator").strip()
            try:
                Role.objects.get(code=code)
            except Role.DoesNotExist:
                messages.error(
                    request,
                    f'Role "{code}" does not exist. Run: python manage.py setup_roles',
                )
                return redirect("parkpe_fleet_access_requests")
            try:
                with transaction.atomic():
                    u = User.objects.select_for_update().get(pk=obj.user_id)
                    obj.status = FleetWorkspaceInterest.STATUS_APPROVED
                    obj.reviewed_by = request.user
                    obj.reviewed_at = timezone.now()
                    obj.save()
            except Exception as exc:
                messages.error(request, f"Could not approve: {exc}")
                return redirect("parkpe_fleet_access_requests")
            messages.success(
                request,
                (
                    f"Approved request #{obj.id} for user {u.username}. "
                    f"Fleet workspace access granted without changing portal role."
                ),
            )
            return redirect("parkpe_fleet_access_requests")

        messages.error(request, "Unknown action.")
        return redirect("parkpe_fleet_access_requests")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = FleetWorkspaceInterest.objects.select_related("user", "reviewed_by").order_by("-created_at")[:250]
        ctx["fleet_interests"] = qs
        ctx["fleet_pending_count"] = FleetWorkspaceInterest.objects.filter(
            status=FleetWorkspaceInterest.STATUS_PENDING
        ).count()
        return ctx


class ParkPeSettingsGovernanceView(TemplateView):
    template_name = "portal/parkpe/settings_governance.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_parkpe_admin(request.user):
            messages.error(request, "Access denied. Admin role required.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        since_24h = now - timedelta(hours=24)
        since_7d = now - timedelta(days=7)
        logs_7d = UserSettingsAuditLog.objects.filter(created_at__gte=since_7d)

        ctx["settings_changes_24h"] = UserSettingsAuditLog.objects.filter(created_at__gte=since_24h).count()
        ctx["parkpe_settings_changes_24h"] = UserSettingsAuditLog.objects.filter(
            created_at__gte=since_24h, source=UserSettingsAuditLog.SOURCE_PARKPE
        ).count()
        ctx["hub_settings_changes_24h"] = UserSettingsAuditLog.objects.filter(
            created_at__gte=since_24h, source=UserSettingsAuditLog.SOURCE_HUB
        ).count()
        ctx["sessions_revoked_24h"] = UserSettingsAuditLog.objects.filter(
            created_at__gte=since_24h, action="sessions_revoked"
        ).count()
        ctx["top_changed_users_7d"] = list(
            logs_7d.values("user_id").annotate(total=Count("id")).order_by("-total")[:10]
        )
        ctx["recent_settings_audit"] = logs_7d.select_related("user", "actor_user").order_by("-created_at")[:120]
        return ctx


@login_required
def parkpe_settings_governance_analytics_view(request):
    if not _is_parkpe_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)

    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    logs_24h = UserSettingsAuditLog.objects.filter(created_at__gte=since_24h)
    logs_7d = UserSettingsAuditLog.objects.filter(created_at__gte=since_7d)
    logs_30d = UserSettingsAuditLog.objects.filter(created_at__gte=since_30d)

    return JsonResponse(
        {
            "success": True,
            "metrics": {
                "settings_changes_24h": logs_24h.count(),
                "settings_changes_7d": logs_7d.count(),
                "settings_changes_30d": logs_30d.count(),
                "sessions_revoked_24h": logs_24h.filter(action="sessions_revoked").count(),
                "parkpe_source_24h": logs_24h.filter(source=UserSettingsAuditLog.SOURCE_PARKPE).count(),
                "hub_source_24h": logs_24h.filter(source=UserSettingsAuditLog.SOURCE_HUB).count(),
            },
            "actions_7d": list(
                logs_7d.values("action").annotate(total=Count("id")).order_by("-total")
            ),
            "top_changed_users_7d": list(
                logs_7d.values("user_id").annotate(total=Count("id")).order_by("-total")[:10]
            ),
        }
    )
