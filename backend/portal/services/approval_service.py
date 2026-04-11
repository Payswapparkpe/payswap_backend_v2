"""
Approval workflow service (4-eye / maker-checker) for high-risk admin actions.
High-risk actions MUST go through: REQUEST → APPROVAL → EXECUTION.
Execution calls existing services only; no business logic duplicated here.
"""
from typing import Optional, Dict, Any
from django.utils import timezone
from django.db import transaction

from portal.models import (
    ApprovalRequest,
    ResellerPartner,
    ResellerPartnerSettlement,
    GiftVoucher,
    User,
)
from portal.services.partner_accounting_service import PartnerAccountingService
from portal.utils.logging_helper import get_logger

# Audit logger: writes to logs/audit.log (approval execution, overrides; file-system only)
logger = get_logger('portal.audit')


# Action types that require approval (must match ApprovalRequest.ACTION_TYPE_CHOICES)
REQUIRES_APPROVAL = frozenset([
    'partner_wallet_credit',
    'partner_wallet_debit',
    'settlement_execute',
    'refund_execute',
    'voucher_status_override',
    'manual_balance_adjustment',
])


def _approver_hierarchy_ok(approver: User, requester: User) -> bool:
    """
    Approver must be a different user with equal or higher role hierarchy.
    Protects against self-approval and lower-privilege override.
    """
    if approver.id == requester.id:
        return False
    if not hasattr(approver, 'role') or not approver.role:
        return False
    if not hasattr(requester, 'role') or not requester.role:
        return False
    return approver.role.hierarchy_level >= requester.role.hierarchy_level


def create_approval_request(
    action_type: str,
    entity_type: str,
    entity_id: str,
    payload: Dict[str, Any],
    requested_by: User,
) -> ApprovalRequest:
    """
    Maker flow: create an approval request with status PENDING.
    Does NOT execute business logic. Payload must NOT contain secrets.

    Integration: High-risk UI/API must call this instead of executing directly.
    Return "Approval request created. Awaiting approval." to the user.

    Payload examples (do not store API keys or secrets):
    - partner_wallet_credit: {"partner_id": int, "amount": Decimal, "reference_id": str, "description": str}
    - partner_wallet_debit: same
    - settlement_execute: {"settlement_id": int, "payment_method": str, "payment_reference": str}
    - voucher_status_override: {"voucher_id": int, "new_status": "BLOCKED"|"EXPIRED"}
    - manual_balance_adjustment: {"partner_id"|"voucher_id", "amount", "direction": "credit"|"debit", ...}
    """
    if action_type not in REQUIRES_APPROVAL:
        raise ValueError(f"Action type '{action_type}' is not a high-risk action requiring approval.")

    # Payload is stored as-is; caller must not include API keys or secrets.
    req = ApprovalRequest.objects.create(
        action_type=action_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        payload=dict(payload),
        requested_by=requested_by,
        status=ApprovalRequest.STATUS_PENDING,
    )
    logger.info(
        f'Approval request created: {action_type} entity={entity_type}:{entity_id} by {requested_by.username}',
        extra_data={'approval_request_id': req.id, 'requested_by_id': requested_by.id},
    )
    return req


def reject(approval_request_id: int, approved_by: User, rejection_reason: str) -> ApprovalRequest:
    """
    Checker flow: reject the request. No execution.
    Approver must be different from requester and have sufficient role.
    """
    req = ApprovalRequest.objects.select_related('requested_by', 'requested_by__role').get(
        id=approval_request_id
    )
    if req.status != ApprovalRequest.STATUS_PENDING:
        raise ValueError(f"Approval request {approval_request_id} is not PENDING (current: {req.status}).")

    if not _approver_hierarchy_ok(approved_by, req.requested_by):
        raise ValueError(
            "Approver must be a different user with equal or higher role (4-eye). Self-approval is not allowed."
        )

    req.status = ApprovalRequest.STATUS_REJECTED
    req.approved_by = approved_by
    req.approved_at = timezone.now()
    req.rejection_reason = rejection_reason or "Rejected by approver"
    req.save(update_fields=['status', 'approved_by', 'approved_at', 'rejection_reason'])

    logger.info(
        f'Approval request rejected: id={req.id} by {approved_by.username}',
        extra_data={'approval_request_id': req.id, 'approved_by_id': approved_by.id},
    )
    return req


def _execute_partner_wallet_credit(req: ApprovalRequest, approved_by: User) -> Dict[str, Any]:
    """Execute manual partner wallet credit via existing service. Atomic inside approve_and_execute."""
    partner_id = req.payload.get('partner_id') or req.entity_id
    partner = ResellerPartner.objects.get(id=int(partner_id))
    amount = req.payload['amount']
    if hasattr(amount, '__float__'):
        from decimal import Decimal
        amount = Decimal(str(amount))
    reference_id = req.payload.get('reference_id') or f"APPROVAL-{req.id}"
    description = req.payload.get('description') or f"Manual credit (approval #{req.id})"
    txn = PartnerAccountingService.manual_partner_wallet_credit(
        partner=partner,
        amount=amount,
        reference_id=reference_id,
        description=description,
        performed_by=approved_by,
    )
    return {'partner_transaction_id': txn.id, 'reference_id': reference_id}


