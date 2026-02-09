"""
PayPoint DMT (Domestic Money Transfer) API client.
Official docs: https://docs.paypointindia.co.in/api/paypoint-dmt-api/dmt-api/overview

- RESTful API, application/json, HTTP POST for all requests.
- UserCode, Password, IdentificationCode must be encrypted using the "Encrypt" API
  before passing in every DMT request (same mechanism as PayPoint AEPS).
- Client IPs must be whitelisted by PayPoint to access the API.

Endpoint paths (align with PayPoint DMT API doc; adjust if contract differs):
- POST /api/Encrypt – get encrypted credentials (internal)
- POST /api/RegisterSender – sender/remitter registration
- POST /api/AddBeneficiary – add beneficiary
- POST /api/Remit – money transfer
- POST /api/TransactionStatus – transaction status
- POST /api/GetBeneficiaries – list beneficiaries
"""
from typing import Optional, Dict, Any, List

import httpx
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.vendors.paypoint_dmt")


def _secret_value(val) -> Optional[str]:
    if val is None:
        return None
    if hasattr(val, "get_secret_value"):
        return val.get_secret_value()
    return str(val)


class PayPointDMTClient:
    """
    PayPoint India DMT API client.
    Uses Encrypt API to get encrypted UserCode, Password, IdentificationCode, then
    passes them in each DMT request. Paths and field names should be aligned with
    PayPoint's DMT API documentation.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        user_code: Optional[str] = None,
        password: Optional[str] = None,
        identification_code: Optional[str] = None,
        key: Optional[str] = None,
    ):
        from core.config import payswap_config

        self.base_url = (base_url or getattr(
            payswap_config, "PAYPOINT_DMT_BASE_URL", "https://api.paypointindia.co.in"
        )).rstrip("/")
        self.user_code = user_code or getattr(
            payswap_config, "PAYPOINT_DMT_USER_CODE", None
        )
        self.password = password or _secret_value(
            getattr(payswap_config, "PAYPOINT_DMT_PASSWORD", None)
        )
        self.identification_code = identification_code or getattr(
            payswap_config, "PAYPOINT_DMT_IDENTIFICATION_CODE", None
        )
        self.key = key or _secret_value(
            getattr(payswap_config, "PAYPOINT_DMT_KEY", None)
        )
        self.enabled = getattr(payswap_config, "PAYPOINT_DMT_ENABLED", False)
        self._encrypted_cache: Optional[Dict[str, str]] = None

    def is_configured(self) -> bool:
        return bool(
            self.enabled
            and self.user_code
            and self.password
            and self.identification_code
            and self.key
        )

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        base = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if extra:
            base.update(extra)
        return base

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "success": False,
                "error": "PAYPOINT_DMT is not configured or enabled",
                "error_code": "CONFIG_MISSING",
            }
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(
                    method,
                    url,
                    json=json_data,
                    params=params,
                    headers=self._headers(),
                )
                data = resp.json() if resp.content else {}
                if resp.status_code >= 400:
                    return {
                        "success": False,
                        "error": data.get("message", data.get("error", data.get("Message", resp.text))),
                        "status_code": resp.status_code,
                        "response": data,
                    }
                return {"success": True, "data": data, "status_code": resp.status_code}
        except httpx.TimeoutException as e:
            logger.warning("PayPoint DMT request timeout", extra={"url": url, "error": str(e)})
            return {"success": False, "error": "Request timeout", "error_code": "TIMEOUT"}
        except Exception as e:
            logger.exception("PayPoint DMT request failed")
            return {"success": False, "error": str(e), "error_code": "REQUEST_FAILED"}

    def encrypt(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Call PayPoint Encrypt API (same as AEPS). Required before every DMT request.
        """
        if use_cache and self._encrypted_cache:
            return {"success": True, "data": self._encrypted_cache}
        path = "/api/Encrypt"
        payload = {
            "UserCode": self.user_code,
            "Password": self.password,
            "IdentificationCode": self.identification_code,
            "Key": self.key,
        }
        result = self._request("POST", path, json_data=payload)
        if result.get("success") and result.get("data"):
            data = result["data"]
            enc_user = data.get("EncryptedUserCode") or data.get("UserCode") or data.get("userCode")
            enc_pass = data.get("EncryptedPassword") or data.get("Password") or data.get("password")
            enc_id = data.get("EncryptedIdentificationCode") or data.get("IdentificationCode") or data.get("identificationCode")
            if enc_user is not None and enc_pass is not None and enc_id is not None:
                self._encrypted_cache = {
                    "UserCode": enc_user,
                    "Password": enc_pass,
                    "IdentificationCode": enc_id,
                }
                result["data"] = self._encrypted_cache
        return result

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
        """DMT sender/remitter registration. Field names align with typical DMT; adjust per PayPoint doc."""
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        payload = {
            **enc["data"],
            "Key": self.key,
            "MobileNumber": mobile_number,
            "FirstName": first_name,
            "LastName": last_name,
        }
        if pincode is not None:
            payload["Pincode"] = pincode
        if state is not None:
            payload["State"] = state
        if address is not None:
            payload["Address"] = address
        if date_of_birth is not None:
            payload["DateOfBirth"] = date_of_birth
        if extra:
            payload.update(extra)
        path = "/api/RegisterSender"
        return self._request("POST", path, json_data=payload)

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
        """Add beneficiary for DMT. Adjust field names per PayPoint DMT API doc."""
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        payload = {
            **enc["data"],
            "Key": self.key,
            "SenderMobile": sender_mobile,
            "BeneficiaryName": beneficiary_name,
            "AccountNumber": account_number,
            "IFSC": ifsc,
        }
        if mobile_number is not None:
            payload["MobileNumber"] = mobile_number
        if bank_name is not None:
            payload["BankName"] = bank_name
        if extra:
            payload.update(extra)
        path = "/api/AddBeneficiary"
        return self._request("POST", path, json_data=payload)

    def remit(
        self,
        sender_mobile: str,
        beneficiary_id: str,
        amount: str,
        client_ref_id: Optional[str] = None,
        remarks: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute DMT remittance. Amount as string; adjust params per PayPoint doc."""
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        payload = {
            **enc["data"],
            "Key": self.key,
            "SenderMobile": sender_mobile,
            "BeneficiaryId": beneficiary_id,
            "Amount": amount,
        }
        if client_ref_id is not None:
            payload["ClientRefId"] = client_ref_id
        if remarks is not None:
            payload["Remarks"] = remarks
        if extra:
            payload.update(extra)
        path = "/api/Remit"
        return self._request("POST", path, json_data=payload)

    def transaction_status(self, ref_id: str) -> Dict[str, Any]:
        """DMT transaction status by reference id."""
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        path = "/api/TransactionStatus"
        payload = {**enc["data"], "Key": self.key, "ReferenceId": ref_id}
        return self._request("POST", path, json_data=payload)

    def get_beneficiaries(
        self,
        sender_mobile: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get list of beneficiaries for a sender. Path/fields per PayPoint DMT doc."""
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        payload = {**enc["data"], "Key": self.key, "SenderMobile": sender_mobile}
        if extra:
            payload.update(extra)
        path = "/api/GetBeneficiaries"
        return self._request("POST", path, json_data=payload)
