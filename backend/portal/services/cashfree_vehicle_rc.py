"""
Cashfree Vehicle RC (Registration Certificate) Verification API.
POST /verification/vehicle-rc with vehicle_number; store response in VehicleRCData.
Uses CASHFREE_VERIFICATION_API_KEY/SECRET if set, else CASHFREE_API_KEY/SECRET (from Cashfree Verification Suite).
When Cashfree requires 2FA, x-cf-signature is added using CASHFREE_PUBLIC_KEY or CASHFREE_PUBLIC_KEY_PATH.
"""
import base64
import logging
import time
from typing import Any, Dict, Optional

import requests

from core.config import payswap_config

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)

VRS_SANDBOX = "https://sandbox.cashfree.com/verification"
VRS_PRODUCTION = "https://api.cashfree.com/verification"


def _vrs_base_url() -> str:
    env = getattr(payswap_config, "CASHFREE_VERIFICATION_ENVIRONMENT", "PRODUCTION") or "PRODUCTION"
    return VRS_SANDBOX if env.upper() == "SANDBOX" else VRS_PRODUCTION


def _get_verification_credentials() -> tuple[str, str]:
    """Return (client_id, client_secret) for Verification API. Prefer CASHFREE_VERIFICATION_* if set."""
    key_val = ""
    secret_val = ""
    vkey = getattr(payswap_config, "CASHFREE_VERIFICATION_API_KEY", None)
    vsecret = getattr(payswap_config, "CASHFREE_VERIFICATION_API_SECRET", None)
    if vkey and hasattr(vkey, "get_secret_value"):
        key_val = vkey.get_secret_value() or ""
    if vsecret and hasattr(vsecret, "get_secret_value"):
        secret_val = vsecret.get_secret_value() or ""
    if not key_val or not secret_val:
        key_val = payswap_config.get_cashfree_api_key() if hasattr(payswap_config, "get_cashfree_api_key") else ""
        secret_val = payswap_config.get_cashfree_api_secret() if hasattr(payswap_config, "get_cashfree_api_secret") else ""
    return key_val, secret_val


def _get_cf_signature(client_id: str) -> Optional[str]:
    """Generate x-cf-signature for Cashfree (clientId.timestamp encrypted with public key, base64). Required when IP is not whitelisted."""
    if not _CRYPTO_AVAILABLE or not client_id:
        return None
    public_key = None
    try:
        pem = getattr(payswap_config, "CASHFREE_PUBLIC_KEY", None)
        if pem:
            public_key = load_pem_public_key(pem.encode("utf-8"), backend=default_backend())
        if not public_key:
            path = getattr(payswap_config, "CASHFREE_PUBLIC_KEY_PATH", None)
            if path:
                with open(path, "rb") as f:
                    public_key = load_pem_public_key(f.read(), backend=default_backend())
        if not public_key:
            return None
        data_to_sign = f"{client_id}.{int(time.time())}"
        encrypted = public_key.encrypt(
            data_to_sign.encode("utf-8"),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
        )
        return base64.b64encode(encrypted).decode("utf-8")
    except Exception as e:
        logger.debug("Cashfree Vehicle RC: could not generate x-cf-signature: %s", e)
        return None


def fetch_vehicle_rc(registration_number: str) -> tuple[Optional[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]]]:
    """
    Call Cashfree Verify Vehicle RC Details API.
    Returns (response_dict, None, None) on success.
    On failure: (None, reason_string, details). details has cf_status/cf_message for http_error.
    reason_string: "no_credentials", "invalid_reg", "http_error", "invalid_status", "exception".
    """
    client_id, client_secret = _get_verification_credentials()
    if not client_id or not client_secret:
        logger.warning(
            "Cashfree Vehicle RC: no credentials. Set CASHFREE_API_KEY and CASHFREE_API_SECRET "
            "(or CASHFREE_VERIFICATION_API_KEY/SECRET) from Cashfree Verification Suite: "
            "https://merchant.cashfree.com/verificationsuite/developers/api-keys",
            extra={"rc_reason": "no_credentials"},
        )
        return None, "no_credentials", None
    reg = (registration_number or "").strip().upper().replace(" ", "")
    if not reg or len(reg) < 2:
        logger.info("Cashfree Vehicle RC: invalid registration number", extra={"reg_no": reg, "rc_reason": "invalid_reg"})
        return None, "invalid_reg", None
    url = f"{_vrs_base_url()}/vehicle-rc"
    from portal.utils.transaction_id import generate_transaction_id

    verification_id = generate_transaction_id()
    payload = {"verification_id": verification_id, "vehicle_number": reg}
    headers = {
        "Content-Type": "application/json",
        "x-client-id": client_id,
        "x-client-secret": client_secret,
    }
    sig = _get_cf_signature(client_id)
    if sig:
        headers["x-cf-signature"] = sig
    try:
        logger.info(
            "Cashfree Vehicle RC API call starting",
            extra={"reg_no": reg, "url": url},
        )
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        try:
            data = resp.json() if resp.text else {}
        except Exception:
            data = {"_raw": (resp.text[:500] if resp.text else "")}
        logger.info(
            "Cashfree Vehicle RC API response received",
            extra={"reg_no": reg, "http_status": resp.status_code, "cf_status": data.get("status")},
        )
        if resp.status_code != 200:
            cf_msg = data.get("message") or data.get("error") or data.get("_raw") or str(data)[:200]
            logger.warning(
                "Cashfree Vehicle RC HTTP error: status=%s message=%s",
                resp.status_code,
                cf_msg,
                extra={"reg_no": reg, "status": resp.status_code, "body": data, "rc_reason": "http_error"},
            )
            return None, "http_error", {"cf_status": resp.status_code, "cf_message": cf_msg}
        if data.get("status") == "INVALID":
            logger.info(
                "Cashfree Vehicle RC INVALID (number not found or invalid)",
                extra={"reg_no": reg, "rc_reason": "invalid_status"},
            )
            return None, "invalid_status", None
        logger.info("Cashfree Vehicle RC success", extra={"reg_no": reg})
        return data, None, None
    except Exception as e:
        err_msg = str(e)
        logger.exception(
            "Cashfree Vehicle RC request failed: %s",
            err_msg,
            extra={"reg_no": reg, "rc_reason": "exception", "error": err_msg},
        )
        return None, "exception", {"error": err_msg}
