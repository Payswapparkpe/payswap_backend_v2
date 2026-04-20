"""
Admin-driven refunds when a voucher debit succeeded but the service did not complete.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from portal.models import (
    GiftVoucher,
    GiftVoucherTransaction,
    ParkPeVoucherTransaction,
    ServiceVoucherRefundCase,
    Vehicle,
)
from portal.utils.transaction_id import generate_transaction_id

# RC fetch failed for these reasons after payment → queue for refund review.
RC_REFUND_QUEUE_REASONS = frozenset({"http_error", "exception", "no_credentials", "invalid_status"})


def ensure_rc_view_refund_case(
    *,
    vehicle: Vehicle,
    rc_reason: str | None,
    customer_message: str,
) -> ServiceVoucherRefundCase | None:
    """
    Create an open refund case when RC fetch returned no data after the user had paid RC_VIEW.
    """
    if not vehicle.rc_view_paid_at or not (vehicle.rc_view_debit_reference_id or "").strip():
        return None
    reason = (rc_reason or "").strip()
    if reason not in RC_REFUND_QUEUE_REASONS:
        return None
    debit_ref = vehicle.rc_view_debit_reference_id.strip()
    existing_open = ServiceVoucherRefundCase.objects.filter(
        debit_reference_id=debit_ref,
        status=ServiceVoucherRefundCase.STATUS_OPEN,
    ).first()
    if existing_open:
        if customer_message and customer_message not in (existing_open.failure_detail or ""):
            existing_open.failure_detail = f"{existing_open.failure_detail}\n{customer_message}".strip()
            existing_open.save(update_fields=["failure_detail", "updated_at"])
        return existing_open
    debit_row = ParkPeVoucherTransaction.objects.filter(
        user_id=vehicle.user_id,
        reference_id=debit_ref,
        transaction_type=ParkPeVoucherTransaction.DEBIT,
        service_code="RC_VIEW",
    ).first()
    amount = debit_row.amount if debit_row else Decimal("50")
    return ServiceVoucherRefundCase.objects.create(
        user_id=vehicle.user_id,
        vehicle=vehicle,
        debit_reference_id=debit_ref,
        amount=amount,
        service_code="RC_VIEW",
        status=ServiceVoucherRefundCase.STATUS_OPEN,
        rc_reason_code=reason,
        failure_detail=(customer_message or "")[:4000],
        source="auto_fetch_failed",
    )


def dismiss_open_cases_after_rc_success(*, vehicle: Vehicle) -> int:
    """When RC is persisted, close any mistaken open queue rows for this debit ref."""
    ref = (vehicle.rc_view_debit_reference_id or "").strip()
    if not ref:
        return 0
    return ServiceVoucherRefundCase.objects.filter(
        debit_reference_id=ref,
        status=ServiceVoucherRefundCase.STATUS_OPEN,
        vehicle_id=vehicle.pk,
    ).update(
        status=ServiceVoucherRefundCase.STATUS_DISMISSED,
        dismissed_at=timezone.now(),
        dismiss_note="RC data delivered; auto-dismissed.",
    )


def execute_service_voucher_refund(
    *,
    case_id: int,
    admin_user,
    narration: str,
) -> ServiceVoucherRefundCase:
    """
    Credit voucher balance, write audit rows, clear RC payment lock on vehicle.
    ParkPe CREDIT uses the same reference_id as the original debit for reconciliation.
    GiftVoucherTransaction uses a new unique transaction_ref with metadata.original_debit_transaction_ref.
    """
    text = (narration or "").strip()
    if len(text) < 10:
        raise ValueError("Narration must be at least 10 characters.")

    with transaction.atomic():
        case = (
            ServiceVoucherRefundCase.objects.select_for_update()
            .filter(pk=case_id)
            .select_related("user", "vehicle")
            .first()
        )
        if not case:
            raise ValueError("Case not found.")
        if case.status != ServiceVoucherRefundCase.STATUS_OPEN:
            raise ValueError("Case is not open for refund.")

        orig_txn = GiftVoucherTransaction.objects.filter(
            transaction_ref=case.debit_reference_id,
            transaction_type="REDEMPTION",
            transaction_status="SUCCESS",
        ).select_related("voucher").first()
        if not orig_txn:
            raise ValueError("Original voucher redemption not found for this debit reference.")

        voucher = GiftVoucher.objects.select_for_update().get(pk=orig_txn.voucher_id)
        amount = case.amount
        if amount <= 0:
            raise ValueError("Invalid refund amount on case.")

        before = voucher.current_balance
        after = before + amount
        voucher.current_balance = after
        voucher.last_transaction_at = timezone.now()
        if after == 0:
            voucher.status = "FULLY_REDEEMED"
        elif after < voucher.original_amount:
            voucher.status = "PARTIALLY_REDEEMED"
        else:
            voucher.status = "ACTIVE"
        voucher.save(update_fields=["current_balance", "last_transaction_at", "status"])

        credit_ref = generate_transaction_id()
        if GiftVoucherTransaction.objects.filter(transaction_ref=credit_ref).exists():
            credit_ref = generate_transaction_id()

        GiftVoucherTransaction.objects.create(
            voucher=voucher,
            transaction_type="REDEMPTION",
            transaction_amount=amount,
            balance_before=before,
            balance_after=after,
            redemption_method="PIN",
            transaction_status="SUCCESS",
            transaction_ref=credit_ref,
            metadata={
                "type": "SERVICE_REFUND",
                "original_debit_transaction_ref": case.debit_reference_id,
                "service_code": case.service_code,
                "refund_case_id": case.pk,
                "admin_user_id": admin_user.pk,
                "narration": text[:2000],
            },
        )

        cr_txn = ParkPeVoucherTransaction.objects.create(
            user_id=case.user_id,
            amount=amount,
            transaction_type=ParkPeVoucherTransaction.CREDIT,
            balance_after=None,
            reference_id=case.debit_reference_id,
            service_code=case.service_code,
            description=f"Refund (same ref as debit {case.debit_reference_id}): {text[:200]}",
        )
        from portal.services.billing_document_service import schedule_billing_from_parkpe_voucher_transaction

        schedule_billing_from_parkpe_voucher_transaction(cr_txn)

        veh = case.vehicle
        if veh and veh.rc_view_debit_reference_id == case.debit_reference_id:
            Vehicle.objects.filter(pk=veh.pk).update(
                rc_view_paid_at=None,
                rc_view_debit_reference_id=None,
            )

        case.status = ServiceVoucherRefundCase.STATUS_REFUNDED
        case.admin_narration = text[:4000]
        case.credit_transaction_ref = credit_ref
        case.refunded_at = timezone.now()
        case.refunded_by = admin_user
        case.save(
            update_fields=[
                "status",
                "admin_narration",
                "credit_transaction_ref",
                "refunded_at",
                "refunded_by",
                "updated_at",
            ]
        )
        return case


def dismiss_service_voucher_refund_case(
    *,
    case_id: int,
    admin_user,
    note: str,
) -> ServiceVoucherRefundCase:
    note = (note or "").strip()
    if len(note) < 3:
        raise ValueError("Dismiss note must be at least 3 characters.")

    with transaction.atomic():
        case = (
            ServiceVoucherRefundCase.objects.select_for_update()
            .filter(pk=case_id)
            .first()
        )
        if not case:
            raise ValueError("Case not found.")
        if case.status != ServiceVoucherRefundCase.STATUS_OPEN:
            raise ValueError("Case is not open.")
        case.status = ServiceVoucherRefundCase.STATUS_DISMISSED
        case.dismissed_at = timezone.now()
        case.dismissed_by = admin_user
        case.dismiss_note = note[:4000]
        case.save(
            update_fields=[
                "status",
                "dismissed_at",
                "dismissed_by",
                "dismiss_note",
                "updated_at",
            ]
        )
        return case
