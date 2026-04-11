"""
Record Hub vendor costs (SMS, IVR, Cashfree) for P&L and reporting.
"""
from decimal import Decimal
from django.utils import timezone

from portal.models import HubVendorCostRecord, HubCostRateConfig


def get_unit_cost(service_code: str, vendor_code: str) -> Decimal:
    """Get configured unit cost for service/vendor; default 0."""
    try:
        config = HubCostRateConfig.objects.filter(
            service_code=service_code,
            vendor_code=vendor_code,
            is_active=True,
        ).first()
        if config and config.unit_cost is not None:
            return config.unit_cost
    except Exception:
        pass
    return Decimal('0')


def record_hub_cost(
    service_code: str,
    vendor_code: str,
    unit_count: int = 1,
    reference_id: str = None,
    partner=None,
):
    """
    Record one Hub cost record. Uses HubCostRateConfig for unit_cost; if not set, amount=0.
    """
    unit_cost = get_unit_cost(service_code, vendor_code)
    amount = unit_cost * unit_count
    HubVendorCostRecord.objects.create(
        service_code=service_code,
        vendor_code=vendor_code,
        amount=amount,
        unit_count=unit_count,
        unit_cost=unit_cost,
        period_date=timezone.now().date(),
        reference_id=reference_id,
        partner=partner,
    )
