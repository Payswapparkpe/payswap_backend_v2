"""
Mobikwik BBPS (Bharat Bill Payment System) API client – New API (UAT/Onboarding docs).

New integration uses:
- Token Generation API (Client ID + Client Secret) for auth.
- Encrypted request body: encryptedSessionKey, encryptedPayload, keyVersion, iv.
- APIs: Token, Balance Check, Validation, View Bill, Recharge, Transaction Status Check.

Credentials and base URL from .env (MOBIKWIK_BBPS_*).
Exact endpoint paths and encryption algorithm must be confirmed from Mobikwik API Kit.
"""
import hashlib
import json
import time
from base64 import b64encode
from typing import Any, Dict, Optional, Union

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.vendors.mobikwik")

# Default API paths from Mobikwik RT-Recharge & Bill Payment API Documentation
# Base URL (testing): https://alpha3.mobikwik.com
DEFAULT_PATHS = {
    "token": "/recharge/v1/verify/retailer",
    "balance": "/recharge/v3/retailerBalance",
    "validation": "/recharge/v3/retailerValidation",
    "view_bill": "/recharge/v3/retailerViewbill",
    "recharge": "/recharge/v3/retailerPayment",
    "transaction_status": "/recharge/v3/retailerStatus",
    "operators": "/recharge/v1/rechargePlansAPI",
}


def _secret_value(val) -> Optional[str]:
    """Get secret string value (SecretStr or plain str)."""
    if val is None:
        return None
    if hasattr(val, "get_secret_value"):
        return val.get_secret_value()
    return str(val)


