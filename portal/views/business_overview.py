"""
Business visibility dashboard: Revenue, Margin, Partner growth, Vendor performance.
Reuses existing services (finance, growth_metrics, portal models). No new APIs or vendors.
"""
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta

from portal.utils.staff_utils import _is_super_admin_allowed
from portal.models import (
    ResellerPartnerTransaction, ResellerPartner, ResellerPartnerSettlement,
    ApiVendor, PartnerVendorAssignment,
    HubVendorCostRecord, HubIncomeRecord,
)


class BusinessOverviewView(TemplateView):
    """
    GET /dashboard/business/
    Revenue, margin, partner growth, vendor performance. Read-only; reuses existing data.
    """
    template_name = "portal/business_overview.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_super_admin_allowed(request.user):
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from portal.services.growth_metrics import compute_growth_metrics

        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        thirty_days = now - timedelta(days=30)

        # Revenue (30d) — same as finance
        rev = ResellerPartnerTransaction.objects.filter(
            transaction_type="REVENUE",
            status="COMPLETED",
            transaction_date__gte=thirty_days,
        ).aggregate(s=Sum("amount"))["s"]
        ctx["revenue_30d"] = rev or 0

        # Margin (30d) — commission
        margin = ResellerPartnerTransaction.objects.filter(
            transaction_type="REVENUE",
            status="COMPLETED",
            transaction_date__gte=thirty_days,
        ).aggregate(s=Sum("commission_amount"))["s"]
        ctx["margin_30d"] = margin or 0

        # Partner growth — reuse growth_metrics
        growth = compute_growth_metrics()
        ctx["growth"] = growth
        ctx["active_partners"] = ResellerPartner.objects.filter(status="ACTIVE").count()
        ctx["pending_settlements_count"] = ResellerPartnerSettlement.objects.filter(status="PENDING").count()

        # Hub P&L (cost vs income)
        hub_cost_30d = HubVendorCostRecord.objects.filter(
            created_at__gte=thirty_days,
        ).aggregate(s=Sum("amount"))["s"]
        hub_income_30d = HubIncomeRecord.objects.filter(
            created_at__gte=thirty_days,
        ).aggregate(s=Sum("amount"))["s"]
        ctx["hub_cost_30d"] = hub_cost_30d or 0
        ctx["hub_income_30d"] = hub_income_30d or 0
        ctx["net_pnl_30d"] = (hub_income_30d or 0) - (hub_cost_30d or 0)

        # Vendor performance: list vendors with active assignment count
        vendor_perf = []
        for v in ApiVendor.objects.filter(is_active=True).order_by("code"):
            cnt = PartnerVendorAssignment.objects.filter(vendor=v, is_active=True).count()
            vendor_perf.append({"vendor": v, "assignment_count": cnt})
        ctx["vendor_performance"] = vendor_perf

        return ctx


class HubPnlView(TemplateView):
    """
    GET /dashboard/hub-pnl/?days=7|30
    Hub P&L: income vs cost by service and date range. Cost breakdown (SMS, IVR, Cashfree), income breakdown (BBPS, Voucher).
    """
    template_name = "portal/hub_pnl.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_super_admin_allowed(request.user):
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            days = int(self.request.GET.get("days", "30"))
        except ValueError:
            days = 30
        days = max(1, min(90, days))
        now = timezone.now()
        since = now - timedelta(days=days)

        # Cost breakdown by service_code
        cost_qs = HubVendorCostRecord.objects.filter(created_at__gte=since)
        cost_totals = cost_qs.values("service_code").annotate(total=Sum("amount")).order_by("service_code")
        cost_by_service = {r["service_code"]: float(r["total"]) for r in cost_totals}
        total_cost = cost_qs.aggregate(s=Sum("amount"))["s"] or 0

        # Income breakdown by service_code
        income_qs = HubIncomeRecord.objects.filter(created_at__gte=since)
        income_totals = income_qs.values("service_code").annotate(total=Sum("amount")).order_by("service_code")
        income_by_service = {r["service_code"]: float(r["total"]) for r in income_totals}
        total_income = income_qs.aggregate(s=Sum("amount"))["s"] or 0

        ctx["period_days"] = days
        ctx["total_cost"] = total_cost
        ctx["total_income"] = total_income
        ctx["net_pnl"] = (total_income or 0) - (total_cost or 0)
        ctx["cost_by_service"] = cost_by_service
        ctx["income_by_service"] = income_by_service
        return ctx
