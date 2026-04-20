from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from portal.models import ServiceVoucherRefundCase
from portal.services.service_voucher_refund_service import (
    dismiss_service_voucher_refund_case,
    execute_service_voucher_refund,
)
from portal.views.parkpe_hub_views import _is_parkpe_admin


@method_decorator(login_required, name="dispatch")
class ServiceVoucherRefundQueueView(TemplateView):
    """Admin queue: voucher debits where service failed (e.g. RC API) — refund or dismiss with narration."""

    template_name = "portal/parkpe/service_voucher_refund_queue.html"

    def dispatch(self, request, *args, **kwargs):
        if not _is_parkpe_admin(request.user):
            messages.error(request, "Access denied. Admin role required.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "").strip().lower()
        raw_id = request.POST.get("case_id")
        try:
            case_id = int(raw_id)
        except (TypeError, ValueError):
            messages.error(request, "Invalid case.")
            return redirect("service_voucher_refund_queue")

        try:
            if action == "refund":
                narration = (request.POST.get("narration") or "").strip()
                execute_service_voucher_refund(
                    case_id=case_id,
                    admin_user=request.user,
                    narration=narration,
                )
                messages.success(
                    request,
                    f"Refund completed for case #{case_id}. Voucher balance restored. "
                    "ParkPe credit row reuses the original debit reference_id for reconciliation.",
                )
            elif action == "dismiss":
                note = (request.POST.get("dismiss_note") or "").strip()
                dismiss_service_voucher_refund_case(
                    case_id=case_id,
                    admin_user=request.user,
                    note=note,
                )
                messages.success(request, f"Case #{case_id} dismissed (no refund).")
            else:
                messages.error(request, "Unknown action.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("service_voucher_refund_queue")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tab = (self.request.GET.get("tab") or "open").strip().lower()
        base = ServiceVoucherRefundCase.objects.select_related(
            "user", "vehicle", "refunded_by", "dismissed_by"
        ).order_by("-created_at")
        if tab == "all":
            ctx["cases"] = list(base[:500])
        else:
            ctx["cases"] = list(
                base.filter(status=ServiceVoucherRefundCase.STATUS_OPEN)[:500]
            )
            tab = "open"
        ctx["tab"] = tab
        ctx["open_count"] = ServiceVoucherRefundCase.objects.filter(
            status=ServiceVoucherRefundCase.STATUS_OPEN
        ).count()
        return ctx
