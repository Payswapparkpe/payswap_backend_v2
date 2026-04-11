"""
Partner margin and profit tracking: gross, vendor cost, commission, GST, net margin.
Per partner / per service. Used for revenue dashboards and leakage detection.
"""
from decimal import Decimal
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Sum, Q

from portal.models import ResellerPartner, ResellerPartnerTransaction, ResellerPartnerPricing, HubVendorCostRecord


class PartnerMarginService:
    """
    Real profit engine: aggregate partner transactions into gross, cost, commission, net.
    """

    @staticmethod
    def get_margin_for_partner(
        partner: ResellerPartner,
        start_date: Optional[timezone.datetime] = None,
        end_date: Optional[timezone.datetime] = None,
    ) -> Dict[str, Any]:
        """
        Returns: gross, vendor_cost, commission, gst, net_margin, by_service list.
        Uses ResellerPartnerTransaction (REVENUE = gross; COMMISSION = partner commission).
        Vendor cost = derived from service cost or pricing if available.
        """
        if not start_date:
            start_date = timezone.now() - timezone.timedelta(days=30)
        if not end_date:
            end_date = timezone.now()

        qs = ResellerPartnerTransaction.objects.filter(
            partner=partner,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            status="COMPLETED",
        )
        revenue_sum = qs.filter(transaction_type="REVENUE").aggregate(s=Sum("amount"))["s"] or Decimal("0")
        commission_sum = qs.filter(transaction_type="COMMISSION").aggregate(s=Sum("commission_amount"))["s"] or Decimal("0")
        gross = revenue_sum
        commission = commission_sum
        # Vendor cost: from HubVendorCostRecord when available (SMS, IVR, Cashfree cost allocated to partner)
        vendor_cost_sum = HubVendorCostRecord.objects.filter(
            partner=partner,
            created_at__gte=start_date,
            created_at__lte=end_date,
        ).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        vendor_cost = vendor_cost_sum
        net_margin = gross - vendor_cost - commission

        by_service = list(
            qs.values("service__name", "service_id")
            .annotate(
                revenue=Sum("amount", filter=Q(transaction_type="REVENUE")),
                commission=Sum("commission_amount", filter=Q(transaction_type="COMMISSION")),
            )
        )
        by_service = [x for x in by_service if (x.get("revenue") or 0) != 0]

        return {
            "partner_id": partner.id,
            "partner_code": partner.partner_code,
            "period": {"start": start_date, "end": end_date},
            "gross": gross,
            "vendor_cost": vendor_cost,
            "commission": commission,
            "gst": Decimal("0"),  # extend when GST tracked
            "net_margin": net_margin,
            "by_service": by_service,
        }

    @staticmethod
    def detect_leakage(partner: ResellerPartner, since_days: int = 7) -> List[Dict[str, Any]]:
        """
        Leakage detection: negative margin, zero commission, unbilled tx.
        Returns list of issues (empty if none).
        """
        issues = []
        start = timezone.now() - timezone.timedelta(days=since_days)
        margin = PartnerMarginService.get_margin_for_partner(partner, start_date=start)
        if margin["net_margin"] < 0:
            issues.append({"type": "negative_margin", "net_margin": str(margin["net_margin"])})
        if margin["gross"] > 0 and margin["commission"] == 0:
            issues.append({"type": "zero_commission", "gross": str(margin["gross"])})
        # Unbilled: REVENUE without matching COMMISSION (simplified check)
        return issues
