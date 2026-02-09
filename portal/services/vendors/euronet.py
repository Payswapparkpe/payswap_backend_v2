"""
Euronet BBPS (Bharat Connect / EFT APME) API client.

Single endpoint: EnService (POST). Request body: serviceType, merchantCode, username,
password, storeCode, channelCode, agentId, salt; plus operation-specific fields.
UAT: https://epayuat.eftapme.com/ENServiceAES256/API/EnService

Credentials from .env (EURONET_BBPS_*). Request/response schema to be aligned with
Euronet API spec once available; this stub follows the Postman collection structure.
"""
import json
from typing import Any, Dict, Optional

import httpx
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.vendors.euronet")


def _secret_value(val) -> Optional[str]:
    if val is None:
        return None
    if hasattr(val, "get_secret_value"):
        return val.get_secret_value()
    return str(val)


class EuronetBBPSClient:
    """
    Euronet BBPS API client – single EnService endpoint.
    Methods: balance_check, get_operators, fetch_bill, pay_bill, pay_status.
    """

    SERVICE_TYPES = {
        "balance": "BALANCE_ENQUIRY",
        "get_billers": "GET_BILLERS",
        "fetch_bill": "FETCH_BILL",
        "pay_bill": "PAY_BILL",
        "transaction_status": "TRANSACTION_STATUS",
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        merchant_code: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        store_code: Optional[str] = None,
        channel_code: Optional[str] = None,
        agent_id: Optional[str] = None,
        salt: Optional[str] = None,
        encryption_key: Optional[str] = None,
    ):
        from core.config import payswap_config

        cfg = payswap_config
        self.base_url = (
            base_url or getattr(cfg, "EURONET_BBPS_BASE_URL", "https://epayuat.eftapme.com/ENServiceAES256/API")
        ).rstrip("/")
        self.enabled = getattr(cfg, "EURONET_BBPS_ENABLED", False)
        self.merchant_code = merchant_code or getattr(cfg, "EURONET_BBPS_MERCHANT_CODE", None)
        self.username = username or getattr(cfg, "EURONET_BBPS_USERNAME", None)
        self.password = _secret_value(password or getattr(cfg, "EURONET_BBPS_PASSWORD", None))
        self.store_code = store_code or getattr(cfg, "EURONET_BBPS_STORE_CODE", None)
        self.channel_code = channel_code or getattr(cfg, "EURONET_BBPS_CHANNEL_CODE", "INT")
        self.agent_id = agent_id or getattr(cfg, "EURONET_BBPS_AGENT_ID", None)
        self.salt = salt or getattr(cfg, "EURONET_BBPS_SALT", None)
        self.encryption_key = _secret_value(
            encryption_key or getattr(cfg, "EURONET_BBPS_ENCRYPTION_KEY", None)
        )
        self._en_service_url = f"{self.base_url}/EnService"

    def is_configured(self) -> bool:
        """Return True if credentials are set and integration is enabled."""
        return bool(
            self.enabled
            and self.base_url
            and self.merchant_code
            and self.username
            and self.password
            and self.store_code
            and self.agent_id
        )

    def _base_payload(self, service_type: str) -> Dict[str, Any]:
        """Common fields for every EnService request (per Postman collection)."""
        return {
            "serviceType": service_type,
            "merchantCode": self.merchant_code or "",
            "username": self.username or "",
            "password": self.password or "",
            "storeCode": self.store_code or "",
            "channelCode": self.channel_code or "INT",
            "agentId": self.agent_id or "",
            "salt": self.salt or "",
        }

    def _post(self, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """POST to EnService and return { success, data, error, status_code }."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "Euronet BBPS is not configured or enabled",
                "error_code": "CONFIG_MISSING",
            }
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    self._en_service_url,
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
            raw = resp.text
            try:
                data = resp.json() if resp.content else {}
            except (ValueError, json.JSONDecodeError):
                data = {"_raw": raw[:500]}
            if resp.status_code >= 400:
                err = data.get("message") or data.get("error") or data.get("msg") or raw or f"HTTP {resp.status_code}"
                if isinstance(err, dict):
                    err = err.get("message") or str(err)
                logger.warning(
                    "Euronet BBPS EnService error",
                    extra_data={"status_code": resp.status_code, "payload_service_type": payload.get("serviceType"), "error": str(err)[:200]},
                )
                return {
                    "success": False,
                    "error": str(err)[:500],
                    "status_code": resp.status_code,
                    "response": data,
                }
            return {"success": True, "data": data, "status_code": resp.status_code}
        except httpx.TimeoutException as e:
            logger.warning("Euronet BBPS request timeout", extra_data={"url": self._en_service_url, "error": str(e)})
            return {"success": False, "error": "Request timeout", "error_code": "TIMEOUT"}
        except Exception as e:
            logger.error("Euronet BBPS request failed", extra_data={"error": str(e)})
            return {"success": False, "error": str(e), "error_code": "REQUEST_FAILED"}

    def balance_check(self) -> Dict[str, Any]:
        """Balance Enquiry – serviceType BALANCE_ENQUIRY."""
        payload = self._base_payload(self.SERVICE_TYPES["balance"])
        return self._post(payload)

    def get_operators(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get list of billers/operators – serviceType GET_BILLERS. category optional (if API supports)."""
        payload = self._base_payload(self.SERVICE_TYPES["get_billers"])
        if category:
            payload["category"] = category
        return self._post(payload)

    def fetch_bill(
        self,
        operator_id: str,
        customer_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch bill – serviceType FETCH_BILL; billerId = operator_id, consumerId = customer_id."""
        payload = self._base_payload(self.SERVICE_TYPES["fetch_bill"])
        payload["billerId"] = operator_id
        payload["consumerId"] = customer_id
        if subscriber_id:
            payload["subscriberId"] = subscriber_id
        if extra_params:
            for k, v in extra_params.items():
                if v not in (None, ""):
                    payload[k] = v
        return self._post(payload)

    def pay_bill(
        self,
        operator_id: str,
        customer_id: str,
        amount: str,
        ref_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pay bill – serviceType PAY_BILL."""
        payload = self._base_payload(self.SERVICE_TYPES["pay_bill"])
        payload["billerId"] = operator_id
        payload["consumerId"] = customer_id
        payload["amount"] = amount
        payload["refId"] = ref_id
        if subscriber_id:
            payload["subscriberId"] = subscriber_id
        if extra_params:
            for k, v in extra_params.items():
                if k not in ("billerId", "consumerId", "amount", "refId"):
                    if v not in (None, ""):
                        payload[k] = v
        return self._post(payload)

    def pay_status(self, ref_id: str) -> Dict[str, Any]:
        """Transaction status – serviceType TRANSACTION_STATUS."""
        payload = self._base_payload(self.SERVICE_TYPES["transaction_status"])
        payload["refId"] = ref_id
        return self._post(payload)
