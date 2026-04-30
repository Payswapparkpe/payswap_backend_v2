"""
Instantpay client and metadata for Hub integrations.

This module provides:
- API catalog used by portal vendor detail view (`INSTANTPAY_API_CATEGORIES`)
- A reusable HTTP client (`InstantpayClient`) for v2 service wrappers
- Lightweight normalization for variable Instantpay responses
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from typing import Any, Dict, Optional

import httpx

from core.config import payswap_config
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.vendors.instantpay")


INSTANTPAY_API_CATEGORIES = [
    {
        "name": "AEPS and Banking",
        "apis": [
            {"code": "aeps_withdraw", "name": "AEPS Withdraw", "method": "POST", "icon": "ti-cash"},
            {"code": "balance_check", "name": "Balance Check", "method": "POST", "icon": "ti-wallet"},
            {"code": "account_statement", "name": "Account Statement", "method": "POST", "icon": "ti-file-text"},
        ],
    },
    {
        "name": "DMT and Remittance",
        "apis": [
            {"code": "dmt_transfer", "name": "DMT Transfer", "method": "POST", "icon": "ti-transfer"},
            {"code": "remittance_domestic", "name": "Remittance Domestic", "method": "POST", "icon": "ti-home"},
            {"code": "remittance_nepal", "name": "Remittance Nepal", "method": "POST", "icon": "ti-world"},
        ],
    },
    {
        "name": "Bill Payments and Vehicle",
        "apis": [
            {"code": "credit_card_bill_pay", "name": "Credit Card Bill Payment", "method": "POST", "icon": "ti-credit-card-pay"},
            {"code": "rc_verification", "name": "RC Verification", "method": "POST", "icon": "ti-car"},
            {"code": "vehicle_challan_lookup", "name": "Vehicle Challan Lookup", "method": "POST", "icon": "ti-alert-circle"},
            {"code": "vehicle_challan_pay", "name": "Vehicle Challan Pay", "method": "POST", "icon": "ti-receipt-2"},
        ],
    },
    {
        "name": "Identity, Cards, Credit, Merchant",
        "apis": [
            {"code": "digilocker_init", "name": "DigiLocker Init", "method": "POST", "icon": "ti-lock"},
            {"code": "digilocker_status", "name": "DigiLocker Status", "method": "GET", "icon": "ti-shield-check"},
            {"code": "card_bin_lookup", "name": "Card BIN Lookup", "method": "POST", "icon": "ti-credit-card"},
            {"code": "credit_report", "name": "Credit Report", "method": "POST", "icon": "ti-report-analytics"},
            {"code": "credit_score_simulator", "name": "Credit Score Simulator", "method": "POST", "icon": "ti-chart-line"},
            {"code": "merchant_onboarding", "name": "Merchant Onboarding", "method": "POST", "icon": "ti-user-plus"},
            {"code": "transaction_status", "name": "Transaction Status", "method": "GET", "icon": "ti-loader"},
            {"code": "gstin_lookup", "name": "GSTIN Lookup", "method": "POST", "icon": "ti-building-store"},
            {"code": "pincode_lookup", "name": "Pincode Lookup", "method": "POST", "icon": "ti-map-pin"},
        ],
    },
]


class InstantpayClient:
    """HTTP client for Instantpay APIs with normalized responses."""

    ENDPOINTS = {
        "aeps_withdraw": ("POST", "/aeps/withdraw"),
        "balance_check": ("POST", "/aeps/balance-check"),
        "account_statement": ("POST", "/reports/statement"),
        "business_wallet_balance": ("POST", "/accounts/balance"),
        "dmt_transfer": ("POST", "/dmt/transfer"),
        "remittance_domestic": ("POST", "/remittance/domestic"),
        "remittance_nepal": ("POST", "/remittance/nepal"),
        "credit_card_bill_pay": ("POST", "/billpay/credit-card"),
        "rc_verification": ("POST", "/vehicle/rc-verification"),
        # Instantpay identity verification suite (documented endpoint).
        "vehicle_challan_lookup": ("POST", "/identity/vehicleChallan"),
        "vehicle_challan_pay": ("POST", "/identity/vehicleChallanPay"),
        "digilocker_init": ("POST", "/digilocker/init"),
        "digilocker_status": ("GET", "/digilocker/status"),
        "card_bin_lookup": ("POST", "/cards/bin-lookup"),
        "credit_report": ("POST", "/credit/report"),
        "credit_score_simulator": ("POST", "/credit/score-simulator"),
        "merchant_onboarding": ("POST", "/merchant/onboarding"),
        "transaction_status": ("GET", "/transaction/status"),
        "gstin_lookup": ("POST", "/gstin/lookup"),
        "pincode_lookup": ("POST", "/pincode/lookup"),
        "bank_verification": ("POST", "/bank/verification"),
    }

    def __init__(self):
        self.client_id = payswap_config.get_instantpay_client_id()
        self.client_secret = payswap_config.get_instantpay_client_secret()
        self.encryption_key = payswap_config.get_instantpay_encryption_key()
        self.auth_code = payswap_config.get_instantpay_auth_code()
        self.identity_auth_mode = payswap_config.get_instantpay_identity_auth_mode()
        self.endpoint_ip = payswap_config.get_instantpay_endpoint_ip() or ""
        self.environment = (payswap_config.INSTANTPAY_ENVIRONMENT or "SANDBOX").upper()
        self.base_url = self._resolve_base_url()
        self.timeout_seconds = 45.0
        self._log_config_sanity()

    def _resolve_base_url(self) -> str:
        if payswap_config.INSTANTPAY_BASE_URL:
            return str(payswap_config.INSTANTPAY_BASE_URL).rstrip("/")
        # Keep default host resolvable unless explicit sandbox URL is provided in env.
        if self.environment == "SANDBOX":
            logger.warning("INSTANTPAY_BASE_URL not set; using default api host for sandbox.")
        return "https://api.instantpay.in"

    def _log_config_sanity(self) -> None:
        """
        Emit high-signal config warnings to catch environment/auth mismatches early.
        This is intentionally non-blocking and never logs raw secrets.
        """
        url = (self.base_url or "").lower()
        mode = (self.identity_auth_mode or "").strip().lower()
        if self.environment == "PRODUCTION" and any(tok in url for tok in ("sandbox", "staging", "uat", "test")):
            logger.warning(
                f"Instantpay config mismatch: INSTANTPAY_ENVIRONMENT=PRODUCTION but base URL looks non-prod "
                f"(base_url={self.base_url}, identity_auth_mode={mode})."
            )
        if self.environment == "SANDBOX" and not any(tok in url for tok in ("sandbox", "staging", "uat", "test")):
            logger.warning(
                f"Instantpay config mismatch: INSTANTPAY_ENVIRONMENT=SANDBOX but base URL looks prod/default "
                f"(base_url={self.base_url}, identity_auth_mode={mode})."
            )
        if mode == "static" and not self.auth_code:
            logger.warning(
                "Instantpay identity auth mode is static but INSTANTPAY_AUTH_CODE is empty; fallback hash mode will be used."
            )
        if mode in {"sha256_pipe", "sha256_concat", "base64_basic", "fixed_1"} and self.auth_code:
            logger.info(
                "Instantpay identity auth runs in dynamic mode; INSTANTPAY_AUTH_CODE remains configured but "
                f"unused for identity auth (identity_auth_mode={mode})."
            )

    def is_configured(self) -> bool:
        return payswap_config.is_instantpay_configured()

    def _request_id(self) -> str:
        return str(uuid.uuid4())

    def _identity_auth_code_pipe(self, timestamp: str) -> str:
        raw = f"{self.client_id}|{self.client_secret}|{timestamp}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _identity_auth_code_concat(self, timestamp: str) -> str:
        raw = f"{self.client_id}{self.client_secret}{timestamp}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _identity_auth_code_base64(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    def _resolve_identity_auth(
        self, timestamp: str, explicit_auth_code: Optional[str] = None
    ) -> tuple[str, str]:
        if explicit_auth_code:
            return explicit_auth_code, "explicit_override"
        mode = (self.identity_auth_mode or "sha256_pipe").strip().lower()
        if mode == "fixed_1":
            return "1", "fixed_1"
        if mode == "static":
            if self.auth_code:
                return self.auth_code, "static"
            return self._identity_auth_code_pipe(timestamp), "sha256_pipe_fallback"
        if mode == "sha256_concat":
            return self._identity_auth_code_concat(timestamp), "sha256_concat"
        if mode == "base64_basic":
            return self._identity_auth_code_base64(), "base64_basic"
        return self._identity_auth_code_pipe(timestamp), "sha256_pipe"

    def _build_headers(
        self,
        request_id: str,
        body: Optional[Dict[str, Any]],
        auth_code: Optional[str] = None,
        *,
        auth_code_only: bool = False,
    ) -> tuple[Dict[str, str], Dict[str, Any]]:
        if auth_code_only:
            ts = str(int(time.time()))
            selected_auth_code, resolved_mode = self._resolve_identity_auth(
                ts, explicit_auth_code=auth_code
            )
            headers = {
                "Content-Type": "application/json",
                "X-Ipay-Auth-Code": selected_auth_code,
                "X-Ipay-Client-Id": self.client_id,
                "X-Ipay-Client-Secret": self.client_secret,
            }
            if self.endpoint_ip:
                headers["X-Ipay-Endpoint-Ip"] = self.endpoint_ip
            if resolved_mode in {"sha256_pipe", "sha256_pipe_fallback", "sha256_concat"}:
                headers["X-Ipay-Timestamp"] = ts
            auth_hash = hashlib.sha256(selected_auth_code.encode("utf-8")).hexdigest()
            meta = {
                "auth_mode": resolved_mode,
                "timestamp_sent": ts,
                "auth_code_sha256": auth_hash,
                "auth_code_prefix": selected_auth_code[:4],
                "auth_code_suffix": selected_auth_code[-4:] if len(selected_auth_code) >= 4 else selected_auth_code,
                "header_names": sorted(list(headers.keys())),
            }
            return headers, meta

        selected_auth_code = auth_code if auth_code is not None else self.auth_code
        ts = str(int(time.time()))
        payload = json.dumps(body or {}, separators=(",", ":"), sort_keys=True)
        body_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        sign_input = f"{self.client_id}.{ts}.{request_id}.{body_digest}"
        signature = hashlib.sha256(f"{sign_input}.{self.client_secret}".encode("utf-8")).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Ipay-Client-Id": self.client_id,
            "X-Ipay-Client-Secret": self.client_secret,
            "x-timestamp": ts,  # keep for compatibility if accepted server-side
            "x-request-id": request_id,  # keep for tracing
            "x-signature": signature,
        }
        if self.endpoint_ip:
            headers["X-Ipay-Endpoint-Ip"] = self.endpoint_ip
        if selected_auth_code:
            headers["X-Ipay-Auth-Code"] = selected_auth_code
        return headers, {"header_names": sorted(list(headers.keys()))}

    def _encrypt_optional(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lightweight envelope encryption helper.
        If required later by exact Instantpay contracts, this can be upgraded
        without changing service/view callers.
        """
        if not self.encryption_key:
            return payload
        raw = json.dumps(payload).encode("utf-8")
        cipher = base64.b64encode(raw).decode("utf-8")
        return {"payload": cipher, "mode": "base64-envelope"}

    def _normalize(self, api_code: str, status_code: int, body: Any, error: Optional[str] = None) -> Dict[str, Any]:
        success = status_code in (200, 201)
        if isinstance(body, dict):
            vendor_status = body.get("status") or body.get("code") or "unknown"
            message = body.get("message") or body.get("msg") or body.get("internalCode") or body.get("status") or ""
            vendor_code = str(body.get("statuscode") or "").upper()
            if vendor_code in {"ERR", "RPI", "FAIL", "FAILED"}:
                success = False
        else:
            vendor_status = "unknown"
            message = ""
        return {
            "api_code": api_code,
            "status_code": status_code,
            "success": success,
            "vendor_status": vendor_status,
            "json": body if isinstance(body, dict) else None,
            "body": body if not isinstance(body, dict) else None,
            "error": error,
            "message": message or error or "",
            "retryable": status_code in (408, 429, 500, 502, 503, 504),
        }

    def _path_candidates(self, path: str) -> list[str]:
        """Try common route prefixes because Instantpay account routes vary by tenant setup."""
        normalized = path if path.startswith("/") else f"/{path}"
        # Identity verification APIs use fixed routes; probing /api/v1 variants yields noisy 404s.
        if normalized.startswith("/identity/"):
            return [normalized]
        candidates = [
            normalized,
            f"/api{normalized}",
            f"/api/v1{normalized}",
            f"/api/v2{normalized}",
        ]
        seen = set()
        deduped = []
        for p in candidates:
            if p not in seen:
                deduped.append(p)
                seen.add(p)
        return deduped

    def request(
        self,
        api_code: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        query: Optional[Dict[str, Any]] = None,
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from api.parkpe_logging import log_instantpay_api_call

        _lc = dict(log_context or {})

        def _emit(res: Dict[str, Any], x_request_id: str) -> Dict[str, Any]:
            log_instantpay_api_call(api_code, res, x_request_id, log_context=_lc)
            return res

        if api_code not in self.ENDPOINTS:
            rid = self._request_id()
            return _emit(self._normalize(api_code, 400, {}, error=f"Unsupported api_code: {api_code}"), rid)
        if not self.is_configured():
            rid = self._request_id()
            return _emit(self._normalize(api_code, 400, {}, error="Instantpay not configured"), rid)

        method, path = self.ENDPOINTS[api_code]
        request_id = self._request_id()
        body = payload or {}
        if api_code == "vehicle_challan_lookup":
            vehicle_number = (
                body.get("vehicleRegistrationNumber")
                or body.get("vehicleNumber")
                or body.get("vehicle_number")
                or ""
            )
            prepared_body = {
                "vehicleRegistrationNumber": str(vehicle_number).strip().upper(),
                "consent": str(body.get("consent") or "Y"),
                "latitude": str(body.get("latitude") or "0.0"),
                "longitude": str(body.get("longitude") or "0.0"),
                "externalRef": str(body.get("externalRef") or body.get("partner_txn_id") or request_id),
            }
        elif api_code == "vehicle_challan_pay":
            vehicle_number = (
                body.get("vehicleRegistrationNumber")
                or body.get("vehicleNumber")
                or body.get("vehicle_number")
                or ""
            )
            prepared_body = {
                "vehicleRegistrationNumber": str(vehicle_number).strip().upper(),
                "challanNumber": str(body.get("challanNumber") or body.get("challan_number") or ""),
                "amount": str(body.get("amount") or "0"),
                "paymentMode": str(body.get("paymentMode") or body.get("payment_method") or "upi"),
                "externalRef": str(body.get("externalRef") or body.get("partner_txn_id") or request_id),
                "consent": str(body.get("consent") or "Y"),
                "latitude": str(body.get("latitude") or "0.0"),
                "longitude": str(body.get("longitude") or "0.0"),
            }
        elif api_code == "business_wallet_balance":
            # Business wallet endpoint expects plain JSON keys (not encrypted envelope).
            prepared_body = {
                "bankProfileId": str(body.get("bankProfileId") or "0"),
                "accountNumber": str(body.get("accountNumber") or ""),
                "accountType": str(body.get("accountType") or "CURRENT"),
                "externalRef": str(body.get("externalRef") or request_id),
                "latitude": str(body.get("latitude") or "20.1236"),
                "longitude": str(body.get("longitude") or "78.3228"),
            }
        else:
            prepared_body = self._encrypt_optional(body)
        auth_candidates = [None]
        if api_code in {"vehicle_challan_lookup", "vehicle_challan_pay", "account_statement", "business_wallet_balance"}:
            # Identity challan + business wallet statement follow fixed header contracts.
            # Do not probe alternate auth code values for these endpoints.
            auth_candidates = [None]

        try:
            # trust_env=False avoids unintended proxy/DNS overrides from host env vars.
            with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
                last_normalized: Optional[Dict[str, Any]] = None
                last_non_404: Optional[Dict[str, Any]] = None
                for candidate_path in self._path_candidates(path):
                    for auth_candidate in auth_candidates:
                        headers, request_meta = self._build_headers(
                            request_id=request_id,
                            body=body,
                            auth_code=auth_candidate,
                            auth_code_only=(api_code in {"vehicle_challan_lookup", "vehicle_challan_pay", "account_statement", "business_wallet_balance"}),
                        )
                        if api_code in {"vehicle_challan_lookup", "vehicle_challan_pay", "business_wallet_balance"}:
                            request_meta["normalized_payload"] = dict(prepared_body)
                        if method == "GET":
                            response = client.get(
                                f"{self.base_url}{candidate_path}",
                                headers=headers,
                                params=query or payload or {},
                            )
                        else:
                            response = client.post(
                                f"{self.base_url}{candidate_path}",
                                headers=headers,
                                json=prepared_body,
                            )
                        try:
                            response_body: Any = response.json()
                        except Exception:
                            response_body = response.text
                        normalized = self._normalize(api_code, response.status_code, response_body)
                        normalized["attempted_path"] = candidate_path
                        normalized["request_meta"] = request_meta
                        if auth_candidate is not None:
                            normalized["attempted_auth_code"] = auth_candidate
                        last_normalized = normalized
                        if response.status_code != 404:
                            last_non_404 = normalized
                        # stop on first successful business response
                        if normalized.get("success"):
                            return _emit(normalized, request_id)
                        # no alternate probing configured for current endpoint contracts
                        break
                final = last_non_404 or last_normalized or self._normalize(api_code, 500, {}, error="No response from Instantpay")
                return _emit(final, request_id)
        except Exception as exc:
            logger.error(f"Instantpay request failed for {self.base_url}{path}: {exc}")
            return _emit(self._normalize(api_code, 500, {}, error=f"{exc}"), request_id)

    # Quick-test helpers used by portal legacy view
    def gstin_verification(self, gstin: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self.request("gstin_lookup", {"gstin": gstin, "client_ip": client_ip})

    def pin_code_lookup(self, pincode: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self.request("pincode_lookup", {"pincode": pincode, "client_ip": client_ip})
