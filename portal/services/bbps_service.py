"""
BBPS (Bharat Bill Payment System) service layer.
Supports multiple vendors: Mobikwik, Euronet. Partner-facing APIs call this service.
"""
from typing import Optional, Dict, Any, List, Union

from portal.services.vendors.mobikwik import MobikwikBBPSClient
from portal.services.vendors.euronet import EuronetBBPSClient
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.bbps_service")

BBPS_VENDOR_MOBIKWIK = "mobikwik"
BBPS_VENDOR_EURONET = "euronet"


def _default_bbps_vendor() -> str:
    """Default vendor: mobikwik (preserve existing behaviour when vendor not specified)."""
    return BBPS_VENDOR_MOBIKWIK


class BBPSService:
    """BBPS service – delegates to Mobikwik or Euronet BBPS client by vendor. Optional test_params override env for testing."""

    def __init__(self, vendor: Optional[str] = None, test_params: Optional[Dict[str, Any]] = None):
        self._vendor = (vendor or _default_bbps_vendor()).lower().strip() or BBPS_VENDOR_MOBIKWIK
        if self._vendor not in (BBPS_VENDOR_MOBIKWIK, BBPS_VENDOR_EURONET):
            self._vendor = BBPS_VENDOR_MOBIKWIK
        self._test_params = test_params or {}
        self._client: Optional[Union[MobikwikBBPSClient, EuronetBBPSClient]] = None

    @property
    def vendor(self) -> str:
        return self._vendor

    def _euronet_kwargs(self) -> Dict[str, Any]:
        """Map test_params keys to EuronetBBPSClient constructor kwargs."""
        p = self._test_params
        return {
            k: p[v]
            for k, v in (
                ("base_url", "base_url"),
                ("merchant_code", "merchant_code"),
                ("username", "username"),
                ("password", "password"),
                ("store_code", "store_code"),
                ("channel_code", "channel_code"),
                ("agent_id", "agent_id"),
                ("salt", "salt"),
                ("encryption_key", "encryption_key"),
            )
            if p.get(v) not in (None, "")
        }

    def _mobikwik_kwargs(self) -> Dict[str, Any]:
        """Map test_params keys to MobikwikBBPSClient constructor kwargs."""
        p = self._test_params
        return {
            k: p[v]
            for k, v in (
                ("base_url", "base_url"),
                ("client_id", "client_id"),
                ("client_secret", "client_secret"),
                ("merchant_id", "merchant_id"),
                ("api_key", "api_key"),
                ("secret_key", "secret_key"),
            )
            if p.get(v) not in (None, "")
        }

    @property
    def client(self) -> Union[MobikwikBBPSClient, EuronetBBPSClient]:
        if self._client is None:
            if self._vendor == BBPS_VENDOR_EURONET:
                self._client = EuronetBBPSClient(**self._euronet_kwargs())
            else:
                self._client = MobikwikBBPSClient(**self._mobikwik_kwargs())
        return self._client

    def is_available(self) -> bool:
        """Return True if the selected BBPS vendor is configured and enabled."""
        return self.client.is_configured()

    def balance_check(self) -> Dict[str, Any]:
        """Balance Check API – get wallet/account balance (new Mobikwik API)."""
        result = self.client.balance_check()
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Balance check failed"),
                "balance": None,
            }
        data = result.get("data") or {}
        return {
            "success": True,
            "balance": data.get("balance") or data.get("availableBalance") or data.get("amount"),
            "vendor": self._vendor,
            "data": data,
        }

    def get_operators(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Get list of billers/operators.
        category: ELECTRICITY, WATER, DTH, MOBILE_PREPAID, etc.
        """
        result = self.client.get_operators(category=category)
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Failed to fetch operators"),
                "operators": [],
            }
        data = result.get("data") or {}
        # Normalise response; Mobikwik may return list under different keys
        operators = (
            data.get("operators")
            or data.get("data")
            or data.get("billers")
            or data.get("rechargePlans")
            or data.get("recharge_plans")
            or data.get("plans")
            or data.get("operatorList")
            or []
        )
        return {
            "success": True,
            "operators": operators if isinstance(operators, list) else [operators],
            "vendor": self._vendor,
        }

    def fetch_bill(
        self,
        operator_id: str,
        customer_id: str,
        subscriber_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch bill details for a consumer."""
        result = self.client.fetch_bill(
            operator_id=operator_id,
            customer_id=customer_id,
            subscriber_id=subscriber_id,
            extra_params=extra,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Bill fetch failed"),
                "bill_details": None,
            }
        data = result.get("data") or {}
        # New API may return billDetails, bill_details, or root fields
        bill_details = data.get("billDetails") or data.get("bill_details") or data
        return {
            "success": True,
            "bill_details": bill_details,
            "vendor": self._vendor,
        }

    def pay_bill(
        self,
        operator_id: str,
        customer_id: str,
        amount: str,
        ref_id: str,
        subscriber_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pay bill and return payment result."""
        result = self.client.pay_bill(
            operator_id=operator_id,
            customer_id=customer_id,
            amount=amount,
            ref_id=ref_id,
            subscriber_id=subscriber_id,
            extra_params=extra,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Payment failed"),
                "transaction_id": None,
                "status": "FAILED",
            }
        data = result.get("data") or {}
        status_val = data.get("status") or data.get("transactionStatus") or "SUBMITTED"
        txn_id = data.get("transactionId") or data.get("transaction_id") or data.get("refId") or data.get("ref_id") or ref_id
        return {
            "success": True,
            "transaction_id": txn_id,
            "status": status_val,
            "vendor": self._vendor,
            "data": data,
        }

    def payment_status(self, ref_id: str) -> Dict[str, Any]:
        """Get payment status by reference id."""
        result = self.client.pay_status(ref_id=ref_id)
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Status fetch failed"),
                "status": None,
            }
        data = result.get("data") or {}
        status_val = data.get("status") or data.get("transactionStatus") or "UNKNOWN"
        return {
            "success": True,
            "ref_id": ref_id,
            "status": status_val,
            "data": data,
        }