class MobikwikBBPSClient:
    """
    Mobikwik BBPS API client (new API).
    - Auth: Token Generation (Client ID + Client Secret); token used in subsequent calls.
    - Request body: Encrypted format (encryptedSessionKey, encryptedPayload, keyVersion, iv) when encryption enabled.
    - APIs: get_token, balance_check, validation (bill fetch), view_bill, recharge (pay), transaction_status.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        merchant_id: Optional[str] = None,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        use_encryption: Optional[bool] = None,
        public_key_pem: Optional[str] = None,
        key_version: Optional[str] = None,
    ):
        from core.config import payswap_config

        cfg = payswap_config
        self.client_id = client_id or _secret_value(getattr(cfg, "MOBIKWIK_BBPS_CLIENT_ID", None))
        self.client_secret = client_secret or _secret_value(getattr(cfg, "MOBIKWIK_BBPS_CLIENT_SECRET", None))
        self.merchant_id = merchant_id or getattr(cfg, "MOBIKWIK_BBPS_MERCHANT_ID", None)
        self.api_key = api_key or _secret_value(getattr(cfg, "MOBIKWIK_BBPS_API_KEY", None))
        self.secret_key = secret_key or _secret_value(getattr(cfg, "MOBIKWIK_BBPS_SECRET_KEY", None))
        self.base_url = (
            base_url or getattr(cfg, "MOBIKWIK_BBPS_BASE_URL", "https://alpha3.mobikwik.com")
        ).rstrip("/")
        self.enabled = getattr(cfg, "MOBIKWIK_BBPS_ENABLED", False)
        self.use_encryption = (
            use_encryption
            if use_encryption is not None
            else getattr(cfg, "MOBIKWIK_BBPS_USE_ENCRYPTION", False)
        )
        self.public_key_pem = public_key_pem or _secret_value(
            getattr(cfg, "MOBIKWIK_BBPS_PUBLIC_KEY", None)
        )
        if not self.public_key_pem:
            key_path = getattr(cfg, "MOBIKWIK_BBPS_PUBLIC_KEY_PATH", None)
            if key_path:
                self.public_key_pem = self._load_public_key_from_path(key_path)
        self.key_version = key_version or getattr(cfg, "MOBIKWIK_BBPS_KEY_VERSION", "1.0")
        self._paths = getattr(cfg, "MOBIKWIK_BBPS_PATHS", None) or DEFAULT_PATHS
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._token_ttl_seconds = 300  # refresh 5 min before expiry if we had expiry from response
        self._last_token_error: Optional[str] = None  # actual error when token fails (for logging/UI)

    def is_configured(self) -> bool:
        """Return True if credentials are set and integration is enabled."""
        has_token_creds = bool(self.client_id and self.client_secret)
        has_legacy_creds = bool(self.merchant_id and self.api_key and self.secret_key)
        return bool(
            self.enabled
            and self.base_url
            and (has_token_creds or has_legacy_creds)
        )

    def _get_path(self, name: str) -> str:
        return self._paths.get(name) or DEFAULT_PATHS.get(name, f"/api/v1/{name}")

    @staticmethod
    def _op_int(operator_id: Union[str, int]) -> Union[str, int]:
        """Mobikwik expects 'op' as Integer. Return int when operator_id is int or digit string."""
        if isinstance(operator_id, int):
            return operator_id
        if isinstance(operator_id, str) and operator_id.strip().isdigit():
            return int(operator_id.strip())
        return operator_id

    def _load_public_key_from_path(self, key_path: str) -> Optional[str]:
        """Load PEM content from file path. Path can be absolute or relative to project root (BASE_DIR)."""
        import os
        from django.conf import settings
        if not key_path:
            return None
        path = key_path
        if not os.path.isabs(path):
            base = getattr(settings, "BASE_DIR", None)
            if base:
                path = os.path.join(base, key_path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error("Mobikwik BBPS: failed to load public key from path", extra_data={"path": key_path, "error": str(e)})
            return None

    # -------------------------------------------------------------------------
    # Token (new API)
    # -------------------------------------------------------------------------

    def get_token(self) -> Dict[str, Any]:
        """
        Token Generation API – get access token using Client ID + Client Secret.
        Required before Balance Check, Validation, View Bill, Recharge, Transaction Status.
        """
        if not self.client_id or not self.client_secret:
            return {
                "success": False,
                "error": "MOBIKWIK_BBPS_CLIENT_ID and MOBIKWIK_BBPS_CLIENT_SECRET are required for token",
                "error_code": "CONFIG_MISSING",
            }
        # Token path: override via MOBIKWIK_BBPS_TOKEN_PATH (per Mobikwik RT-Recharge & Bill Payment API doc) or use default
        from core.config import payswap_config
        token_path = getattr(payswap_config, "MOBIKWIK_BBPS_TOKEN_PATH", None)
        path = (token_path or self._get_path("token")).strip().lstrip("/")
        base = self.base_url.rstrip("/")
        # Some servers require trailing slash for POST
        url = f"{base}/{path}/" if path else (base + "/")
        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
            # Parse JSON safely; server may return HTML or empty body
            try:
                data = resp.json() if resp.content else {}
            except (ValueError, json.JSONDecodeError):
                raw = (resp.text or resp.content.decode("utf-8", errors="replace") if resp.content else "")[:500]
                self._last_token_error = (
                    f"HTTP {resp.status_code}: non-JSON response. URL: {url} | Response: {raw[:200]}..."
                )
                return {
                    "success": False,
                    "error": self._last_token_error,
                    "status_code": resp.status_code,
                    "response": {"_url": url, "_raw_preview": raw[:300]},
                }
            if resp.status_code >= 400:
                err_msg = data.get("message") or data.get("error") or data.get("msg") or resp.text or f"HTTP {resp.status_code}"
                if isinstance(err_msg, dict):
                    err_msg = data.get("message") or str(err_msg)
                self._last_token_error = err_msg[:500] if err_msg else f"HTTP {resp.status_code}"
                return {
                    "success": False,
                    "error": self._last_token_error,
                    "status_code": resp.status_code,
                    "response": data,
                }
            # PDF: success response has data.token and data.expiryTime
            data_obj = data.get("data") or {}
            token = data_obj.get("token") or data.get("token") or data.get("accessToken") or data.get("access_token")
            if not token:
                self._last_token_error = "Token not found in response"
                return {
                    "success": False,
                    "error": self._last_token_error,
                    "response": data,
                }
            self._token = token
            self._last_token_error = None
            # PDF: token valid 24 hours; expiryTime "YYYY-MM-DD HH:mm:ss". Refresh 5 min before expiry.
            expiry_str = data_obj.get("expiryTime") or data.get("expiryTime")
            if expiry_str and isinstance(expiry_str, str):
                try:
                    from datetime import datetime as dt
                    et = dt.strptime(expiry_str.strip()[:19], "%Y-%m-%d %H:%M:%S")
                    self._token_expires_at = et.timestamp() - 300
                except Exception:
                    self._token_expires_at = time.time() + (86400 - 300)
            else:
                self._token_expires_at = time.time() + (86400 - 300)
            return {"success": True, "data": data, "token": token}
        except Exception as e:
            self._last_token_error = str(e)[:500]
            logger.error("Mobikwik BBPS token request failed", extra_data={"error": self._last_token_error})
            return {"success": False, "error": self._last_token_error, "error_code": "TOKEN_FAILED"}

    def _ensure_token(self) -> bool:
        """Ensure we have a valid token; refresh if expired. Returns True if token is available."""
        if self._token and time.time() < self._token_expires_at:
            return True
        result = self.get_token()
        return result.get("success") is True

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        base = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._token:
            # PDF: "Authorization: <token>" (token only, no Bearer prefix)
            base["Authorization"] = self._token
        if self.api_key:
            base["X-API-Key"] = self.api_key
        if self.merchant_id:
            base["X-Merchant-Id"] = self.merchant_id
        if extra:
            base.update(extra)
        return base

    # -------------------------------------------------------------------------
    # Request encryption (encryptedSessionKey, encryptedPayload, keyVersion, iv)
    # -------------------------------------------------------------------------

    def _encrypt_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build encrypted request body per Mobikwik PDF: encryptedSessionKey, encryptedPayload, keyVersion, iv.
        Uses AES-256-GCM with 12-byte nonce (NIST standard); session key encrypted with Mobikwik RSA public key.
        """
        if not self.use_encryption or not self.public_key_pem:
            return payload
        try:
            from Crypto.Cipher import AES
            from Crypto.Random import get_random_bytes

            session_key = get_random_bytes(32)
            nonce = get_random_bytes(12)  # AES-GCM standard: 12-byte (96-bit) nonce
            plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")
            cipher = AES.new(session_key, AES.MODE_GCM, nonce=nonce)
            ciphertext, tag = cipher.encrypt_and_digest(plaintext)
            # encryptedPayload = Base64( ciphertext + tag ); iv sent separately
            encrypted_payload_b64 = b64encode(ciphertext + tag).decode("ascii")
            iv_b64 = b64encode(nonce).decode("ascii")

            public_key = serialization.load_pem_public_key(self.public_key_pem.encode("utf-8"))
            encrypted_session_key = public_key.encrypt(
                session_key,
                padding.PKCS1v15(),
            )
            encrypted_session_key_b64 = b64encode(encrypted_session_key).decode("ascii")

            return {
                "encryptedSessionKey": encrypted_session_key_b64,
                "encryptedPayload": encrypted_payload_b64,
                "keyVersion": self.key_version,
                "iv": iv_b64,
            }
        except Exception as e:
            logger.warning("Mobikwik payload encryption failed, sending plain", extra={"error": str(e)})
            return payload

    def _checksum(self, params: Dict[str, Any]) -> str:
        """Generate checksum (SHA256) for requests that still require it (legacy or fallback)."""
        if not self.secret_key:
            return ""
        sorted_keys = sorted(k for k in params if params[k] not in (None, ""))
        param_str = "".join(f"{k}{params[k]}" for k in sorted_keys)
        raw = f"{param_str}{self.secret_key}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        require_token: bool = True,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Make HTTP request to Mobikwik BBPS API. Optionally encrypt body."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "MOBIKWIK_BBPS is not configured or enabled",
                "error_code": "CONFIG_MISSING",
            }
        if require_token and (self.client_id and self.client_secret) and not self._ensure_token():
            detail = f": {self._last_token_error}" if self._last_token_error else ""
            return {
                "success": False,
                "error": f"Failed to obtain Mobikwik BBPS token{detail}",
                "error_code": "TOKEN_FAILED",
                "response": {"detail": self._last_token_error} if self._last_token_error else None,
            }
        url = f"{self.base_url}{path}"
        if method.upper() == "POST" and json_data is not None:
            json_data = self._encrypt_payload(json_data)
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(
                    method,
                    url,
                    json=json_data,
                    params=params,
                    headers=self._headers(),
                )
            try:
                data = resp.json() if resp.content else {}
            except (ValueError, json.JSONDecodeError):
                data = {"_raw": (resp.text or resp.content.decode("utf-8", errors="replace") if resp.content else "")[:500]}
            if resp.status_code >= 400:
                return {
                    "success": False,
                    "error": data.get("message", data.get("error", resp.text)),
                    "status_code": resp.status_code,
                    "response": data,
                }
            return {"success": True, "data": data, "status_code": resp.status_code}
        except httpx.TimeoutException as e:
            logger.warning("Mobikwik BBPS request timeout", extra={"url": url, "error": str(e)})
            return {"success": False, "error": "Request timeout", "error_code": "TIMEOUT"}
        except Exception as e:
            logger.error("Mobikwik BBPS request failed", extra_data={"error": str(e)})
            return {"success": False, "error": str(e), "error_code": "REQUEST_FAILED"}

    # -------------------------------------------------------------------------
    # New APIs (per UAT: Balance Check, Validation, View Bill, Recharge, Transaction Status)
    # -------------------------------------------------------------------------

    def balance_check(self) -> Dict[str, Any]:
        """Balance Check API – get wallet/account balance."""
        path = self._get_path("balance")
        payload = {}
        if self.merchant_id:
            payload["merchantId"] = self.merchant_id
        return self._request("POST", path, json_data=payload if payload else None)

    def validation(
        self,
        operator_id: str,
        customer_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validation API – validate consumer (prepaid). Payload per PDF: amt, cn, op, cir, planCode?, adParams.
        For bill fetch use view_bill() instead.
        """
        path = self._get_path("validation")
        cir = (extra_params or {}).get("cir", "") if extra_params else ""
        ad_params = {k: v for k, v in (extra_params or {}).items() if k != "cir"}
        payload = {
            "amt": (extra_params or {}).get("amt", "1"),
            "cn": customer_id,
            "op": self._op_int(operator_id),
            "cir": cir or "",
            "adParams": ad_params,
        }
        if (extra_params or {}).get("planCode"):
            payload["planCode"] = extra_params["planCode"]
        return self._request("POST", path, json_data=payload)

    def view_bill(
        self,
        operator_id: str,
        customer_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        View Bill API – get bill details. Payload per PDF: cn, op, cir, adParams.
        """
        path = self._get_path("view_bill")
        # PDF: View Bill plain JSON before encryption: cn, op, cir, adParams
        extra = dict(extra_params) if extra_params else {}
        cir = extra.pop("cir", "")
        payload = {
            "cn": customer_id,
            "op": self._op_int(operator_id),
            "cir": cir or "",
            "adParams": extra,
        }
        return self._request("POST", path, json_data=payload)

    def recharge(
        self,
        operator_id: str,
        customer_id: str,
        amount: str,
        ref_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Recharge API – pay bill / recharge (maps to BBPS pay).
        """
        path = self._get_path("recharge")
        payload = {
            "merchantId": self.merchant_id or "",
            "operatorId": self._op_int(operator_id),
            "customerId": customer_id,
            "amount": amount,
            "refId": ref_id,
        }
        if subscriber_id:
            payload["subscriberId"] = subscriber_id
        if extra_params:
            payload.update(extra_params)
        payload["timestamp"] = int(time.time())
        if self.secret_key:
            payload["checksum"] = self._checksum(payload)
        return self._request("POST", path, json_data=payload)

    def transaction_status(self, ref_id: str) -> Dict[str, Any]:
        """Transaction Status Check API – get status by reference id. Uses POST with refId in body (Mobikwik UAT)."""
        path = self._get_path("transaction_status")
        return self._request("POST", path, json_data={"refId": ref_id})

    # -------------------------------------------------------------------------
    # Legacy / compatibility (operators, fetch_bill, pay_bill, pay_status)
    # -------------------------------------------------------------------------

    def get_operators(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get list of operators/billers (BBPS). Uses operators path or balance/validation params per API Kit."""
        path = self._get_path("operators")
        params = {}
        if category:
            params["category"] = category
        return self._request("GET", path, params=params, require_token=True)

    def fetch_bill(
        self,
        operator_id: str,
        customer_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch bill – uses View Bill API (bill details); Validation is for prepaid only."""
        return self.view_bill(
            operator_id=operator_id,
            customer_id=customer_id,
            subscriber_id=subscriber_id,
            extra_params=extra_params,
        )

    def pay_bill(
        self,
        operator_id: str,
        customer_id: str,
        amount: str,
        ref_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pay bill – uses Recharge API (new)."""
        return self.recharge(
            operator_id=operator_id,
            customer_id=customer_id,
            amount=amount,
            ref_id=ref_id,
            subscriber_id=subscriber_id,
            extra_params=extra_params,
        )

    def pay_status(self, ref_id: str) -> Dict[str, Any]:
        """Check payment status – uses Transaction Status Check API (new)."""
        return self.transaction_status(ref_id=ref_id)
