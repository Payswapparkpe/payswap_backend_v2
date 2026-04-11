"""
Record Hub income (BBPS, Voucher) for P&L and reporting.
"""
from decimal import Decimal
from django.utils import timezone

from portal.models import HubIncomeRecord, ServiceIncomeConfig, Service


def _get_income_amount(service_code: str, vendor_code: str, transaction_amount: Decimal) -> Decimal:
    """Compute income from ServiceIncomeConfig (rate per txn or percentage)."""
    try:
        code_map = {'bbps': 'BBPS', 'voucher': 'VOUCHER'}
        svc_code = code_map.get(service_code, service_code.upper())
        service = Service.objects.filter(code__in=[svc_code, 'GIFT_VOUCHER']).first()
        if not service:
            return Decimal('0')
        config = ServiceIncomeConfig.objects.filter(
            service=service,
            income_type__in=['COMMISSION', 'PER_TXN', 'MARKUP'],
            is_active=True,
        ).first()
        if not config:
            return Decimal('0')
        if config.rate_per_txn is not None and config.rate_per_txn > 0:
            return config.rate_per_txn
        if config.rate_percentage is not None and config.rate_percentage > 0 and transaction_amount:
            return (transaction_amount * config.rate_percentage / 100)
    except Exception:
        pass
    return Decimal('0')


def record_hub_income(
    service_code: str,
    amount: Decimal = None,
    transaction_amount: Decimal = None,
    vendor_code: str = None,
    reference_id: str = None,
    partner=None,
):
    """
    Record one Hub income record. If amount not provided, computed from ServiceIncomeConfig.
    """
    if amount is None and transaction_amount is not None:
        amount = _get_income_amount(service_code, vendor_code or '', transaction_amount)
    if amount is None:
        amount = Decimal('0')
    HubIncomeRecord.objects.create(
        service_code=service_code,
        amount=amount,
        transaction_amount=transaction_amount,
        vendor_code=vendor_code,
        reference_id=reference_id,
        partner=partner,
        period_date=timezone.now().date(),
    )
