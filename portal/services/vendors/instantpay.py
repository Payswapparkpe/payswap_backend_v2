"""
Instantpay API client - all services per https://developers.instantpay.in/
Authentication: X-Ipay-Auth-Code: -1, X-Ipay-Client-Id, X-Ipay-Client-Secret, X-Ipay-Endpoint-Ip
Encryption: AES-256-CBC for sensitive fields (Aadhaar etc.) using INSTANTPAY_ENCRYPTION_KEY
"""
import base64
import logging
from typing import Any, Dict, Optional

import httpx
from core.config import payswap_config

logger = logging.getLogger(__name__)

# Auth code per Instantpay docs
IPAY_AUTH_CODE = "-1"


def _get_base_url() -> str:
    url = getattr(payswap_config, "INSTANTPAY_BASE_URL", None) or ""
    if url:
        return url.rstrip("/")
    env = getattr(payswap_config, "INSTANTPAY_ENVIRONMENT", "SANDBOX") or "SANDBOX"
    if env == "PRODUCTION":
        return "https://api.instantpay.in"
    return "https://api.instantpay.in"  # Sandbox may use same host with different credentials


def _aes_encrypt(plain_text: str, key_hex: str) -> Optional[str]:
    """AES-256-CBC encrypt and return base64(encrypted + iv) for Instantpay sensitive fields."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        import os
    except ImportError:
        logger.warning("cryptography not available for Instantpay AES encryption")
        return None
    try:
        key = bytes.fromhex(key_hex) if len(key_hex) == 64 else key_hex.encode("utf-8")[:32].ljust(32, b"\0")
        if len(key) < 32:
            key = (key_hex * 2).encode("utf-8")[:32]
        elif len(key) > 32:
            key = key[:32]
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        pad = 16 - (len(plain_text) % 16)
        padded = plain_text.encode("utf-8") + bytes([pad] * pad)
        ct = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(iv + ct).decode("utf-8")
    except Exception as e:
        logger.warning("Instantpay AES encrypt failed: %s", e)
        return None


class InstantpayClient:
    """Instantpay API client - Identity, Banking, Payouts, AePS, Collect, etc."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        encryption_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.client_id = client_id or payswap_config.get_instantpay_client_id()
        self.client_secret = client_secret or payswap_config.get_instantpay_client_secret()
        self.encryption_key = encryption_key or payswap_config.get_instantpay_encryption_key()
        self.base_url = base_url or _get_base_url()

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.encryption_key)

    def _headers(self, client_ip: Optional[str] = None) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Ipay-Auth-Code": IPAY_AUTH_CODE,
            "X-Ipay-Client-Id": self.client_id or "",
            "X-Ipay-Client-Secret": self.client_secret or "",
            "X-Ipay-Endpoint-Ip": client_ip or "127.0.0.1",
        }

    def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=timeout) as http_client:
                r = http_client.request(
                    method,
                    url,
                    json=json_body,
                    headers=self._headers(client_ip),
                )
                out = {"status_code": r.status_code, "body": r.text}
                try:
                    out["json"] = r.json()
                except Exception:
                    out["json"] = None
                r.raise_for_status()
                return out
        except httpx.HTTPStatusError as e:
            return {"status_code": e.response.status_code, "body": e.response.text, "json": None, "error": str(e)}
        except Exception as e:
            return {"status_code": 0, "body": "", "json": None, "error": str(e)}

    # ---------- Asset Verifications ----------
    def epfo_uan_verification(self, uan: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/verifyEpfoUan", {"uan": uan}, client_ip)

    def driving_license_verification(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/verifyDrivingLicense", payload, client_ip)

    def vehicle_challan_lookup(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/vehicleChallan", payload, client_ip)

    # ---------- Banking ----------
    def balance_check(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/banking/balanceCheck", payload, client_ip)

    def account_statement(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/reports/statement", payload, client_ip)

    # ---------- Business Verifications ----------
    def lei_verification(self, lei: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("GET", f"/identity/verifyLei?lei={lei}", None, client_ip)

    def fssai_verification(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/verifyFssai", payload, client_ip)

    def tan_verification_plus(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/verifyTan", payload, client_ip)

    # ---------- Tax / GSTIN ----------
    def gstin_verification(self, gstin: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/verifyGstin", {"gstin": gstin}, client_ip)

    def gstin_verification_plus(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/verifyGstinPlus", payload, client_ip)

    def aadhaar_pan_linking_status(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/aadhaarPanLinkingStatus", payload, client_ip)

    # ---------- Financial Verifications ----------
    def pep_sanctions_search(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/pepSanctionsSearch", payload, client_ip)

    def verify_upi_vpa(self, vpa: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/bankAccount/verifyUpiVpa", {"vpa": vpa}, client_ip)

    def bank_account_verification(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/bankAccount/verify", payload, client_ip)

    # ---------- Location / Geo ----------
    def ip_lookup(self, ip: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        body = {"ip": ip} if ip else {}
        return self._request("POST", "/geo/ipLookup", body or None, client_ip)

    def pin_code_lookup(self, pincode: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("GET", f"/geo/pinCodeLookup?pincode={pincode}", None, client_ip)

    # ---------- Mobile Based ----------
    def mobile_to_address_lookup(self, mobile: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/addressLookup", {"mobile": mobile}, client_ip)

    def mobile_to_upi_vpa_lookup(self, mobile: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/mobileToUpiVpa", {"mobile": mobile}, client_ip)

    def mobile_to_name_lookup(self, mobile: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/nameLookup", {"mobile": mobile}, client_ip)

    # ---------- Digital KYC / Identity ----------
    def profile_enrichment(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/profileEnrichment", payload, client_ip)

    def face_liveness(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/faceLiveness", payload, client_ip)

    def digilocker_create_url(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/digilocker/createUrl", payload, client_ip)

    # ---------- Payouts ----------
    def payouts_bank_list(self, client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("GET", "/payouts/bankList", None, client_ip)

    def payouts_bank_accounts(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/payouts/bankAccount", payload, client_ip)

    def payouts_create(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/payouts/create", payload, client_ip)

    # ---------- Other ----------
    def transaction_status(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/reporting/transactionStatus", payload, client_ip)

    def merchant_onboarding(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/customerOnboarding", payload, client_ip)

    # ---------- AI / Utility ----------
    def image_moderation(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/imageModeration", payload, client_ip)

    def face_detection_analysis(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/faceDetection", payload, client_ip)

    def face_comparison(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/identity/faceComparison", payload, client_ip)

    # ---------- Cards / Gift Cards ----------
    def corporate_gift_cards(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/giftCards/create", payload, client_ip)

    def brand_voucher(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/brandVoucher/create", payload, client_ip)

    # ---------- AePS / Financial Inclusion ----------
    def aeps_transaction(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/aeps/transaction", payload, client_ip)

    def remittance_domestic(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/remittance/domestic", payload, client_ip)

    def remittance_nepal(self, payload: Dict[str, Any], client_ip: Optional[str] = None) -> Dict[str, Any]:
        return self._request("POST", "/remittance/nepal", payload, client_ip)


# API categories and methods for UI - service-wise grouping
INSTANTPAY_API_CATEGORIES = [
    {
        "name": "Asset Verifications",
        "code": "asset",
        "apis": [
            {"code": "epfo_uan", "name": "EPFO UAN Verification", "method": "POST", "icon": "ti-id"},
            {"code": "driving_license", "name": "Driving License Verification", "method": "POST", "icon": "ti-license"},
            {"code": "vehicle_challan", "name": "Vehicle Challan Lookup", "method": "POST", "icon": "ti-car"},
        ],
    },
    {
        "name": "Banking",
        "code": "banking",
        "apis": [
            {"code": "balance_check", "name": "Balance Check", "method": "POST", "icon": "ti-wallet"},
            {"code": "account_statement", "name": "Account Statement", "method": "POST", "icon": "ti-file-invoice"},
        ],
    },
    {
        "name": "Business Verifications",
        "code": "business",
        "apis": [
            {"code": "lei", "name": "LEI Verification", "method": "GET", "icon": "ti-building"},
            {"code": "fssai", "name": "FSSAI Verification", "method": "POST", "icon": "ti-certificate"},
            {"code": "tan_plus", "name": "TAN Verification Plus", "method": "POST", "icon": "ti-receipt"},
        ],
    },
    {
        "name": "Tax Data",
        "code": "tax",
        "apis": [
            {"code": "gstin", "name": "GSTIN Verification", "method": "POST", "icon": "ti-receipt"},
            {"code": "gstin_plus", "name": "GSTIN Verification Plus", "method": "POST", "icon": "ti-receipt-2"},
            {"code": "aadhaar_pan_linking", "name": "Aadhaar-PAN Linking Status", "method": "POST", "icon": "ti-link"},
        ],
    },
    {
        "name": "Financial Verifications",
        "code": "financial",
        "apis": [
            {"code": "pep_sanctions", "name": "PEP & Sanctions Search", "method": "POST", "icon": "ti-shield-search"},
            {"code": "verify_upi_vpa", "name": "Verify UPI Handle (VPA)", "method": "POST", "icon": "ti-brand-upwork"},
            {"code": "bank_account", "name": "Bank Account Verification", "method": "POST", "icon": "ti-building-bank"},
        ],
    },
    {
        "name": "Location Services",
        "code": "location",
        "apis": [
            {"code": "ip_lookup", "name": "IP Lookup", "method": "POST", "icon": "ti-network"},
            {"code": "pin_code_lookup", "name": "PIN Code Lookup", "method": "GET", "icon": "ti-map-pin"},
        ],
    },
    {
        "name": "Mobile Based",
        "code": "mobile",
        "apis": [
            {"code": "mobile_to_address", "name": "Mobile to Address Lookup", "method": "POST", "icon": "ti-phone"},
            {"code": "mobile_to_upi_vpa", "name": "Mobile to UPI VPA Lookup", "method": "POST", "icon": "ti-brand-upwork"},
            {"code": "mobile_to_name", "name": "Mobile to Name Lookup", "method": "POST", "icon": "ti-user"},
        ],
    },
    {
        "name": "Digital KYC",
        "code": "digital_kyc",
        "apis": [
            {"code": "profile_enrichment", "name": "Profile Enrichment", "method": "POST", "icon": "ti-user-edit"},
            {"code": "face_liveness", "name": "Face Liveness", "method": "POST", "icon": "ti-face-id"},
            {"code": "digilocker", "name": "Digilocker", "method": "POST", "icon": "ti-lock"},
        ],
    },
    {
        "name": "Payouts",
        "code": "payouts",
        "apis": [
            {"code": "bank_list", "name": "Bank List", "method": "GET", "icon": "ti-list"},
            {"code": "bank_accounts", "name": "Bank Accounts", "method": "POST", "icon": "ti-building-bank"},
            {"code": "payout_create", "name": "Create Payout", "method": "POST", "icon": "ti-send"},
        ],
    },
    {
        "name": "Other",
        "code": "other",
        "apis": [
            {"code": "transaction_status", "name": "Transaction Status", "method": "POST", "icon": "ti-info-circle"},
            {"code": "merchant_onboarding", "name": "Merchant Onboarding", "method": "POST", "icon": "ti-user-plus"},
        ],
    },
    {
        "name": "AI / Utility",
        "code": "ai_utility",
        "apis": [
            {"code": "image_moderation", "name": "Image Moderation", "method": "POST", "icon": "ti-photo"},
            {"code": "face_detection", "name": "Facial Detection & Analysis", "method": "POST", "icon": "ti-face-id"},
            {"code": "face_comparison", "name": "Face Comparison", "method": "POST", "icon": "ti-users"},
        ],
    },
    {
        "name": "Cards & Vouchers",
        "code": "cards",
        "apis": [
            {"code": "corporate_gift_cards", "name": "Corporate Gift Cards", "method": "POST", "icon": "ti-gift"},
            {"code": "brand_voucher", "name": "Brand Voucher", "method": "POST", "icon": "ti-voucher"},
        ],
    },
    {
        "name": "Financial Inclusion",
        "code": "financial_inclusion",
        "apis": [
            {"code": "aeps", "name": "AePS", "method": "POST", "icon": "ti-fingerprint"},
            {"code": "remittance_domestic", "name": "Remittance (Domestic)", "method": "POST", "icon": "ti-transfer"},
            {"code": "remittance_nepal", "name": "Remittance (Nepal)", "method": "POST", "icon": "ti-world"},
        ],
    },
]
