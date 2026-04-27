"""Persist Mobikwik BBPS bill pay references for offline / degraded-vendor lookups."""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.utils import timezone

from portal.models import ParkPeBBPSBillPaymentRecord
from portal.utils.bbps_vendor_phase import vendor_payment_phase

logger = logging.getLogger(__name__)


def _json_safe(obj: Any, max_len: int = 15000) -> Optional[dict]:
    try:
        raw = json.dumps(obj, default=str)
        if len(raw) > max_len:
            raw = raw[:max_len] + "…"
        return json.loads(raw)
    except Exception:
        return None


def _phase_to_db(vendor_phase: str) -> str:
    if vendor_phase == "success":
        return ParkPeBBPSBillPaymentRecord.PHASE_SUCCESS
    if vendor_phase == "failed":
        return ParkPeBBPSBillPaymentRecord.PHASE_FAILED
    return ParkPeBBPSBillPaymentRecord.PHASE_PENDING


def upsert_from_pay_failed(
    *,
    user,
    reference_id: str,
    operator_id: str,
    bill_id: str,
    consumer_id: str,
    amount: Decimal | float,
    payment_method: str,
    result_dict: Dict[str, Any] | None,
    error_message: str | None = None,
) -> Optional[ParkPeBBPSBillPaymentRecord]:
    """Persist a failed Mobikwik pay_bill (same reference rules as success — for receipts / pay-status fallback)."""
    ref = str(reference_id or "").strip()[:64]
    if not ref:
        return None
    existing = ParkPeBBPSBillPaymentRecord.objects.filter(reference_id=ref).first()
    if existing and existing.user_id != user.pk:
        logger.warning(
            "parkpe_bbps_pay_failed_record user mismatch",
            extra_data={"reference_id": ref, "user_id": user.pk},
        )
        return None
    vendor = str((result_dict or {}).get("vendor") or "mobikwik")[:32]
    vs = str((result_dict or {}).get("status") or "FAILED")[:255]
    if not vs.strip():
        vs = "FAILED"
    msg = (error_message or (result_dict or {}).get("message") or "").strip()[:2000]
    obj, _ = ParkPeBBPSBillPaymentRecord.objects.update_or_create(
        reference_id=ref,
        defaults={
            "user": user,
            "operator_id": str(operator_id or "")[:128],
            "bill_id": str(bill_id or "")[:128],
            "consumer_id": str(consumer_id or "")[:255],
            "amount": Decimal(str(amount)),
            "payment_method": str(payment_method or "")[:32],
            "vendor": vendor,
            "last_vendor_status": vs,
            "resolved_phase": ParkPeBBPSBillPaymentRecord.PHASE_FAILED,
            "pay_response_json": _json_safe(result_dict or {}) or {},
            "last_status_check_at": timezone.now(),
            "last_error_message": msg,
        },
    )
    return obj


def upsert_from_pay_submitted(
    *,
    user,
    reference_id: str,
    operator_id: str,
    bill_id: str,
    consumer_id: str,
    amount: Decimal | float,
    payment_method: str,
    result_dict: Dict[str, Any],
    angular_status: str | None = None,
) -> Optional[ParkPeBBPSBillPaymentRecord]:
    """Call after Mobikwik pay_bill returns success."""
    ref = str(reference_id or "").strip()[:64]
    if not ref:
        return None
    existing = ParkPeBBPSBillPaymentRecord.objects.filter(reference_id=ref).first()
    if existing and existing.user_id != user.pk:
        logger.warning(
            "parkpe_bbps_pay_record user mismatch",
            extra_data={"reference_id": ref, "user_id": user.pk},
        )
        return None
    vendor = str((result_dict or {}).get("vendor") or "mobikwik")[:32]
    vs = str((result_dict or {}).get("status") or angular_status or "SUBMITTED")[:255]
    phase_key = vendor_payment_phase(vs)
    obj, _ = ParkPeBBPSBillPaymentRecord.objects.update_or_create(
        reference_id=ref,
        defaults={
            "user": user,
            "operator_id": str(operator_id or "")[:128],
            "bill_id": str(bill_id or "")[:128],
            "consumer_id": str(consumer_id or "")[:255],
            "amount": Decimal(str(amount)),
            "payment_method": str(payment_method or "")[:32],
            "vendor": vendor,
            "last_vendor_status": vs,
            "resolved_phase": _phase_to_db(phase_key),
            "pay_response_json": _json_safe(result_dict) or {},
            "last_status_check_at": timezone.now(),
            "last_error_message": "",
        },
    )
    return obj


def update_from_vendor_poll(
    *,
    user,
    reference_id: str,
    result_dict: Dict[str, Any],
) -> Optional[ParkPeBBPSBillPaymentRecord]:
    """Call when GET pay-status receives a successful vendor poll."""
    ref = str(reference_id or "").strip()[:64]
    if not ref:
        return None
    rec = ParkPeBBPSBillPaymentRecord.objects.filter(reference_id=ref, user=user).first()
    if not rec:
        return None
    vs = str((result_dict or {}).get("status") or "UNKNOWN")[:255]
    phase_key = vendor_payment_phase(vs)
    rec.last_vendor_status = vs
    rec.resolved_phase = _phase_to_db(phase_key)
    rec.last_poll_json = _json_safe(result_dict) or {}
    rec.last_status_check_at = timezone.now()
    rec.save(
        update_fields=[
            "last_vendor_status",
            "resolved_phase",
            "last_poll_json",
            "last_status_check_at",
            "updated_at",
        ]
    )
    return rec


def record_poll_failure(*, user, reference_id: str, message: str) -> None:
    ref = str(reference_id or "").strip()[:64]
    if not ref:
        return
    now = timezone.now()
    ParkPeBBPSBillPaymentRecord.objects.filter(reference_id=ref, user=user).update(
        last_error_message=str(message or "")[:2000],
        last_status_check_at=now,
        updated_at=now,
    )


def get_user_record(user, reference_id: str) -> Optional[ParkPeBBPSBillPaymentRecord]:
    ref = str(reference_id or "").strip()[:64]
    if not ref:
        return None
    return ParkPeBBPSBillPaymentRecord.objects.filter(reference_id=ref, user=user).first()


def response_from_db_row(rec: ParkPeBBPSBillPaymentRecord) -> dict:
    """Shape aligned with GET pay-status JSON for app polling."""
    vs = rec.last_vendor_status or "UNKNOWN"
    if rec.resolved_phase == ParkPeBBPSBillPaymentRecord.PHASE_FAILED:
        phase_key = "failed"
    elif rec.resolved_phase == ParkPeBBPSBillPaymentRecord.PHASE_SUCCESS:
        phase_key = "success"
    else:
        phase_key = vendor_payment_phase(vs)
    out = {
        "success": phase_key != "failed",
        "ref_id": rec.reference_id,
        "vendorStatus": vs,
        "phase": phase_key,
        "source": "database",
    }
    if rec.last_error_message and phase_key == "failed":
        out["message"] = rec.last_error_message[:500]
    return out
