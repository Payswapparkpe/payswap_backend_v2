"""
Growth metrics for fundraising and reporting: MRR, ARR, active partners, churn, retention, revenue growth.
Source: ResellerPartnerTransaction + ResellerPartnerSettlement + ResellerPartner.
"""
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone
from django.db.models import Sum

from portal.models import ResellerPartner, ResellerPartnerTransaction, ResellerPartnerSettlement


def _month_bounds(months_ago: int = 0) -> tuple:
    """Return (start, end) for the month that is `months_ago` months before current month."""
    now = timezone.now()
    if months_ago == 0:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    else:
        # Go to first of current month, then subtract months
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Approximate: subtract 30 * months_ago days then set day=1
        approx = first - timedelta(days=30 * months_ago)
        start = approx.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if months_ago == 1:
            end = first - timedelta(microseconds=1)
        else:
            next_start = start + timedelta(days=32)
            next_start = next_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = next_start - timedelta(microseconds=1)
    return start, end


def compute_growth_metrics() -> dict[str, Any]:
    """
    Compute MRR, ARR, active partners, churn, retention, revenue growth %.
    Returns a dict suitable for JSON (decimals as strings).
    """
    # Current month revenue (MRR approximation: this month's revenue)
    start_0, end_0 = _month_bounds(0)
    start_1, end_1 = _month_bounds(1)

    rev_this = ResellerPartnerTransaction.objects.filter(
        transaction_type="REVENUE",
        status="COMPLETED",
        transaction_date__gte=start_0,
        transaction_date__lte=end_0,
    ).aggregate(s=Sum("amount"))["s"] or Decimal("0")

    rev_prev = ResellerPartnerTransaction.objects.filter(
        transaction_type="REVENUE",
        status="COMPLETED",
        transaction_date__gte=start_1,
        transaction_date__lte=end_1,
    ).aggregate(s=Sum("amount"))["s"] or Decimal("0")

    mrr = rev_this
    arr = mrr * 12

    # Active partners: have status ACTIVE (or partners with at least one completed REVENUE in last 30 days)
    active_partners = ResellerPartner.objects.filter(status="ACTIVE").count()
    thirty_days_ago = timezone.now() - timedelta(days=30)
    partners_with_revenue_30d = (
        ResellerPartnerTransaction.objects.filter(
            transaction_type="REVENUE",
            status="COMPLETED",
            transaction_date__gte=thirty_days_ago,
        )
        .values_list("partner_id", flat=True)
        .distinct()
    )
    active_partners_with_revenue = len(list(partners_with_revenue_30d))

    # Churn: partners who had revenue in prev month but zero in current month
    partner_ids_prev = set(
        ResellerPartnerTransaction.objects.filter(
            transaction_type="REVENUE",
            status="COMPLETED",
            transaction_date__gte=start_1,
            transaction_date__lte=end_1,
        ).values_list("partner_id", flat=True).distinct()
    )
    partner_ids_this = set(
        ResellerPartnerTransaction.objects.filter(
            transaction_type="REVENUE",
            status="COMPLETED",
            transaction_date__gte=start_0,
            transaction_date__lte=end_0,
        ).values_list("partner_id", flat=True).distinct()
    )
    churned = partner_ids_prev - partner_ids_this
    retained = partner_ids_prev & partner_ids_this
    retention_count = len(retained)
    retention_pct = (Decimal(len(retained)) / Decimal(len(partner_ids_prev)) * 100) if partner_ids_prev else Decimal("100")
    churn_count = len(churned)

    # Revenue growth %
    if rev_prev > 0:
        revenue_growth_pct = (rev_this - rev_prev) / rev_prev * 100
    else:
        revenue_growth_pct = Decimal("0") if rev_this == 0 else Decimal("100")

    return {
        "mrr": str(mrr),
        "arr": str(arr),
        "active_partners": active_partners,
        "active_partners_with_revenue_30d": active_partners_with_revenue,
        "churn_count": churn_count,
        "retention_count": retention_count,
        "retention_pct": str(round(retention_pct, 2)),
        "revenue_this_month": str(rev_this),
        "revenue_prev_month": str(rev_prev),
        "revenue_growth_pct": str(round(revenue_growth_pct, 2)),
        "period_this": start_0.isoformat(),
        "period_prev": start_1.isoformat(),
    }
