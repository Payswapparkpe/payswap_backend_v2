"""
AEPS (Aadhaar Enabled Payment System) service layer.
Uses PayPoint as the AEPS vendor. Partner-facing APIs call this service.
"""
from typing import Optional, Dict, Any, List

from portal.services.vendors.paypoint import PayPointAEPSClient
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.aeps_service")


class AEPSService:
    """AEPS service – delegates to PayPoint AEPS client."""

    def __init__(self):
        self._client: Optional[PayPointAEPSClient] = None

    @property
    def client(self) -> PayPointAEPSClient:
        if self._client is None:
            self._client = PayPointAEPSClient()
        return self._client

    def is_available(self) -> bool:
        """Return True if AEPS (PayPoint) is configured and enabled."""
        return self.client.is_configured()

    def balance_enquiry(
        self,
        aadhaar_number: str,
        mobile_number: str,
        bank_iin: str,
        rd_request: str,
        latitude: str,
        longitude: str,
        terminal_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """AEPS balance enquiry."""
        result = self.client.balance_enquiry(
            aadhaar_number=aadhaar_number,
            mobile_number=mobile_number,
            bank_iin=bank_iin,
            rd_request=rd_request,
            latitude=latitude,
            longitude=longitude,
            terminal_id=terminal_id,
            extra_params=extra,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Balance enquiry failed"),
                "balance": None,
                "rrn": None,
            }
        data = result.get("data") or {}
        balance = data.get("balance") or data.get("account_balance") or data.get("Balance") or data.get("AccountBalance")
        rrn = data.get("rrn") or data.get("reference_number") or data.get("RRN") or data.get("ReferenceNumber")
        return {
            "success": True,
            "balance": balance,
            "rrn": rrn,
            "vendor": "paypoint",
            "data": data,
        }

    def cash_withdrawal(
        self,
        aadhaar_number: str,
        mobile_number: str,
        bank_iin: str,
        rd_request: str,
        amount: str,
        latitude: str,
        longitude: str,
        terminal_id: Optional[str] = None,
        client_ref_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """AEPS cash withdrawal."""
        result = self.client.cash_withdrawal(
            aadhaar_number=aadhaar_number,
            mobile_number=mobile_number,
            bank_iin=bank_iin,
            rd_request=rd_request,
            amount=amount,
            latitude=latitude,
            longitude=longitude,
            terminal_id=terminal_id,
            client_ref_id=client_ref_id,
            extra_params=extra,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Cash withdrawal failed"),
                "transaction_id": None,
                "rrn": None,
                "status": "FAILED",
            }
        data = result.get("data") or {}
        txn_id = data.get("transaction_id") or data.get("TransactionId") or data.get("client_ref_id") or data.get("ClientRefId") or client_ref_id
        rrn = data.get("rrn") or data.get("reference_number") or data.get("RRN") or data.get("ReferenceNumber")
        status_val = data.get("status") or data.get("Status", "SUBMITTED")
        return {
            "success": True,
            "transaction_id": txn_id,
            "rrn": rrn,
            "status": status_val,
            "vendor": "paypoint",
            "data": data,
        }

    def mini_statement(
        self,
        aadhaar_number: str,
        mobile_number: str,
        bank_iin: str,
        rd_request: str,
        latitude: str,
        longitude: str,
        terminal_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """AEPS mini statement."""
        result = self.client.mini_statement(
            aadhaar_number=aadhaar_number,
            mobile_number=mobile_number,
            bank_iin=bank_iin,
            rd_request=rd_request,
            latitude=latitude,
            longitude=longitude,
            terminal_id=terminal_id,
            extra_params=extra,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Mini statement failed"),
                "transactions": [],
            }
        data = result.get("data") or {}
        transactions = data.get("transactions") or data.get("mini_statement") or data.get("Transactions") or data.get("MiniStatement") or []
        if not isinstance(transactions, list):
            transactions = [transactions]
        return {
            "success": True,
            "transactions": transactions,
            "vendor": "paypoint",
            "data": data,
        }

    def transaction_status(self, ref_id: str) -> Dict[str, Any]:
        """Get AEPS transaction status by reference id."""
        result = self.client.transaction_status(ref_id=ref_id)
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Status fetch failed"),
                "status": None,
            }
        data = result.get("data") or {}
        return {
            "success": True,
            "ref_id": ref_id,
            "status": data.get("status", "UNKNOWN"),
            "data": data,
        }

    def encrypt(self, use_cache: bool = True) -> Dict[str, Any]:
        """Call PayPoint Encrypt API. Internal use; optional expose for admin/test."""
        return self.client.encrypt(use_cache=use_cache)

    def agent_registration(
        self,
        agent_name: Optional[str] = None,
        mobile_number: Optional[str] = None,
        email: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Agent Registration (PayPoint AEPS)."""
        result = self.client.agent_registration(
            agent_name=agent_name,
            mobile_number=mobile_number,
            email=email,
            extra=extra,
        )
        if not result.get("success"):
            return {"success": False, "message": result.get("error", "Agent registration failed"), "data": result.get("response")}
        return {"success": True, "data": result.get("data"), "vendor": "paypoint"}

    def update_agent_details(
        self,
        agent_id: str,
        agent_name: Optional[str] = None,
        mobile_number: Optional[str] = None,
        email: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update Agent Details (PayPoint AEPS)."""
        result = self.client.update_agent_details(
            agent_id=agent_id,
            agent_name=agent_name,
            mobile_number=mobile_number,
            email=email,
            extra=extra,
        )
        if not result.get("success"):
            return {"success": False, "message": result.get("error", "Update agent failed"), "data": result.get("response")}
        return {"success": True, "data": result.get("data"), "vendor": "paypoint"}

    def check_agent_service_status(
        self,
        agent_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Check Agent Service Status (PayPoint AEPS)."""
        result = self.client.check_agent_service_status(agent_id=agent_id, extra=extra)
        if not result.get("success"):
            return {"success": False, "message": result.get("error", "Check status failed"), "data": result.get("response")}
        return {"success": True, "data": result.get("data"), "vendor": "paypoint"}

    def check_agent_authentication(
        self,
        agent_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Check Agent Authentication (PayPoint AEPS)."""
        result = self.client.check_agent_authentication(agent_id=agent_id, extra=extra)
        if not result.get("success"):
            return {"success": False, "message": result.get("error", "Agent auth check failed"), "data": result.get("response")}
        return {"success": True, "data": result.get("data"), "vendor": "paypoint"}

    def two_factor_authentication(
        self,
        otp: Optional[str] = None,
        mobile_number: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Two Factor Authentication (PayPoint AEPS)."""
        result = self.client.two_factor_authentication(
            otp=otp,
            mobile_number=mobile_number,
            extra=extra,
        )
        if not result.get("success"):
            return {"success": False, "message": result.get("error", "2FA failed"), "data": result.get("response")}
        return {"success": True, "data": result.get("data"), "vendor": "paypoint"}

    def transaction_check_status(self, ref_id: str) -> Dict[str, Any]:
        """Transaction Check Status (PayPoint AEPS). Same as transaction_status; alternate endpoint name."""
        return self.transaction_status(ref_id=ref_id)
