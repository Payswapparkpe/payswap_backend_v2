"""
BBPS (Bharat Bill Payment System) service layer.
Supports Mobikwik. Partner-facing APIs call this service.
"""
from typing import Optional, Dict, Any, List

from portal.services.vendors.mobikwik import MobikwikBBPSClient
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.bbps_service")

BBPS_VENDOR_MOBIKWIK = "mobikwik"


class BBPSService:
    """BBPS service – delegates to Mobikwik BBPS client. Optional test_params override env for testing."""

    def __init__(self, vendor: Optional[str] = None, test_params: Optional[Dict[str, Any]] = None):
        self._vendor = BBPS_VENDOR_MOBIKWIK
        self._test_params = test_params or {}
        self._client: Optional[MobikwikBBPSClient] = None

    @property
    def vendor(self) -> str:
        return self._vendor

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
    def client(self) -> MobikwikBBPSClient:
        if self._client is None:
            self._client = MobikwikBBPSClient(**self._mobikwik_kwargs())
        return self._client

    def is_available(self) -> bool:
        """Return True if the selected BBPS vendor is configured and enabled."""
        return self.client.is_configured()

    def _extract_balance(self, obj: Any) -> Optional[Any]:
        """Extract balance from API response – top-level or nested data, various key names."""
        if not isinstance(obj, dict):
            return None
        keys = ("balance", "availableBalance", "amount", "walletBalance", "retailerBalance", "available_balance")
        for k in keys:
            v = obj.get(k)
            if v is not None and v != "":
                try:
                    if isinstance(v, (int, float)):
                        return float(v)
                    if isinstance(v, str) and v.strip():
                        return float(v.strip())
                except (ValueError, TypeError):
                    continue
        # Nested: data.data.balance (Mobikwik sometimes wraps in data)
        nested = obj.get("data")
        if isinstance(nested, dict):
            return self._extract_balance(nested)
        return None

    def balance_check(self, log_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Balance Check API – get wallet/account balance (new Mobikwik API)."""
        result = self.client.balance_check(log_context=log_context)
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Balance check failed"),
                "balance": None,
            }
        data = result.get("data") or {}
        if data.get("success") is False:
            msg = data.get("message")
            if isinstance(msg, dict):
                msg = msg.get("text") or msg.get("message") or str(msg)
            return {
                "success": False,
                "message": msg or "Balance check failed",
                "balance": None,
            }
        balance = self._extract_balance(data)
        return {
            "success": True,
            "balance": balance,
            "vendor": self._vendor,
            "data": data,
        }

    def get_operators(self, category: Optional[str] = None, log_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get list of billers/operators.
        category: ELECTRICITY, WATER, DTH, MOBILE_PREPAID, etc.
        """
        result = self.client.get_operators(category=category, log_context=log_context)
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
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch bill details for a consumer."""
        result = self.client.fetch_bill(
            operator_id=operator_id,
            customer_id=customer_id,
            subscriber_id=subscriber_id,
            extra_params=extra,
            log_context=log_context,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Bill fetch failed"),
                "bill_details": None,
            }
        raw_data = result.get("data")
        # Normalize: upstream may return full body dict or (rarely) list; avoid .get on list (UAT: body is {"success", "data": [...]})
        if isinstance(raw_data, list):
            data = {"success": True, "data": raw_data}
        elif isinstance(raw_data, dict):
            data = raw_data
        else:
            data = {}
        # Mobikwik returns HTTP 200 but body can have success: false (e.g. code 900)
        if data.get("success") is False:
            msg = data.get("message")
            if isinstance(msg, dict):
                msg = msg.get("text") or msg.get("message") or str(msg)
            return {
                "success": False,
                "message": msg or "Bill fetch failed",
                "bill_details": None,
            }
        # Mobikwik View Bill per UAT §7: {"success": true, "data": [{"billAmount", "billdate", "dueDate", "userName", ...}]}
        bill_details = data.get("billDetails") or data.get("bill_details")
        if bill_details is None and isinstance(data.get("data"), list) and data["data"]:
            # Mobikwik returns bill in data[0]; merge nested Data.dueDate etc. into flat dict
            item = data["data"][0]
            if isinstance(item, dict):
                bill_details = dict(item)
                nested = bill_details.get("Data") or bill_details.get("data")
                if isinstance(nested, dict):
                    bill_details["dueDate"] = bill_details.get("dueDate") or nested.get("dueDate")
                    bill_details["due_date"] = bill_details.get("due_date") or nested.get("due_date")
                    bill_details.pop("Data", None)
                    bill_details.pop("data", None)
        if bill_details is None:
            # Empty data array per UAT: treat as no bill found
            if isinstance(data.get("data"), list) and len(data.get("data", [])) == 0:
                return {
                    "success": False,
                    "message": "No bill details found for this consumer.",
                    "bill_details": None,
                    "vendor": self._vendor,
                }
            bill_details = data
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
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pay bill and return payment result."""
        result = self.client.pay_bill(
            operator_id=operator_id,
            customer_id=customer_id,
            amount=amount,
            ref_id=ref_id,
            subscriber_id=subscriber_id,
            extra_params=extra,
            log_context=log_context,
        )
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Payment failed"),
                "transaction_id": None,
                "status": "FAILED",
            }
        data = result.get("data") or {}
        # Mobikwik can return HTTP 200 with success: false in body (e.g. code 900)
        if data.get("success") is False:
            msg = data.get("message")
            if isinstance(msg, dict):
                msg = msg.get("text") or msg.get("message") or str(msg)
            return {
                "success": False,
                "message": msg or "Payment failed",
                "transaction_id": None,
                "status": "FAILED",
            }
        status_val = (
            data.get("status")
            or data.get("txStatus")
            or data.get("transactionStatus")
            or "SUBMITTED"
        )
        txn_id = (
            data.get("txId")
            or data.get("transactionId")
            or data.get("transaction_id")
            or data.get("refId")
            or data.get("ref_id")
            or data.get("mobikwikrefno")
            or ref_id
        )
        return {
            "success": True,
            "transaction_id": txn_id,
            "status": status_val,
            "vendor": self._vendor,
            "data": data,
        }

    def payment_status(self, ref_id: str, log_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get payment status by reference id."""
        result = self.client.pay_status(ref_id=ref_id, log_context=log_context)
        if not result.get("success"):
            return {
                "success": False,
                "message": result.get("error", "Status fetch failed"),
                "status": None,
            }
        data = result.get("data") or {}
        if data.get("success") is False:
            msg = data.get("message")
            if isinstance(msg, dict):
                msg = msg.get("text") or msg.get("message") or str(msg)
            return {
                "success": False,
                "message": msg or "Status fetch failed",
                "status": None,
            }
        status_val = (
            data.get("status")
            or data.get("txStatus")
            or data.get("transactionStatus")
            or "UNKNOWN"
        )
        return {
            "success": True,
            "ref_id": ref_id,
            "status": status_val,
            "data": data,
        }
