"""
Hub service wrapper for Instantpay modules.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from portal.models import ApiVendor, InstantpayTransaction, ResellerPartner
from portal.services.vendors.instantpay import InstantpayClient

logger = logging.getLogger(__name__)


class InstantpayHubService:
    """Orchestrates Instantpay calls with common Hub metadata."""

    def __init__(self):
        self.client = InstantpayClient()

    def is_available(self) -> bool:
        return self.client.is_configured()

    def execute(
        self,
        api_code: str,
        payload: Optional[Dict[str, Any]],
        *,
        partner_id: Optional[int] = None,
        partner_code: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = dict(payload or {})
        body.setdefault("meta", {})
        if partner_id:
            body["meta"]["partner_id"] = partner_id
        if partner_code:
            body["meta"]["partner_code"] = partner_code
        if idempotency_key:
            body["meta"]["idempotency_key"] = idempotency_key

        partner = ResellerPartner.objects.filter(id=partner_id).first() if partner_id else None
        vendor = ApiVendor.objects.filter(code="instantpay").first()
        partner_txn_id = str(body.get("partner_txn_id") or body.get("meta", {}).get("partner_txn_id") or "")
        tx = None
        if partner_txn_id:
            tx, _ = InstantpayTransaction.objects.get_or_create(
                partner=partner,
                partner_txn_id=partner_txn_id,
                defaults={
                    "vendor": vendor,
                    "service_name": self._service_name_from_api_code(api_code),
                    "action": api_code,
                    "idempotency_key": idempotency_key,
                    "request_payload": body,
                    "status": InstantpayTransaction.STATUS_INITIATED,
                },
            )

        result = self.client.request(api_code, body)

        if tx:
            tx.response_payload = result.get("json") or {"body": result.get("body")}
            tx.vendor_reference = str(
                (result.get("json") or {}).get("reference_id")
                or (result.get("json") or {}).get("txn_id")
                or ""
            )[:128] or None
            tx.error_message = result.get("error") or ""
            tx.status = (
                InstantpayTransaction.STATUS_SUCCESS
                if result.get("success")
                else InstantpayTransaction.STATUS_FAILED
            )
            tx.save(
                update_fields=[
                    "response_payload",
                    "vendor_reference",
                    "error_message",
                    "status",
                    "updated_at",
                ]
            )
            if result.get("success"):
                try:
                    from decimal import Decimal
                    from portal.services.hub_income_service import record_hub_income
                    amount_raw = body.get("amount") or 0
                    amount = Decimal(str(amount_raw)) if amount_raw else Decimal("0")
                    record_hub_income(
                        "instantpay",
                        transaction_amount=amount,
                        vendor_code="instantpay",
                        reference_id=partner_txn_id,
                        partner=partner,
                    )
                except Exception as exc:
                    logger.warning(
                        f"Instantpay income recording failed for txn={partner_txn_id} api={api_code}: {exc}"
                    )

        return result

    def get_status(self, partner_txn_id: str, *, partner_id: Optional[int] = None) -> Dict[str, Any]:
        qs = InstantpayTransaction.objects.filter(partner_txn_id=partner_txn_id)
        if partner_id:
            qs = qs.filter(partner_id=partner_id)
        tx = qs.order_by("-created_at").first()
        if not tx:
            return {"success": False, "message": "Transaction not found", "status_code": 404}
        return {
            "success": True,
            "status_code": 200,
            "transaction": {
                "partner_txn_id": tx.partner_txn_id,
                "status": tx.status,
                "service_name": tx.service_name,
                "action": tx.action,
                "vendor_reference": tx.vendor_reference,
                "response_payload": tx.response_payload,
                "error_message": tx.error_message,
                "created_at": tx.created_at.isoformat(),
                "updated_at": tx.updated_at.isoformat(),
            },
        }

    @staticmethod
    def _service_name_from_api_code(api_code: str) -> str:
        if api_code.startswith("aeps") or api_code in ("balance_check", "account_statement"):
            return "aeps"
        if api_code.startswith("dmt") or api_code.startswith("remittance"):
            return "dmt"
        if api_code in ("credit_card_bill_pay",):
            return "billpay"
        if api_code in ("rc_verification", "vehicle_challan_lookup"):
            return "vehicle"
        if api_code.startswith("digilocker"):
            return "identity_docs"
        if api_code.startswith("card_bin"):
            return "cards"
        if api_code.startswith("credit_"):
            return "credit"
        if api_code.startswith("merchant_"):
            return "merchant"
        return "reconciliation"