def _execute_partner_wallet_debit(req: ApprovalRequest, approved_by: User) -> Dict[str, Any]:
    """Execute manual partner wallet debit via existing service."""
    partner_id = req.payload.get('partner_id') or req.entity_id
    partner = ResellerPartner.objects.get(id=int(partner_id))
    amount = req.payload['amount']
    if hasattr(amount, '__float__'):
        from decimal import Decimal
        amount = Decimal(str(amount))
    reference_id = req.payload.get('reference_id') or f"APPROVAL-{req.id}"
    description = req.payload.get('description') or f"Manual debit (approval #{req.id})"
    txn = PartnerAccountingService.manual_partner_wallet_debit(
        partner=partner,
        amount=amount,
        reference_id=reference_id,
        description=description,
        performed_by=approved_by,
    )
    return {'partner_transaction_id': txn.id, 'reference_id': reference_id}


def _execute_settlement(req: ApprovalRequest, approved_by: User) -> Dict[str, Any]:
    """Execute settlement (mark paid) via existing service."""
    settlement_id = req.payload.get('settlement_id') or req.entity_id
    settlement = ResellerPartnerSettlement.objects.get(id=int(settlement_id))
    payment_method = req.payload.get('payment_method') or 'MANUAL'
    payment_reference = req.payload.get('payment_reference') or f"APPROVAL-{req.id}"
    PartnerAccountingService.process_settlement(
        settlement=settlement,
        payment_method=payment_method,
        payment_reference=payment_reference,
        processed_by=approved_by,
    )
    return {
        'settlement_id': settlement.id,
        'settlement_reference': settlement.settlement_reference,
        'payment_reference': payment_reference,
    }


def _execute_refund(req: ApprovalRequest, approved_by: User) -> Dict[str, Any]:
    """Refund execution: placeholder until payment/voucher refund is implemented."""
    raise NotImplementedError(
        "Refund execution is not yet implemented. Use payment gateway or voucher reversal flow."
    )


def _execute_voucher_status_override(req: ApprovalRequest, approved_by: User) -> Dict[str, Any]:
    """Override voucher status (e.g. BLOCKED, EXPIRED) for audit/reversal. Lock row, validate, then update."""
    voucher_id = req.payload.get('voucher_id') or req.entity_id
    new_status = req.payload.get('new_status')
    if not new_status or new_status not in dict(GiftVoucher.STATUS_CHOICES):
        raise ValueError(f"payload.new_status must be one of: {list(dict(GiftVoucher.STATUS_CHOICES).keys())}")
    with transaction.atomic():
        voucher = GiftVoucher.objects.select_for_update().get(id=int(voucher_id))
        old_status = voucher.status
        voucher.status = new_status
        voucher.save(update_fields=['status'])
    return {'voucher_id': voucher.id, 'old_status': old_status, 'new_status': new_status}


def _execute_manual_balance_adjustment(req: ApprovalRequest, approved_by: User) -> Dict[str, Any]:
    """Dispatch to wallet credit/debit or voucher based on entity_type and payload."""
    if req.entity_type == 'wallet':
        direction = req.payload.get('direction', 'credit')
        if direction == 'credit':
            return _execute_partner_wallet_credit(req, approved_by)
        return _execute_partner_wallet_debit(req, approved_by)
    if req.entity_type == 'voucher':
        return _execute_voucher_status_override(req, approved_by)
    raise ValueError(f"manual_balance_adjustment not supported for entity_type={req.entity_type}")


def _execute_approval_request(req: ApprovalRequest, approved_by: User) -> Dict[str, Any]:
    """
    Dispatch to existing services only. No business logic duplicated here.
    Protects financial integrity by using atomic, audited service methods.
    """
    if req.action_type == 'partner_wallet_credit':
        return _execute_partner_wallet_credit(req, approved_by)
    if req.action_type == 'partner_wallet_debit':
        return _execute_partner_wallet_debit(req, approved_by)
    if req.action_type == 'settlement_execute':
        return _execute_settlement(req, approved_by)
    if req.action_type == 'refund_execute':
        return _execute_refund(req, approved_by)
    if req.action_type == 'voucher_status_override':
        return _execute_voucher_status_override(req, approved_by)
    if req.action_type == 'manual_balance_adjustment':
        return _execute_manual_balance_adjustment(req, approved_by)
    raise ValueError(f"Unknown action_type: {req.action_type}")


def approve_and_execute(approval_request_id: int, approved_by: User) -> ApprovalRequest:
    """
    Checker flow: approve and execute. Execution is atomic; on success mark APPROVED.
    Approver must be different from requester and have sufficient role.
    Business logic is executed via existing services only.
    """
    req = ApprovalRequest.objects.select_related('requested_by', 'requested_by__role').get(
        id=approval_request_id
    )
    if req.status != ApprovalRequest.STATUS_PENDING:
        raise ValueError(f"Approval request {approval_request_id} is not PENDING (current: {req.status}).")

    if not _approver_hierarchy_ok(approved_by, req.requested_by):
        raise ValueError(
            "Approver must be a different user with equal or higher role (4-eye). Self-approval is not allowed."
        )

    # Execute inside atomic so we either fully apply and mark APPROVED or roll back.
    with transaction.atomic():
        result = _execute_approval_request(req, approved_by)
        req.status = ApprovalRequest.STATUS_APPROVED
        req.approved_by = approved_by
        req.approved_at = timezone.now()
        req.execution_result = result
        req.rejection_reason = None
        req.save(update_fields=['status', 'approved_by', 'approved_at', 'execution_result', 'rejection_reason'])

    logger.info(
        f'Approval request approved and executed: id={req.id} by {approved_by.username}',
        extra_data={'approval_request_id': req.id, 'approved_by_id': approved_by.id, 'result': result},
    )
    return req
