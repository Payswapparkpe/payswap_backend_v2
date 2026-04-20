"""
FASTag balance for Connect vehicles via BBPS View Bill (Mobikwik).
User selects issuer (biller_id); we fetch bill using vehicle registration as consumer id.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.utils import timezone

from portal.models import BBPSOperator, Vehicle
from portal.services.bbps_service import BBPSService
from portal.utils.logging_helper import get_logger

logger = get_logger(__name__)


def _resolve_mobikwik_op(operator_id: str) -> str:
    if not operator_id or not str(operator_id).strip():
        return operator_id
    oid = str(operator_id).strip()
    try:
        rec = BBPSOperator.objects.filter(biller_id=oid).first()
        if rec and getattr(rec, "op", None) and str(rec.op).strip():
            return str(rec.op).strip()
    except Exception:
        pass
    return oid


def _extra_params_for_biller(biller_id: str) -> Dict[str, Any]:
    """Circle + optional ad params from BBPSOperator row."""
    extra: Dict[str, Any] = {}
    try:
        rec = BBPSOperator.objects.filter(biller_id=biller_id.strip(), is_active=True).first()
        if not rec:
            return extra
        if getattr(rec, "circle", None) and str(rec.circle).strip():
            extra["cir"] = str(rec.circle).strip()
        for key, field in (
            ("ad1", "ad1"),
            ("ad2", "ad2"),
            ("ad3", "ad3"),
            ("ad4", "ad4"),
            ("ad9", "ad9"),
        ):
            val = getattr(rec, field, None)
            if val not in (None, ""):
                extra[key] = str(val).strip()
    except Exception:
        pass
    return extra


def _amount_from_bill_details(bill_details: Any) -> Optional[float]:
    if not isinstance(bill_details, dict):
        return None
    amount_val = (
        bill_details.get("billAmount")
        or bill_details.get("billnetamount")
        or bill_details.get("amount")
        or bill_details.get("dueAmount")
        or bill_details.get("outstanding")
        or bill_details.get("due_amount")
        or bill_details.get("outstanding_amount")
        or bill_details.get("total_amount")
        or bill_details.get("minBillAmount")
    )
    if amount_val is None or amount_val == "":
        return None
    try:
        return float(amount_val)
    except (TypeError, ValueError):
        return None


def refresh_vehicle_fastag_balance(vehicle: Vehicle) -> Tuple[bool, Optional[str], Optional[Decimal]]:
    """
    Call BBPS fetch_bill for this vehicle's saved FASTag biller + registration number.
    On success, persist fastag_balance_last_value and fastag_balance_fetched_at.

    Returns (success, error_message, balance_decimal_or_none).
    """
    biller_id = (getattr(vehicle, "fastag_biller_id", None) or "").strip()
    if not biller_id:
        return False, "Select a FASTag issuer (biller) for this vehicle first.", None

    reg = (vehicle.registration_number or "").strip()
    if not reg:
        return False, "Vehicle registration number is missing.", None

    op_for_api = _resolve_mobikwik_op(biller_id)
    if not op_for_api or not str(op_for_api).strip():
        return False, "Invalid FASTag biller configuration.", None

    extra = _extra_params_for_biller(biller_id)
    service = BBPSService()
    if not service.is_available():
        return False, "BBPS service is not configured.", None

    try:
        result = service.fetch_bill(
            operator_id=op_for_api,
            customer_id=reg.upper(),
            subscriber_id=None,
            extra=extra if extra else None,
            log_context={"source": "ParkPe", "api_name": "Connect FASTag balance"},
        )
    except Exception as e:
        logger.exception("connect_fastag_fetch_bill_error", extra_data={"vehicle_id": vehicle.pk, "error": str(e)})
        return False, "Could not reach FASTag service. Try again.", None

    if not result.get("success"):
        msg = result.get("message") or "Bill fetch failed."
        return False, str(msg), None

    bill_details = result.get("bill_details")
    amt = _amount_from_bill_details(bill_details)
    if amt is None:
        return False, "FASTag response did not include a balance amount.", None

    dec = Decimal(str(round(amt, 2)))
    vehicle.fastag_balance_last_value = dec
    vehicle.fastag_balance_fetched_at = timezone.now()
    vehicle.save(update_fields=["fastag_balance_last_value", "fastag_balance_fetched_at", "updated_at"])

    return True, None, dec
