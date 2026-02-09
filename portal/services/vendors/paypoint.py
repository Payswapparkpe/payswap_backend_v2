"""
PayPoint AEPS (Aadhaar Enabled Payment System) API client.
Official docs: https://docs.paypointindia.co.in/api/paypoint-aeps-api/paypoint/overview

- RESTful API, application/json, HTTP POST for all requests.
- UserCode, Password, IdentificationCode & Key are provided by PayPoint.
- UserCode, Password & IdentificationCode must be encrypted using the "Encrypt" API
  call before passing in every AEPS request.
- Client IPs must be whitelisted by PayPoint to access the API.
"""
from typing import Optional, Dict, Any

import httpx
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.vendors.paypoint")


def _secret_value(val) -> Optional[str]:
    """Get secret string value (SecretStr or plain str)."""
    if val is None:
        return None
    if hasattr(val, "get_secret_value"):
        return val.get_secret_value()
    return str(val)


class PayPointAEPSClient:
    """
    PayPoint India AEPS API client.
    Uses Encrypt API to get encrypted credentials, then passes them in each AEPS request.
    Endpoint paths and request/response fields should be aligned with PayPoint's full API doc.
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
            payswap_config, "PAYPOINT_AEPS_BASE_URL", "https://api.paypointindia.co.in"
        )).rstrip("/")
        self.user_code = user_code or getattr(
            payswap_config, "PAYPOINT_AEPS_USER_CODE", None
        )
        self.password = password or _secret_value(
            getattr(payswap_config, "PAYPOINT_AEPS_PASSWORD", None)
        )
        self.identification_code = identification_code or getattr(
            payswap_config, "PAYPOINT_AEPS_IDENTIFICATION_CODE", None
        )
        self.key = key or _secret_value(
            getattr(payswap_config, "PAYPOINT_AEPS_KEY", None)
        )
        self.enabled = getattr(payswap_config, "PAYPOINT_AEPS_ENABLED", False)
        self._encrypted_cache: Optional[Dict[str, str]] = None

    def is_configured(self) -> bool:
        """Return True if credentials are set and integration is enabled."""
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
        """Make HTTP request to PayPoint AEPS API. All calls use POST per docs."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "PAYPOINT_AEPS is not configured or enabled",
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
            logger.warning("PayPoint AEPS request timeout", extra={"url": url, "error": str(e)})
            return {"success": False, "error": "Request timeout", "error_code": "TIMEOUT"}
        except Exception as e:
            logger.exception("PayPoint AEPS request failed")
            return {"success": False, "error": str(e), "error_code": "REQUEST_FAILED"}

    def encrypt(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Call PayPoint Encrypt API to get encrypted UserCode, Password, IdentificationCode.
        Per docs: these must be encrypted before passing in every AEPS request.
        Exact request/response keys may vary – adjust to match PayPoint API doc.
        """
        if use_cache and self._encrypted_cache:
            return {"success": True, "data": self._encrypted_cache}
        # Path as per PayPoint docs; adjust if they use different path (e.g. /Encrypt, /api/Encrypt)
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
            # Accept common response key names; update to match actual API response
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

    def _aeps_payload(
        self,
        encrypted: Dict[str, str],
        aadhaar_number: str,
        mobile_number: str,
        bank_iin: str,
        rd_request: str,
        latitude: str,
        longitude: str,
        transaction_type: str,
        amount: Optional[str] = None,
        terminal_id: Optional[str] = None,
        client_ref_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build AEPS request body with encrypted credentials. Field names align with typical AEPS; adjust per PayPoint doc."""
        payload = {
            **encrypted,
            "Key": self.key,
            "AadhaarNumber": aadhaar_number,
            "MobileNumber": mobile_number,
            "BankIIN": bank_iin,
            "RdRequest": rd_request,
            "Latitude": latitude,
            "Longitude": longitude,
            "TransactionType": transaction_type,
        }
        if amount is not None:
            payload["Amount"] = amount
        if terminal_id:
            payload["TerminalId"] = terminal_id
        if client_ref_id:
            payload["ClientRefId"] = client_ref_id
        if extra:
            payload.update(extra)
        return payload

    def balance_enquiry(
        self,
        aadhaar_number: str,
        mobile_number: str,
        bank_iin: str,
        rd_request: str,
        latitude: str,
        longitude: str,
        terminal_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """AEPS balance enquiry. Uses Encrypt API then POST to balance endpoint."""
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        payload = self._aeps_payload(
            enc["data"],
            aadhaar_number=aadhaar_number,
            mobile_number=mobile_number,
            bank_iin=bank_iin,
            rd_request=rd_request,
            latitude=latitude,
            longitude=longitude,
            transaction_type="BE",
            terminal_id=terminal_id,
            extra=extra_params,
        )
        path = "/api/BalanceEnquiry"
        return self._request("POST", path, json_data=payload)

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
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """AEPS cash withdrawal. Uses Encrypt API then POST to withdrawal endpoint."""
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        payload = self._aeps_payload(
            enc["data"],
            aadhaar_number=aadhaar_number,
            mobile_number=mobile_number,
            bank_iin=bank_iin,
            rd_request=rd_request,
            latitude=latitude,
            longitude=longitude,
            transaction_type="CW",
            amount=amount,
            terminal_id=terminal_id,
            client_ref_id=client_ref_id,
            extra=extra_params,
        )
        path = "/api/CashWithdrawal"
        return self._request("POST", path, json_data=payload)

    def mini_statement(
        self,
        aadhaar_number: str,
        mobile_number: str,
        bank_iin: str,
        rd_request: str,
        latitude: str,
        longitude: str,
        terminal_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """AEPS mini statement. Uses Encrypt API then POST to mini statement endpoint."""
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        payload = self._aeps_payload(
            enc["data"],
            aadhaar_number=aadhaar_number,
            mobile_number=mobile_number,
            bank_iin=bank_iin,
            rd_request=rd_request,
            latitude=latitude,
            longitude=longitude,
            transaction_type="MS",
            terminal_id=terminal_id,
            extra=extra_params,
        )
        path = "/api/MiniStatement"
        return self._request("POST", path, json_data=payload)

    def transaction_status(self, ref_id: str) -> Dict[str, Any]:
        """AEPS transaction status by reference. May require encrypted credentials in body – adjust per PayPoint doc."""
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        path = "/api/TransactionStatus"
        payload = {**enc["data"], "Key": self.key, "ReferenceId": ref_id}
        return self._request("POST", path, json_data=payload)

    # -------------------------------------------------------------------------
    # Agent & Auth APIs (paths per PayPoint AEPS API doc – adjust if different)
    # https://docs.paypointindia.co.in/api/paypoint-aeps-api/paypoint/overview
    # -------------------------------------------------------------------------

    def agent_registration(
        self,
        agent_name: Optional[str] = None,
        mobile_number: Optional[str] = None,
        email: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Agent Registration. Encrypted credentials + agent details.
        Path/fields to be confirmed from PayPoint API doc.
        """
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        path = "/api/AgentRegistration"
        payload = {**enc["data"], "Key": self.key}
        if agent_name is not None:
            payload["AgentName"] = agent_name
        if mobile_number is not None:
            payload["MobileNumber"] = mobile_number
        if email is not None:
            payload["Email"] = email
        if extra:
            payload.update(extra)
        return self._request("POST", path, json_data=payload)

    def update_agent_details(
        self,
        agent_id: str,
        agent_name: Optional[str] = None,
        mobile_number: Optional[str] = None,
        email: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update Agent Details. Encrypted credentials + agent id + updated fields.
        Path/fields per PayPoint API doc.
        """
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        path = "/api/UpdateAgentDetails"
        payload = {**enc["data"], "Key": self.key, "AgentId": agent_id}
        if agent_name is not None:
            payload["AgentName"] = agent_name
        if mobile_number is not None:
            payload["MobileNumber"] = mobile_number
        if email is not None:
            payload["Email"] = email
        if extra:
            payload.update(extra)
        return self._request("POST", path, json_data=payload)

    def check_agent_service_status(
        self,
        agent_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Check Agent Service Status. Encrypted credentials; optional agent id.
        Path per PayPoint API doc.
        """
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        path = "/api/AgentServiceStatus"
        payload = {**enc["data"], "Key": self.key}
        if agent_id:
            payload["AgentId"] = agent_id
        if extra:
            payload.update(extra)
        return self._request("POST", path, json_data=payload)

    def check_agent_authentication(
        self,
        agent_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Check Agent Authentication. Encrypted credentials; optional agent id.
        Path per PayPoint API doc.
        """
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        path = "/api/AgentAuthentication"
        payload = {**enc["data"], "Key": self.key}
        if agent_id:
            payload["AgentId"] = agent_id
        if extra:
            payload.update(extra)
        return self._request("POST", path, json_data=payload)

    def two_factor_authentication(
        self,
        otp: Optional[str] = None,
        mobile_number: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Two Factor Authentication (2FA). Encrypted credentials + OTP/mobile as per PayPoint doc.
        Path per PayPoint API doc.
        """
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        path = "/api/TwoFactorAuthentication"
        payload = {**enc["data"], "Key": self.key}
        if otp is not None:
            payload["OTP"] = otp
        if mobile_number is not None:
            payload["MobileNumber"] = mobile_number
        if extra:
            payload.update(extra)
        return self._request("POST", path, json_data=payload)

    def transaction_check_status(self, ref_id: str) -> Dict[str, Any]:
        """
        Transaction Check Status. Alias for transaction_status; some docs use this name.
        PayPoint may expose /api/TransactionCheckStatus – same as TransactionStatus.
        """
        # Try TransactionCheckStatus first if PayPoint uses it; else same as transaction_status
        enc = self.encrypt()
        if not enc.get("success"):
            return enc
        path = "/api/TransactionCheckStatus"
        payload = {**enc["data"], "Key": self.key, "ReferenceId": ref_id}
        return self._request("POST", path, json_data=payload)
