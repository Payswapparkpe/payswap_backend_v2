"""
DMT (Domestic Money Transfer) service layer.
Uses PayPoint as the DMT vendor. Partner-facing APIs call this service.
"""
from typing import Optional, Dict, Any

from portal.services.vendors.paypoint_dmt import PayPointDMTClient
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.dmt_service")


class DMTService:
    """DMT service – delegates to PayPoint DMT client."""

    def __init__(self):
        self._client: Optional[PayPointDMTClient] = None

    @property
    def client(self) -> PayPointDMTClient:
        if self._client is None:
            self._client = PayPointDMTClient()
        return self._client

    def is_available(self) -> bool:
        """Return True if DMT (PayPoint) is configured and enabled."""
        return self.client.is_configured()

    def register_sender(
        self,
        mobile_number: str,
        first_name: str,
        last_name: str,
        pincode: Optional[str] = None,
        state: Optional[str] = None,
        address: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """DMT sender/remitter registration."""
        result = self.client.register_sender(
            mobile_number=mobile_number,
            first_name=first_name,
            last_name=last_name,
            pincode=pincode,
            state=state,
            address=address,
            date_of_birth=date_of_birth,
            extra=extra,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Sender registration failed"),
                "vendor": "paypoint",
                "data": result.get("response"),
            }
        return {
            "success": True,
            "vendor": "paypoint",
            "data": result.get("data"),
        }

    def add_beneficiary(
        self,
        sender_mobile: str,
        beneficiary_name: str,
        account_number: str,
        ifsc: str,
        mobile_number: Optional[str] = None,
        bank_name: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add DMT beneficiary."""
        result = self.client.add_beneficiary(
            sender_mobile=sender_mobile,
            beneficiary_name=beneficiary_name,
            account_number=account_number,
            ifsc=ifsc,
            mobile_number=mobile_number,
            bank_name=bank_name,
            extra=extra,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Add beneficiary failed"),
                "vendor": "paypoint",
                "data": result.get("response"),
            }
        return {
            "success": True,
            "vendor": "paypoint",
            "data": result.get("data"),
        }

    def remit(
        self,
        sender_mobile: str,
        beneficiary_id: str,
        amount: str,
        client_ref_id: Optional[str] = None,
        remarks: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute DMT remittance."""
        result = self.client.remit(
            sender_mobile=sender_mobile,
            beneficiary_id=beneficiary_id,
            amount=amount,
            client_ref_id=client_ref_id,
            remarks=remarks,
            extra=extra,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Remit failed"),
                "vendor": "paypoint",
                "data": result.get("response"),
            }
        return {
            "success": True,
            "vendor": "paypoint",
            "data": result.get("data"),
        }

    def transaction_status(self, ref_id: str) -> Dict[str, Any]:
        """DMT transaction status by reference id."""
        result = self.client.transaction_status(ref_id=ref_id)
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Transaction status failed"),
                "vendor": "paypoint",
                "data": result.get("response"),
            }
        return {
            "success": True,
            "vendor": "paypoint",
            "data": result.get("data"),
        }

    def get_beneficiaries(
        self,
        sender_mobile: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get list of beneficiaries for a sender."""
        result = self.client.get_beneficiaries(
            sender_mobile=sender_mobile,
            extra=extra,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Get beneficiaries failed"),
                "vendor": "paypoint",
                "data": result.get("response"),
            }
        return {
            "success": True,
            "vendor": "paypoint",
            "data": result.get("data"),
        }
