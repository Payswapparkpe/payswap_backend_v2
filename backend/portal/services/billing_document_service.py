"""
Create immutable BillingDocument rows with idempotency; schedule on transaction.on_commit.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal

from django.db import transaction

from portal.models import BillingDocument, ParkPeVoucherTransaction
from portal.services.billing_party_service import party_snapshot_for_billing
from portal.services.tax_engine import compute_tax_snapshot


def build_idempotency_key(
    *,
    document_type: str,
    service_code: str,
    reference_id: str,
    transaction_direction: str = "",
) -> str:
    raw = f"{document_type}|{service_code}|{reference_id}|{transaction_direction}".encode()
    return hashlib.sha256(raw).hexdigest()[:64]


def record_billing_document(
    *,
    document_type: str,
    user,
    partner,
    service_code: str,
    reference_id: str,
    amount: Decimal,
    parkpe_voucher_transaction_id: int | None = None,
    transaction_direction: str = "",
    document_subtype: str | None = None,
) -> BillingDocument | None:
    """
    Persist a BillingDocument. Returns existing row if idempotency_key matches.
    """
    from portal.models import TaxServiceProfile

    ref = (reference_id or "").strip() or "unknown"
    sc = (service_code or "other").strip().lower() or "other"
    sub = document_subtype or (
        TaxServiceProfile.DOC_B2B if document_type == BillingDocument.DOC_B2B_COMMISSION else TaxServiceProfile.DOC_B2C
    )
    idem = build_idempotency_key(
        document_type=document_type,
        service_code=sc,
        reference_id=ref,
        transaction_direction=transaction_direction or "",
    )
    existing = BillingDocument.objects.filter(idempotency_key=idem).first()
    if existing:
        return existing

    calc = compute_tax_snapshot(
        service_code=sc,
        document_subtype=sub,
        amount=amount,
        document_type=document_type,
    )
    snap = calc.pop("snapshot")
    snap["grand_total"] = str(calc["grand_total"])
    snap["taxable_amount"] = str(calc["taxable_amount"])
    snap["party"] = party_snapshot_for_billing(user=user, partner=partner)

    txn = None
    if parkpe_voucher_transaction_id:
        txn = ParkPeVoucherTransaction.objects.filter(pk=parkpe_voucher_transaction_id).first()

    return BillingDocument.objects.create(
        document_type=document_type,
        user=user,
        partner=partner,
        idempotency_key=idem,
        reference_id=ref[:255],
        service_code=sc[:50],
        transaction_direction=(transaction_direction or "")[:10],
        taxable_amount=calc["taxable_amount"],
        cgst_amount=calc["cgst_amount"],
        sgst_amount=calc["sgst_amount"],
        igst_amount=calc["igst_amount"],
        gst_total=calc["gst_total"],
        tds_amount=calc["tds_amount"],
        grand_total=calc["grand_total"],
        snapshot=snap,
        parkpe_voucher_transaction=txn,
    )


def schedule_billing_document(**kwargs) -> None:
    """Register record_billing_document to run after the current DB transaction commits."""
    kw = dict(kwargs)

    def _run():
        try:
            record_billing_document(**kw)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("record_billing_document failed")

    transaction.on_commit(_run)


def idempotency_key_for_parkpe_voucher_transaction(txn: ParkPeVoucherTransaction) -> str:
    """Idempotency key that `record_billing_from_parkpe_voucher_transaction` would use."""
    if not txn or not txn.user_id:
        return ""
    doc_type = (
        BillingDocument.DOC_CREDIT_NOTE
        if txn.transaction_type == ParkPeVoucherTransaction.CREDIT
        else BillingDocument.DOC_B2C_RECEIPT
    )
    ref = (txn.reference_id or str(txn.pk)).strip()
    sc = (txn.service_code or "other").strip().lower() or "other"
    return build_idempotency_key(
        document_type=doc_type,
        service_code=sc,
        reference_id=ref,
        transaction_direction=txn.transaction_type,
    )


def record_billing_from_parkpe_voucher_transaction(txn: ParkPeVoucherTransaction) -> BillingDocument | None:
    """Create BillingDocument for a ledger row if missing (idempotent). Safe for backfills."""
    if not txn or not txn.user_id:
        return None
    doc_type = (
        BillingDocument.DOC_CREDIT_NOTE
        if txn.transaction_type == ParkPeVoucherTransaction.CREDIT
        else BillingDocument.DOC_B2C_RECEIPT
    )
    ref = (txn.reference_id or str(txn.pk)).strip()
    sc = (txn.service_code or "other").strip().lower() or "other"
    return record_billing_document(
        document_type=doc_type,
        user=txn.user,
        partner=None,
        service_code=sc,
        reference_id=ref,
        amount=txn.amount,
        parkpe_voucher_transaction_id=txn.pk,
        transaction_direction=txn.transaction_type,
        document_subtype=None,
    )


def schedule_billing_from_parkpe_voucher_transaction(txn: ParkPeVoucherTransaction) -> None:
    """Queue BillingDocument for a ParkPeVoucherTransaction row (B2C receipt or credit note)."""

    def _run():
        try:
            record_billing_from_parkpe_voucher_transaction(txn)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("record_billing_from_parkpe_voucher_transaction failed")

    transaction.on_commit(_run)


def idempotency_key_for_voucher_purchase_order(order_id: str) -> str:
    return build_idempotency_key(
        document_type=BillingDocument.DOC_B2C_RECEIPT,
        service_code="voucher_purchase",
        reference_id=str(order_id).strip(),
        transaction_direction="credit",
    )


def record_voucher_purchase_billing(*, user, order_id: str, amount: Decimal) -> BillingDocument | None:
    """PG voucher top-up completed — same row as async `schedule_voucher_purchase_billing`."""
    return record_billing_document(
        document_type=BillingDocument.DOC_B2C_RECEIPT,
        user=user,
        partner=None,
        service_code="voucher_purchase",
        reference_id=str(order_id).strip(),
        amount=amount,
        parkpe_voucher_transaction_id=None,
        transaction_direction="credit",
        document_subtype=None,
    )


def schedule_voucher_purchase_billing(*, user, order_id: str, amount: Decimal) -> None:
    """PG voucher top-up completed — no ParkPeVoucherTransaction row yet."""
    kw = dict(user=user, order_id=str(order_id).strip(), amount=amount)

    def _run():
        try:
            record_voucher_purchase_billing(**kw)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("record_voucher_purchase_billing failed")

    transaction.on_commit(_run)


def schedule_partner_commission_invoice(*, partner, period_key: str, commission_base: Decimal) -> None:
    """One B2B commission tax document per partner per settlement period (YYYY-MM)."""
    ref = f"{partner.pk}:{period_key}"
    schedule_billing_document(
        document_type=BillingDocument.DOC_B2B_COMMISSION,
        user=None,
        partner=partner,
        service_code="partner_commission",
        reference_id=ref,
        amount=commission_base,
        parkpe_voucher_transaction_id=None,
        transaction_direction="",
        document_subtype=None,
    )
