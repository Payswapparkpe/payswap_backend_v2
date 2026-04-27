"""
Mobikwik BBPS (Bharat Bill Payment System) API client – New API (UAT/Onboarding docs).

New integration uses:
- Token Generation API (Client ID + Client Secret) for auth.
- Encrypted request body: encryptedSessionKey, encryptedPayload, keyVersion, iv.
- APIs: Token, Balance Check, Validation, View Bill, Recharge, Transaction Status Check.

Credentials and base URL from .env (MOBIKWIK_BBPS_*).
Aligned with Mobikwik UAT Postman: Token = plain JSON; Balance/Bill/Pay = AES-GCM + RSA encrypted body;
Client ID flow requests omit X-Merchant-Id / X-API-Key (same headers as collection).

Token policy (backend-only; never exposed to frontend):
- Doc: token valid ~24 hours; Mobikwik caps new tokens (~100/calendar day). We count successful Token API mints
  (see MOBIKWIK_BBPS_TOKEN_MAX_MINTS_PER_DAY) and stop calling Token API once the budget is hit for that IST day.
- We parse expiryTime from the token API and set refresh_before = mobikwik_expiry minus
  MOBIKWIK_BBPS_TOKEN_REFRESH_BUFFER_SECONDS (default 1800s = 30 min proactive renew).
- _ensure_token prefers shared Django cache over process memory so all workers share the same token.
- On API "Token is expired" (HTTP 200, message.code 401) we invalidate cache, get_token(force_refresh=True), retry once.
- Token is stored only on backend (Django cache / Redis). All workers share the same token.
- Frontend never receives or manages Mobikwik token; it only calls our backend APIs
  (categories, operators, fetch-bill, pay-bill). Backend handles token internally.
"""
import copy
import hashlib
import json
import time
from base64 import b64encode
from typing import Any, Dict, List, Optional

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.vendors.mobikwik")

# Keys whose values are redacted in UAT logs (request/response)
_SENSITIVE_KEYS = frozenset(
    {"clientSecret", "token", "accessToken", "access_token", "Authorization", "secret", "password"}
)


def _mask_value(val: str, show_last: int = 0) -> str:
    """Return '***' or last N chars masked (e.g. ****1234)."""
    if not val or not isinstance(val, str):
        return "***"
    if show_last <= 0:
        return "***"
    if len(val) <= show_last:
        return "***"
    return "*" * (len(val) - show_last) + val[-show_last:]

# Cache key for Mobikwik BBPS token (shared across workers; 100 tokens/day limit)
MOBIKWIK_BBPS_TOKEN_CACHE_KEY = "mobikwik_bbps_token"
# Default refresh buffer if config not loaded on class (instance uses payswap_config).
MOBIKWIK_BBPS_TOKEN_REFRESH_BUFFER_DEFAULT = 600

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

# __init__ default for member_id: re-read MOBIKWIK_BBPS_MEMBER_ID from .env on each balance_check (get_settings() is lru_cached).
_MISSING_BALANCE_MEMBER_ID = object()


def _secret_value(val) -> Optional[str]:
    """Get secret string value (SecretStr or plain str)."""
    if val is None:
        return None
    if hasattr(val, "get_secret_value"):
        return val.get_secret_value()
    return str(val)


def _optional_env_string(val) -> Optional[str]:
    """Normalize env/config optional strings: strip whitespace; empty → None (never send accidental blanks)."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


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
        member_id: Any = _MISSING_BALANCE_MEMBER_ID,
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
        self.merchant_id = _optional_env_string(merchant_id) or _optional_env_string(
            getattr(cfg, "MOBIKWIK_BBPS_MERCHANT_ID", None)
        )
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
        # UAT: optional override to force plain JSON (set PLAIN_JSON_UAT=True only if Mobikwik allows). Default False = use encryption when USE_ENCRYPTION=True per doc.
        env_name = getattr(cfg, "MOBIKWIK_BBPS_ENVIRONMENT", "UAT") or "UAT"
        if (str(env_name).upper() == "UAT" and getattr(cfg, "MOBIKWIK_BBPS_PLAIN_JSON_UAT", False)):
            self.use_encryption = False
        # Balance memberId: from MOBIKWIK_BBPS_MEMBER_ID in .env. If member_id kwarg omitted, balance_check re-reads .env each time
        # (payswap_config / get_settings is lru_cached — editing .env alone would otherwise keep a stale email until process restart).
        if member_id is _MISSING_BALANCE_MEMBER_ID:
            self._balance_member_id_re_read_env = True
            self.member_id = _optional_env_string(getattr(cfg, "MOBIKWIK_BBPS_MEMBER_ID", None))
        else:
            self._balance_member_id_re_read_env = False
            self.member_id = _optional_env_string(member_id) or _optional_env_string(
                getattr(cfg, "MOBIKWIK_BBPS_MEMBER_ID", None)
            )
        self.agent_id = _optional_env_string(getattr(cfg, "MOBIKWIK_BBPS_AGENT_ID", None))
        pk = public_key_pem or _secret_value(getattr(cfg, "MOBIKWIK_BBPS_PUBLIC_KEY", None))
        if pk is not None and not str(pk).strip():
            pk = None
        self.public_key_pem = pk
        if not self.public_key_pem:
            # .env may set PATH= (empty), wrong folder (e.g. zip name only), or a valid path — try explicit then default.
            raw_path = getattr(cfg, "MOBIKWIK_BBPS_PUBLIC_KEY_PATH", None)
            if isinstance(raw_path, str):
                raw_path = raw_path.strip() or None
            paths_to_try = []
            if raw_path:
                paths_to_try.append(raw_path)
            if "Mobikwik/public_key.pem" not in paths_to_try:
                paths_to_try.append("Mobikwik/public_key.pem")
            for kp in paths_to_try:
                loaded = self._load_public_key_from_path(kp)
                if loaded:
                    self.public_key_pem = loaded
                    if raw_path and kp != raw_path:
                        logger.warning(
                            "Mobikwik BBPS: MOBIKWIK_BBPS_PUBLIC_KEY_PATH did not load (%s); using fallback %s",
                            raw_path,
                            kp,
                        )
                    break
        # Key version: Mobikwik README in zip says "Key Version: 1.0" – must match. Wrong value causes "Unsupported Tag" / 900.
        _kv = key_version or getattr(cfg, "MOBIKWIK_BBPS_KEY_VERSION", "1.0")
        _kv_str = str(_kv).strip() if _kv is not None else "1.0"
        if _kv_str in ("1.0", "1"):
            self.key_version = _kv_str
        else:
            if self.use_encryption:
                logger.warning("Mobikwik BBPS KEY_VERSION=%s ignored – README says 1.0; sending 1.0 to avoid 'Unsupported Tag'", _kv_str)
            self.key_version = "1.0"
        self._paths = getattr(cfg, "MOBIKWIK_BBPS_PATHS", None) or DEFAULT_PATHS
        self._token: Optional[str] = None
        # refresh_before: unix time after which we must obtain a new token (Mobikwik expiry minus buffer)
        self._token_expires_at: float = 0.0
        # mobikwik_expires_at: actual expiry from Mobikwik token response (unix); 0 if unknown
        self._token_mobikwik_expires_at: float = 0.0
        self._last_token_error: Optional[str] = None  # actual error when token fails (for logging/UI)
        self._uat_verbose = getattr(cfg, "MOBIKWIK_BBPS_UAT_VERBOSE_LOG", False)
        self._log_sanitize = getattr(cfg, "MOBIKWIK_BBPS_LOG_SANITIZE", True)
        self._retry_on_failure = getattr(cfg, "MOBIKWIK_BBPS_RETRY_ON_FAILURE", True)
        self._request_timeout = float(getattr(cfg, "MOBIKWIK_BBPS_REQUEST_TIMEOUT", 60) or 60)
        _buf = int(getattr(cfg, "MOBIKWIK_BBPS_TOKEN_REFRESH_BUFFER_SECONDS", MOBIKWIK_BBPS_TOKEN_REFRESH_BUFFER_DEFAULT) or MOBIKWIK_BBPS_TOKEN_REFRESH_BUFFER_DEFAULT)
        self._token_refresh_buffer = max(120, min(_buf, 86400))
        _max_m = int(getattr(cfg, "MOBIKWIK_BBPS_TOKEN_MAX_MINTS_PER_DAY", 100) or 100)
        self._token_max_mints_per_day = max(1, min(_max_m, 500))

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

    @staticmethod
    def _sanitize_for_log(data: Dict[str, Any]) -> Dict[str, Any]:
        """Deep-copy request payload for log (no field masking; caller controls whether this is used)."""
        if not data or not isinstance(data, dict):
            return {}
        return copy.deepcopy(data)

    @staticmethod
    def _sanitize_response_for_log(data: Any, max_len: int = 2000) -> str:
        """Serialize response for log without redaction; only truncate for storage safety."""
        if data is None:
            return ""

        if isinstance(data, str):
            s = data
        else:
            try:
                obj = copy.deepcopy(data) if isinstance(data, dict) else data
                s = json.dumps(obj, default=str, sort_keys=True)
            except Exception:
                s = str(data)
        return (s[:max_len] + "...") if len(s) > max_len else s

    # Human-readable names for vendor API (log list/detail: Parkpe vs Mobikwik call diff)
    _VENDOR_ACTION_DISPLAY = {
        "balance_check": "Balance Check",
        "validation": "Validation",
        "view_bill": "View Bill",
        "recharge": "Pay/Recharge",
        "transaction_status": "Transaction Status",
        "operators": "Get Operators",
        "token": "Token",
    }

    def _create_vendor_call_log_entry(
        self,
        action: str,
        url: str,
        method: str,
        request_plain_sanitized: Optional[Dict[str, Any]],
        request_encrypted_summary: Optional[Dict[str, Any]],
        response_status_code: Optional[int],
        response_body_sanitized: str,
        success: bool,
        log_context: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> None:
        """Write one LogEntry for every call to Mobikwik API so Hub log shows Parkpe vs Vendor call. Never raises."""
        try:
            from portal.models import LogEntry
            api_display = self._VENDOR_ACTION_DISPLAY.get(action, action.replace("_", " ").title())
            extra = {
                "action": action,
                "api_name": f"Mobikwik: {api_display}",
                "api_url": url[:500] if url else None,
                "request_method": method,
                "response_status": response_status_code,
                "response_body": response_body_sanitized,
                "success": success,
                "vendor": "Mobikwik",
                "vendor_name": "Mobikwik",
            }
            if error:
                extra["error"] = str(error)[:1000]
            if error_code:
                extra["error_code"] = str(error_code)
            if request_plain_sanitized is not None:
                extra["request_body"] = request_plain_sanitized
            if request_encrypted_summary is not None:
                extra["request_encrypted_summary"] = request_encrypted_summary
            ctx = log_context or {}
            if ctx.get("request_id"):
                extra["request_id"] = ctx["request_id"]
            if ctx.get("response_id"):
                extra["response_id"] = ctx["response_id"]
            if ctx.get("source"):
                extra["source"] = ctx["source"]
            if ctx.get("api_name"):
                extra["upstream_api_name"] = ctx["api_name"]
            trace = ctx.get("request_id") or ctx.get("correlation_id")
            if trace and len(str(trace)) > 100:
                trace = str(trace)[:100]
            LogEntry.objects.create(
                log_level="INFO" if success else "ERROR",
                category="mobikwik_bbps",
                message=f"[Mobikwik] {api_display}",
                module_name="portal.services.vendors.mobikwik",
                url=url[:500] if url else None,
                extra_data=extra,
                request_id=ctx.get("request_id"),
                response_id=ctx.get("response_id"),
                correlation_id=trace,
                chain_step=2,
                log_role="vendor",
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to create Mobikwik vendor log entry: %s", e)

    def _create_uat_log_entry(
        self,
        action: str,
        url: str,
        method: str,
        request_plain_sanitized: Optional[Dict[str, Any]],
        request_encrypted_summary: Optional[Dict[str, Any]],
        response_status_code: Optional[int],
        response_body_sanitized: str,
        success: bool,
        curl_template: str,
        attempts: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write one LogEntry for UAT when MOBIKWIK_BBPS_UAT_VERBOSE_LOG is True. Never raises."""
        try:
            from portal.models import LogEntry
            extra = {
                "action": action,
                "request_url": url,
                "request_method": method,
                "response_status_code": response_status_code,
                "response_body_truncated_sanitized": response_body_sanitized,
                "curl_template": curl_template,
            }
            if request_plain_sanitized is not None:
                extra["request_body_plain_sanitized"] = request_plain_sanitized
            if request_encrypted_summary is not None:
                extra["request_body_encrypted_summary"] = request_encrypted_summary
            if attempts is not None:
                extra["attempts"] = attempts
            LogEntry.objects.create(
                log_level="INFO" if success else "ERROR",
                category="mobikwik_bbps",
                message=f"UAT: {action}",
                module_name="portal.services.vendors.mobikwik",
                url=url[:500] if url else None,
                extra_data=extra,
            )
        except Exception:
            pass

    def _load_public_key_from_path(self, key_path: str) -> Optional[str]:
        """Load PEM content from file path. Path can be absolute or relative to project root (BASE_DIR).
        If exact path fails (e.g. Mobikwik vs mobikwik folder name), tries alternate casing for first segment.
        """
        import os
        from django.conf import settings
        if not key_path or not str(key_path).strip():
            return None
        key_path = key_path.strip()
        path = key_path
        if not os.path.isabs(path):
            base = getattr(settings, "BASE_DIR", None)
            if base:
                path = os.path.join(base, key_path)
        to_try = [path]
        # Agar file nahi mili to folder name ka case try karo (Mobikwik vs mobikwik)
        if not os.path.isabs(key_path):
            parts = key_path.replace("\\", "/").split("/")
            if len(parts) >= 1 and parts[0]:
                alt = parts[0].lower() if parts[0][:1].isupper() else (parts[0][:1].upper() + (parts[0][1:] if len(parts[0]) > 1 else ""))
                if alt != parts[0] and base:
                    alt_path = os.path.join(base, alt, *parts[1:])
                    to_try.append(alt_path)
        for p in to_try:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    pem = f.read()
                pem = pem.strip()
                if "-----BEGIN" in pem and "-----END" in pem:
                    return pem
                logger.warning("Mobikwik BBPS: PEM file missing BEGIN/END markers", extra_data={"path": p})
                return pem or None
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.error("Mobikwik BBPS: failed to load public key from path", extra_data={"path": p, "error": str(e)})
                if p == path:
                    continue
                return None
        logger.error("Mobikwik BBPS: public key file not found (tried: {})".format(", ".join(to_try)))
        return None

    def _extract_token_from_response(self, data: Dict[str, Any], data_obj: Dict[str, Any]) -> Optional[str]:
        """
        Extract token string from token API response. Tries config path first, then common shapes.
        """
        try:
            from core.config import payswap_config
            path_conf = getattr(payswap_config, "MOBIKWIK_BBPS_TOKEN_RESPONSE_PATH", None)
            if path_conf and isinstance(path_conf, str) and path_conf.strip():
                parts = [p.strip() for p in path_conf.strip().split(".") if p.strip()]
                if parts:
                    obj = data
                    for key in parts:
                        if not isinstance(obj, dict):
                            break
                        obj = obj.get(key)
                    if isinstance(obj, str) and obj:
                        return obj
        except Exception:
            pass
        token = (
            data_obj.get("token")
            or data.get("token")
            or data.get("accessToken")
            or data.get("access_token")
        )
        if token and isinstance(token, str):
            return token
        for key in ("result", "response", "body"):
            obj = data.get(key) if isinstance(data, dict) else None
            if isinstance(obj, dict):
                token = obj.get("token") or obj.get("accessToken") or obj.get("access_token")
                if token and isinstance(token, str):
                    return token
        return None

    def _parse_mobikwik_expiry_string(self, expiry_str: str) -> Optional[float]:
        """
        Parse Mobikwik expiryTime (e.g. 'YYYY-MM-DD HH:mm:ss') to unix timestamp.
        Naive strings are interpreted as Asia/Kolkata (Mobikwik India docs); fallback to local.
        """
        if not expiry_str or not isinstance(expiry_str, str):
            return None
        s = expiry_str.strip()
        if not s:
            return None
        from datetime import datetime as dt

        if len(s) >= 19 and s[4] == "-" and s[7] == "-" and s[10] in " T":
            core = s[:19].replace("T", " ")
            try:
                from zoneinfo import ZoneInfo

                from core.config import payswap_config

                tz_name = getattr(payswap_config, "MOBIKWIK_BBPS_TOKEN_EXPIRY_TIMEZONE", None) or "Asia/Kolkata"
                nd = dt.strptime(core, "%Y-%m-%d %H:%M:%S")
                nd = nd.replace(tzinfo=ZoneInfo(str(tz_name)))
                return nd.timestamp()
            except Exception:
                try:
                    nd = dt.strptime(core, "%Y-%m-%d %H:%M:%S")
                    return nd.timestamp()
                except Exception:
                    return None
        return None

    def _extract_mobikwik_expiry_unix(self, data: Dict[str, Any], data_obj: Dict[str, Any]) -> Optional[float]:
        """Read Mobikwik token expiry from response (several possible keys / numeric epoch)."""
        keys_str = (
            "expiryTime",
            "expiresAt",
            "expireTime",
            "tokenExpiry",
            "expiry_time",
            "token_expiry",
        )
        for d in (data_obj, data):
            if not isinstance(d, dict):
                continue
            for k in keys_str:
                v = d.get(k)
                if v is None:
                    continue
                if isinstance(v, (int, float)):
                    ts = float(v)
                    if ts > 1e15:  # microseconds
                        ts /= 1e6
                    elif ts > 1e12:  # milliseconds
                        ts /= 1000.0
                    if ts > 1e9:
                        return ts
                if isinstance(v, str) and v.strip():
                    parsed = self._parse_mobikwik_expiry_string(v.strip())
                    if parsed is not None:
                        return parsed
        return None

    def _hydrate_token_from_cache_dict(self, cached: Dict[str, Any]) -> bool:
        """
        Load token from cache payload. Returns True if token is still valid (before refresh_before).
        Supports legacy shape: {'token', 'expires_at'} where expires_at was already refresh_before.
        """
        token = cached.get("token")
        refresh_before = cached.get("refresh_before")
        if refresh_before is None:
            refresh_before = cached.get("expires_at") or 0
        mobikwik_exp = float(cached.get("mobikwik_expires_at") or 0.0)
        try:
            refresh_before = float(refresh_before)
        except (TypeError, ValueError):
            refresh_before = 0.0
        if not token or not isinstance(token, str):
            return False
        if time.time() >= refresh_before:
            return False
        self._token = token
        self._token_expires_at = refresh_before
        self._token_mobikwik_expires_at = mobikwik_exp
        self._last_token_error = None
        return True

    def _token_mint_day_cache_key(self) -> str:
        """Cache key for counting Token API successes per calendar day (IST by default)."""
        from datetime import datetime

        try:
            from zoneinfo import ZoneInfo
        except ImportError:  # Python < 3.9
            ZoneInfo = None  # type: ignore
        from core.config import payswap_config

        tz_name = getattr(payswap_config, "MOBIKWIK_BBPS_TOKEN_EXPIRY_TIMEZONE", None) or "Asia/Kolkata"
        if ZoneInfo is None:
            day = datetime.utcnow().date().isoformat()
        else:
            try:
                tz = ZoneInfo(str(tz_name))
            except Exception:
                tz = ZoneInfo("Asia/Kolkata")
            day = datetime.now(tz).date().isoformat()
        return f"mobikwik_bbps_token_mints:{day}"

    def _check_token_mint_daily_budget(self) -> Optional[Dict[str, Any]]:
        """Block Token HTTP call if today's mint count >= MOBIKWIK_BBPS_TOKEN_MAX_MINTS_PER_DAY (~100)."""
        try:
            from django.core.cache import cache

            key = self._token_mint_day_cache_key()
            day = key.split(":")[-1]
            n = cache.get(key)
            if n is not None and int(n) >= self._token_max_mints_per_day:
                return {
                    "success": False,
                    "error": (
                        f"Daily Mobikwik token mint budget reached ({self._token_max_mints_per_day} for {day}). "
                        "Vendor policy ~100 new tokens/day — reuse the shared cached token or continue after midnight IST."
                    ),
                    "error_code": "TOKEN_DAILY_BUDGET",
                }
        except Exception:
            return None
        return None

    def _record_token_mint_success(self) -> None:
        """Increment today's mint counter after a successful response from Mobikwik Token API."""
        try:
            from django.core.cache import cache

            key = self._token_mint_day_cache_key()
            cur = cache.get(key)
            cur_i = int(cur) if cur is not None else 0
            cache.set(key, cur_i + 1, timeout=172800)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Token (new API)
    # -------------------------------------------------------------------------

    def get_token(
        self,
        force_refresh: bool = False,
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Token Generation API – get access token using Client ID + Client Secret.
        Required before Balance Check, Validation, View Bill, Recharge, Transaction Status.
        Parses Mobikwik expiryTime (and variants), stores mobikwik_expires_at and refresh_before
        (refresh self._token_refresh_buffer seconds before that). Uses shared cache until
        refresh_before. force_refresh=True skips cache (use after invalidate / token-expired API response).
        log_context: optional ParkPe request_id / source so Hub LogEntry rows link to the same trace.
        """
        _ctx = log_context or {}
        _trace_request_id = _ctx.get("request_id")
        if not self.client_id or not self.client_secret:
            return {
                "success": False,
                "error": "MOBIKWIK_BBPS_CLIENT_ID and MOBIKWIK_BBPS_CLIENT_SECRET are required for token",
                "error_code": "CONFIG_MISSING",
            }
        # Shared cache: use token only while time.time() < refresh_before (see _hydrate_token_from_cache_dict)
        if not force_refresh:
            try:
                from django.core.cache import cache

                cached = cache.get(MOBIKWIK_BBPS_TOKEN_CACHE_KEY)
                if isinstance(cached, dict) and self._hydrate_token_from_cache_dict(cached):
                    return {"success": True, "data": {}, "token": self._token}
            except Exception:
                pass
        # Token path: override via MOBIKWIK_BBPS_TOKEN_PATH (per Mobikwik RT-Recharge & Bill Payment API doc) or use default
        from core.config import payswap_config
        token_path = getattr(payswap_config, "MOBIKWIK_BBPS_TOKEN_PATH", None)
        path = (token_path or self._get_path("token")).strip().strip("/")
        base = self.base_url.rstrip("/")
        # Postman/UAT: no trailing slash – /recharge/v1/verify/retailer
        url = f"{base}/{path}" if path else base
        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
        }
        # Official UAT Postman: Token Generation = plain JSON at /recharge/v1/verify/retailer (same path for alpha3 and often B2B).
        # Encrypted token body is opt-in: MOBIKWIK_BBPS_TOKEN_USE_ENCRYPTION=True (confirm with Mobikwik for your bundle).
        # Do not auto-encrypt only because base URL is rapi-b2b — that produced 1308 Invalid request for many lprod setups.
        plain_override = bool(getattr(payswap_config, "MOBIKWIK_BBPS_TOKEN_PLAIN_JSON", False))
        explicit_enc = bool(getattr(payswap_config, "MOBIKWIK_BBPS_TOKEN_USE_ENCRYPTION", False))
        if plain_override:
            token_encrypt = False
        elif explicit_enc:
            token_encrypt = True
        else:
            token_encrypt = False
        if token_encrypt:
            if not self.public_key_pem:
                self._last_token_error = (
                    "Encrypted Mobikwik token body requires a public key. Set MOBIKWIK_BBPS_PUBLIC_KEY_PATH "
                    "(PEM from onboarding email) or MOBIKWIK_BBPS_PUBLIC_KEY. "
                    "Only for Mobikwik-approved plain-token tests: MOBIKWIK_BBPS_TOKEN_PLAIN_JSON=True."
                )
                return {
                    "success": False,
                    "error": self._last_token_error,
                    "error_code": "CONFIG_MISSING",
                }
            body = self._encrypt_payload(payload, for_token_api=True)
            if "encryptedSessionKey" not in body:
                self._last_token_error = "Token request encryption failed (check public key PEM and pycryptodome)"
                return {
                    "success": False,
                    "error": self._last_token_error,
                    "error_code": "ENCRYPT_FAILED",
                }
        else:
            body = payload
        budget_err = self._check_token_mint_daily_budget()
        if budget_err:
            self._last_token_error = budget_err.get("error")
            return budget_err
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    url,
                    json=body,
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
                if self._uat_verbose:
                    req_sanitized = self._sanitize_for_log(payload)
                    curl_tpl = f"curl -X POST '{url}' -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{json.dumps(req_sanitized)}'"
                    self._create_uat_log_entry(
                        "token", url, "POST", req_sanitized, None,
                        resp.status_code, self._sanitize_response_for_log({"_raw": raw}), False, curl_tpl,
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
                if self._uat_verbose:
                    req_sanitized = self._sanitize_for_log(payload)
                    curl_tpl = f"curl -X POST '{url}' -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{json.dumps(req_sanitized)}'"
                    self._create_uat_log_entry(
                        "token", url, "POST", req_sanitized, None,
                        resp.status_code, self._sanitize_response_for_log(data), False, curl_tpl,
                    )
                return {
                    "success": False,
                    "error": self._last_token_error,
                    "status_code": resp.status_code,
                    "response": data,
                }
            # PDF: success response has data.token and data.expiryTime; support other shapes via _extract_token
            data_obj = data.get("data") or {}
            token = self._extract_token_from_response(data, data_obj)
            if not token:
                # Prefer Mobikwik's message when present (e.g. success: false, message: "..." or message: {code, text})
                vendor_msg = None
                if isinstance(data, dict):
                    for key in ("message", "error", "msg", "Message", "Error", "errorMessage", "error_message"):
                        v = data.get(key)
                        if v is None:
                            continue
                        if isinstance(v, str) and v.strip():
                            vendor_msg = v.strip()[:500]
                            break
                        if isinstance(v, dict):
                            # e.g. {"code": "1308", "text": "allowed token limit exceeded"}
                            text = (v.get("text") or v.get("message") or v.get("msg") or v.get("description"))
                            if isinstance(text, str) and text.strip():
                                code = v.get("code") or v.get("error_code")
                                vendor_msg = (f"{code}: " if code else "") + text.strip()[:480]
                            else:
                                vendor_msg = str(v).strip()[:500]
                            break
                        vendor_msg = str(v).strip()[:500]
                        break
                if vendor_msg:
                    self._last_token_error = vendor_msg
                    if isinstance(data, dict):
                        m = data.get("message")
                        if isinstance(m, dict) and str(m.get("code", "")) == "1308":
                            if not token_encrypt:
                                self._last_token_error = (
                                    f"{vendor_msg} — With plain token body: verify MOBIKWIK_BBPS_CLIENT_ID / "
                                    "MOBIKWIK_BBPS_CLIENT_SECRET match this base URL (UAT vs rapi-b2b). "
                                    "If Mobikwik requires encrypted token for your account, set MOBIKWIK_BBPS_TOKEN_USE_ENCRYPTION=True "
                                    "and MOBIKWIK_BBPS_PUBLIC_KEY_PATH to the PEM from the same onboarding bundle."
                                )
                            else:
                                self._last_token_error = (
                                    f"{vendor_msg} — Encrypted token body: confirm clientId/secret, PEM matches bundle, "
                                    "MOBIKWIK_BBPS_KEY_VERSION matches README. If Mobikwik says token API is plain JSON only, "
                                    "set MOBIKWIK_BBPS_TOKEN_USE_ENCRYPTION=False (and optionally MOBIKWIK_BBPS_TOKEN_PLAIN_JSON=True)."
                                )
                else:
                    keys_hint = ", ".join(str(k) for k in (data.keys() if isinstance(data, dict) else []))[:180]
                    self._last_token_error = "Token not found in response" + (f"; top-level keys: {keys_hint}" if keys_hint else "")
                sanitized_body = self._sanitize_response_for_log(data)
                logger.warning(
                    "Mobikwik BBPS token not found in response",
                    extra_data={"response_preview": sanitized_body[:1500], "url": url, "status_code": resp.status_code},
                )
                try:
                    from portal.models import LogEntry
                    _extra_token = {
                        "action": "token",
                        "response_status_code": resp.status_code,
                        "response_body_sanitized": sanitized_body,
                        "top_level_keys": list(data.keys()) if isinstance(data, dict) else None,
                    }
                    if _ctx.get("source"):
                        _extra_token["source"] = _ctx["source"]
                    if _ctx.get("api_name") or _ctx.get("upstream_api_name"):
                        _extra_token["upstream_api_name"] = _ctx.get("api_name") or _ctx.get("upstream_api_name")
                    if _trace_request_id:
                        _extra_token["request_id"] = _trace_request_id
                    LogEntry.objects.create(
                        log_level="WARNING",
                        category="mobikwik_bbps",
                        message="Token not found in response",
                        module_name="portal.services.vendors.mobikwik",
                        url=url[:500] if url else None,
                        request_id=_trace_request_id,
                        extra_data=_extra_token,
                    )
                except Exception:
                    pass
                if self._uat_verbose:
                    req_sanitized = self._sanitize_for_log(payload)
                    curl_tpl = f"curl -X POST '{url}' -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{json.dumps(req_sanitized)}'"
                    self._create_uat_log_entry(
                        "token", url, "POST", req_sanitized, None,
                        resp.status_code, sanitized_body, False, curl_tpl,
                    )
                return {
                    "success": False,
                    "error": self._last_token_error,
                    "response": data,
                }
            self._token = token
            self._last_token_error = None
            now = time.time()
            mobikwik_expires_at = self._extract_mobikwik_expiry_unix(data, data_obj)
            if mobikwik_expires_at is None:
                mobikwik_expires_at = now + 86400.0
                logger.debug(
                    "Mobikwik BBPS: no expiryTime in token response; assuming 24h validity from now",
                    extra_data={"url": url},
                )
            elif mobikwik_expires_at <= now:
                logger.warning(
                    "Mobikwik BBPS: token expiryTime is in the past or clock skew; assuming 24h from now",
                    extra_data={"url": url, "parsed_expiry_ts": mobikwik_expires_at},
                )
                mobikwik_expires_at = now + 86400.0
            # Stop using this token this many seconds before Mobikwik's real expiry (proactive renew)
            refresh_before = mobikwik_expires_at - float(self._token_refresh_buffer)
            if refresh_before <= now:
                refresh_before = now + 120.0
                logger.warning(
                    "Mobikwik BBPS: refresh_before was not in the future; using 120s grace window",
                    extra_data={"mobikwik_expires_at": mobikwik_expires_at},
                )
            self._token_mobikwik_expires_at = mobikwik_expires_at
            self._token_expires_at = refresh_before
            logger.debug(
                "Mobikwik BBPS: token stored (mobikwik_expires_at, refresh_before)",
                extra_data={
                    "mobikwik_expires_at": mobikwik_expires_at,
                    "refresh_before": refresh_before,
                    "buffer_sec": self._token_refresh_buffer,
                },
            )
            # Store in cache so all workers reuse same token (100 tokens/day limit)
            try:
                from django.core.cache import cache

                cache_ttl = max(60, int(mobikwik_expires_at - now) + 120)
                cache.set(
                    MOBIKWIK_BBPS_TOKEN_CACHE_KEY,
                    {
                        "token": self._token,
                        "mobikwik_expires_at": mobikwik_expires_at,
                        "refresh_before": refresh_before,
                        "expires_at": refresh_before,  # legacy: same as refresh_before
                    },
                    timeout=cache_ttl,
                )
            except Exception:
                pass
            self._record_token_mint_success()
            if self._uat_verbose:
                req_sanitized = self._sanitize_for_log(payload)
                curl_tpl = f"curl -X POST '{url}' -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{json.dumps(req_sanitized)}'"
                self._create_uat_log_entry(
                    "token", url, "POST", req_sanitized, None,
                    resp.status_code, self._sanitize_response_for_log(data), True, curl_tpl,
                )
            return {"success": True, "data": data, "token": token}
        except Exception as e:
            self._last_token_error = str(e)[:500]
            logger.error("Mobikwik BBPS token request failed", extra_data={"error": self._last_token_error})
            if self._uat_verbose:
                req_sanitized = self._sanitize_for_log(payload)
                curl_tpl = f"curl -X POST '{url}' -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{json.dumps(req_sanitized)}'"
                self._create_uat_log_entry(
                    "token", url, "POST", req_sanitized, None,
                    None, str(e)[:2000], False, curl_tpl,
                )
            return {"success": False, "error": self._last_token_error, "error_code": "TOKEN_FAILED"}

    def _invalidate_cached_token(self) -> None:
        """Clear in-memory and Django cache token so next call fetches a fresh token from Mobikwik."""
        self._token = None
        self._token_expires_at = 0.0
        self._token_mobikwik_expires_at = 0.0
        try:
            from django.core.cache import cache
            cache.delete(MOBIKWIK_BBPS_TOKEN_CACHE_KEY)
        except Exception:
            pass

    def _is_token_expired_response(self, last_result: Optional[Dict[str, Any]]) -> bool:
        """
        True if Mobikwik rejected the call due to expired/invalid token.
        They often return HTTP 200 with body success:false, message.code 401, text 'Token is expired'.
        """
        if not last_result or last_result.get("success"):
            return False
        status = last_result.get("status_code") or 0
        if status == 401:
            return True
        data = last_result.get("response") or last_result.get("data") or {}
        if not isinstance(data, dict):
            return False
        msg = data.get("message")
        if isinstance(msg, dict):
            code = str(msg.get("code", "")).strip().lower()
            text = (msg.get("text") or msg.get("message") or "").lower()
            if code in ("401", "token_expired", "unauthorized"):
                return True
            if "token" in text and "expir" in text:
                return True
            if "invalid" in text and "token" in text:
                return True
        if isinstance(msg, str) and "expir" in msg.lower():
            return True
        err = str(last_result.get("error") or "").lower()
        if "token" in err and "expir" in err:
            return True
        return False

    def _ensure_token(self, log_context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Ensure we have a valid token. Returns True if token is available.
        Prefer Django cache (shared across workers) before process-local memory so one worker
        refreshing the token is picked up by others; avoids stale in-memory JWT after cache updates.
        """
        try:
            from django.core.cache import cache

            cached = cache.get(MOBIKWIK_BBPS_TOKEN_CACHE_KEY)
            if isinstance(cached, dict) and self._hydrate_token_from_cache_dict(cached):
                return True
        except Exception:
            pass
        if self._token and time.time() < self._token_expires_at:
            return True
        result = self.get_token(log_context=log_context)
        return result.get("success") is True

    def _uses_new_token_api(self) -> bool:
        """True when Client ID + Secret flow (Mobikwik UAT Postman): requests use only Content-Type + Authorization."""
        return bool(self.client_id and self.client_secret)

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        base = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._token:
            # PDF: "Authorization: <token>" (token only, no Bearer prefix)
            base["Authorization"] = self._token
        # Postman UAT: Balance / View Bill / Pay / Status — only these headers (no X-Merchant-Id / X-API-Key).
        if self._uses_new_token_api():
            if extra:
                base.update(extra)
            return base
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

    def _encrypt_payload(
        self, payload: Dict[str, Any], *, for_token_api: bool = False
    ) -> Dict[str, Any]:
        """
        Build encrypted request body per Mobikwik RT-Recharge doc: encryptedSessionKey, encryptedPayload, keyVersion, iv.
        - Session key: 256-bit AES random. Payload: AES-256-GCM, 16-byte IV, 128-bit GCM tag (ciphertext+tag then Base64).
        - Session key encrypted with RSA-2048 PKCS1Padding (Mobikwik public key). keyVersion from readme (e.g. "1.0").
        for_token_api: when True, encrypt token request (MOBIKWIK_BBPS_TOKEN_USE_ENCRYPTION) even if other APIs use plain UAT override.
        """
        if for_token_api:
            if not self.public_key_pem:
                return payload
        elif not self.use_encryption or not self.public_key_pem:
            return payload
        try:
            from Crypto.Cipher import AES
            from Crypto.Random import get_random_bytes

            session_key = get_random_bytes(32)  # 256-bit AES session key per doc
            nonce = get_random_bytes(16)  # IV 16 bytes per Mobikwik doc (Encryption Protocol / Java sample)
            # Doc sample order: cn, op, cir, adParams (cir may be ""). No sort_keys.
            plaintext = json.dumps(payload, sort_keys=False, separators=(',', ':')).encode("utf-8")
            cipher = AES.new(session_key, AES.MODE_GCM, nonce=nonce, mac_len=16)  # 128-bit GCM tag per doc
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
                "keyVersion": str(self.key_version),
                "iv": iv_b64,
            }
        except Exception as e:
            import traceback
            logger.warning(
                "Mobikwik payload encryption failed, sending plain",
                extra_data={"error": str(e), "traceback": traceback.format_exc()[:1500]},
            )
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
        timeout: Optional[float] = None,
        action: Optional[str] = None,
        log_context: Optional[Dict[str, Any]] = None,
        _token_retry: int = 0,
    ) -> Dict[str, Any]:
        """Make HTTP request to Mobikwik BBPS API. Optionally encrypt body. Retry once on timeout/5xx when enabled.
        On token-expired (HTTP 401 or body message.code 401), invalidate cache, refresh token, retry once."""
        timeout = timeout if timeout is not None else self._request_timeout
        if not self.is_configured():
            return {
                "success": False,
                "error": "MOBIKWIK_BBPS is not configured or enabled",
                "error_code": "CONFIG_MISSING",
            }
        if require_token and (self.client_id and self.client_secret):
            try:
                if not self._ensure_token(log_context=log_context):
                    detail = f": {self._last_token_error}" if self._last_token_error else ""
                    return {
                        "success": False,
                        "error": f"Failed to obtain Mobikwik BBPS token{detail}",
                        "error_code": "TOKEN_FAILED",
                        "response": {"detail": self._last_token_error} if self._last_token_error else None,
                    }
            except Exception as e:
                logger.exception("Mobikwik BBPS _ensure_token failed")
                return {
                    "success": False,
                    "error": f"Token error: {e!s}"[:500],
                    "error_code": "TOKEN_FAILED",
                }
        url = f"{self.base_url}{path}"
        try:
            plain_copy = copy.deepcopy(json_data) if (method.upper() == "POST" and json_data is not None) else None
        except Exception:
            plain_copy = None
        if method.upper() == "POST" and json_data is not None:
            try:
                json_data = self._encrypt_payload(json_data)
                if "encryptedSessionKey" in json_data:
                    logger.info("Mobikwik BBPS: sending encrypted payload", extra_data={"action": action})
                else:
                    logger.info("Mobikwik BBPS: sending plain JSON (encryption disabled)", extra_data={"action": action})
            except Exception as e:
                logger.warning("Mobikwik encrypt_payload failed, sending plain", extra_data={"error": str(e)})
        encrypted_summary = None
        if json_data and "encryptedSessionKey" in json_data:
            # Log me keyVersion actual value dikhe (1.0), baaki lengths (sensitive na ho)
            encrypted_summary = {}
            for k, v in json_data.items():
                if k == "keyVersion":
                    encrypted_summary[k] = v  # "1.0" – actual value for debugging
                elif isinstance(v, str):
                    encrypted_summary[k] = len(v)
                else:
                    encrypted_summary[k] = v

        attempts_log: List[Dict[str, Any]] = []
        last_result: Optional[Dict[str, Any]] = None
        try:
            for attempt in (1, 2):
                if attempt == 2:
                    time.sleep(2)
                try:
                    with httpx.Client(timeout=timeout) as client:
                        resp = client.request(
                            method,
                            url,
                            json=json_data,
                            params=params,
                            headers=self._headers(),
                        )
                except httpx.TimeoutException as e:
                    logger.warning("Mobikwik BBPS request timeout", extra_data={"url": url, "error": str(e)})
                    last_result = {"success": False, "error": "Request timeout", "error_code": "TIMEOUT"}
                    if self._uat_verbose:
                        attempts_log.append({
                            "attempt": attempt,
                            "response_status_code": None,
                            "response_body": "Request timeout",
                        })
                    if attempt == 1 and self._retry_on_failure:
                        continue
                    break
                except Exception as e:
                    logger.error("Mobikwik BBPS request failed", extra_data={"error": str(e)})
                    last_result = {"success": False, "error": str(e), "error_code": "REQUEST_FAILED"}
                    if self._uat_verbose:
                        attempts_log.append({
                            "attempt": attempt,
                            "response_status_code": None,
                            "response_body": str(e)[:2000],
                        })
                    break
                try:
                    data = resp.json() if resp.content else {}
                except (ValueError, json.JSONDecodeError):
                    data = {"_raw": (resp.text or (resp.content.decode("utf-8", errors="replace") if resp.content else ""))[:500]}
                if self._uat_verbose:
                    attempts_log.append({
                        "attempt": attempt,
                        "response_status_code": resp.status_code,
                        "response_body": self._sanitize_response_for_log(data),
                    })
                if resp.status_code >= 400:
                    last_result = {
                        "success": False,
                        "error": data.get("message", data.get("error", resp.text)),
                        "status_code": resp.status_code,
                        "response": data,
                    }
                    if resp.status_code >= 500 and attempt == 1 and self._retry_on_failure:
                        continue
                    break
                # HTTP 200 but body can have success: false (e.g. Mobikwik 900)
                # Treat missing "success" as True – some APIs return responseCode/data without success key
                body_success = data.get("success") if isinstance(data, dict) else True
                is_success = False if body_success is False else True
                last_result = {
                    "success": is_success,
                    "data": data,
                    "status_code": resp.status_code,
                    "response": data,
                }
                if body_success is False and isinstance(data, dict):
                    msg = data.get("message")
                    if isinstance(msg, dict):
                        msg = msg.get("text") or msg.get("message") or str(msg)
                    last_result["error"] = msg or data.get("error") or "Request failed"
                break
        except Exception as e:
            logger.exception("Mobikwik BBPS _request unexpected error")
            last_result = {"success": False, "error": str(e)[:500], "error_code": "REQUEST_FAILED"}

        if last_result is None:
            last_result = {"success": False, "error": "No response", "error_code": "REQUEST_FAILED"}

        # Mobikwik often returns HTTP 200 with success:false and message.code 401 "Token is expired" — refresh and retry once
        if (
            last_result
            and not last_result.get("success")
            and _token_retry < 1
            and require_token
            and self.client_id
            and self.client_secret
            and self._is_token_expired_response(last_result)
        ):
            post_needs_plain = method.upper() == "POST" and json_data is not None
            if post_needs_plain and plain_copy is None:
                logger.warning(
                    "Mobikwik BBPS: token expired but cannot retry without plain payload copy",
                    extra_data={"url": url, "action": action},
                )
            else:
                logger.warning(
                    "Mobikwik BBPS: token rejected; invalidating cache, fetching new token, retrying once",
                    extra_data={"url": url, "action": action},
                )
                self._invalidate_cached_token()
                refresh = self.get_token(force_refresh=True, log_context=log_context)
                if refresh.get("success"):
                    retry_body = plain_copy if plain_copy is not None else json_data
                    return self._request(
                        method,
                        path,
                        retry_body,
                        params,
                        require_token,
                        timeout,
                        action,
                        log_context,
                        _token_retry=_token_retry + 1,
                    )
                re_err = refresh.get("error") or "Token API failed"
                logger.error(
                    "Mobikwik BBPS: token was expired; force refresh failed — check daily token limit (e.g. 1308), credentials, base URL",
                    extra_data={"refresh_error": str(re_err)[:500], "action": action},
                )
                last_result = {
                    "success": False,
                    "error": f"Token expired; renew failed: {re_err}",
                    "status_code": last_result.get("status_code"),
                    "response": last_result.get("response"),
                    "token_refresh_error": re_err,
                }

        # Always log vendor API call so Hub shows Parkpe log vs Mobikwik call (dono ka diff)
        try:
            if self._log_sanitize:
                req_for_log = self._sanitize_for_log(plain_copy) if plain_copy else {}
                resp_body = self._sanitize_response_for_log(
                    last_result.get("response") or last_result.get("data") or ""
                )
            else:
                req_for_log = copy.deepcopy(plain_copy) if plain_copy else {}
                _resp_data = last_result.get("response") or last_result.get("data") or ""
                try:
                    resp_body = json.dumps(_resp_data, default=str, ensure_ascii=False)[:5000]
                except Exception:
                    resp_body = str(_resp_data)[:5000]
            resp_status = last_result.get("status_code")
            # When no HTTP response (timeout, connection error), include error/error_code so log shows why it failed
            err_msg = last_result.get("error")
            err_code = last_result.get("error_code")
            if not resp_body and err_msg:
                resp_body = f"[No response] {err_code or 'ERROR'}: {err_msg}"
            self._create_vendor_call_log_entry(
                action or "request",
                url,
                method,
                req_for_log,
                encrypted_summary,
                resp_status,
                resp_body,
                last_result.get("success", False),
                log_context=log_context,
                error=err_msg,
                error_code=err_code,
            )
        except Exception:
            pass

        if self._uat_verbose:
            try:
                if self._log_sanitize:
                    req_sanitized = self._sanitize_for_log(plain_copy) if plain_copy else {}
                    response_body_sanitized = self._sanitize_response_for_log(
                        last_result.get("response") or last_result.get("data") or ""
                    )
                else:
                    req_sanitized = copy.deepcopy(plain_copy) if plain_copy else {}
                    _rd = last_result.get("response") or last_result.get("data") or ""
                    try:
                        response_body_sanitized = json.dumps(_rd, default=str, ensure_ascii=False)[:5000]
                    except Exception:
                        response_body_sanitized = str(_rd)[:5000]
                response_status_code = last_result.get("status_code")
                attempts_extra = None
                if attempts_log:
                    attempts_extra = {f"attempt_{a['attempt']}": a for a in attempts_log}
                if method.upper() == "GET":
                    curl_tpl = (
                        f"curl -X GET '{url}' "
                        f"-H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: ***'"
                    )
                else:
                    curl_body = json.dumps(req_sanitized) if req_sanitized else "{}"
                    curl_tpl = (
                        f"curl -X {method.upper()} '{url}' "
                        f"-H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: ***' "
                        f"-d '{curl_body}'"
                    )
                self._create_uat_log_entry(
                    action or "request",
                    url,
                    method,
                    req_sanitized,
                    encrypted_summary,
                    response_status_code,
                    response_body_sanitized,
                    last_result.get("success", False),
                    curl_tpl,
                    attempts=attempts_extra,
                )
            except Exception:
                pass
        return last_result

    # -------------------------------------------------------------------------
    # New APIs (per UAT: Balance Check, Validation, View Bill, Recharge, Transaction Status)
    # -------------------------------------------------------------------------

    def _balance_member_id_live(self) -> Optional[str]:
        """Current MOBIKWIK_BBPS_MEMBER_ID for Balance API (fresh .env read when constructor did not pin member_id)."""
        if getattr(self, "_balance_member_id_re_read_env", False):
            try:
                from core.config import PayswapConfig

                return _optional_env_string(PayswapConfig().MOBIKWIK_BBPS_MEMBER_ID)
            except Exception:
                pass
        return _optional_env_string(self.member_id)

    def balance_check(self, log_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Balance Check — POST /recharge/v3/retailerBalance.
        UAT Postman: encrypt plain body {"memberId": MEMBER_ID} only; no X-Merchant-Id on the request.
        If only merchantId is configured (no member email), send {"merchantId": ...}.
        """
        path = self._get_path("balance")
        payload = {}
        balance_member = self._balance_member_id_live()
        if balance_member:
            payload["memberId"] = balance_member
        elif self.merchant_id:
            payload["merchantId"] = self.merchant_id
        # Mobikwik production sometimes rejects specific memberId values with 1308, while accepting blank memberId.
        # Keep primary payload first, then fallback to blank memberId for better operational resilience.
        primary_payload = payload if payload else {"memberId": ""}
        result = self._request("POST", path, json_data=primary_payload, action="balance_check", log_context=log_context)
        if result.get("success"):
            return result

        def _body(res: Dict[str, Any]) -> Dict[str, Any]:
            b = res.get("response") or res.get("data") or {}
            return b if isinstance(b, dict) else {}

        def _msg_code(res: Dict[str, Any]) -> str:
            m = _body(res).get("message")
            if isinstance(m, dict):
                return str(m.get("code", "")).strip()
            return ""

        code = _msg_code(result)
        last_result = result

        # 1308 + non-empty memberId → blank memberId (token-scoped retailer)
        should_retry_blank_member = (
            code == "1308"
            and bool(payload.get("memberId"))
            and str(payload.get("memberId", "")).strip() != ""
        )
        if should_retry_blank_member:
            logger.warning("Mobikwik balance_check got 1308 for configured memberId; retrying with blank memberId.")
            retry_result = self._request(
                "POST",
                path,
                json_data={"memberId": ""},
                action="balance_check",
                log_context=log_context,
            )
            last_result = retry_result
            if retry_result.get("success"):
                return retry_result
            # Still 1308 and merchantId configured (B2B often keys balance on merchantId, not email)
            if self.merchant_id and _msg_code(retry_result) == "1308":
                logger.warning(
                    "Mobikwik balance_check still 1308 after blank memberId; retrying with merchantId.",
                    extra_data={"merchant_id_set": True},
                )
                mid_result = self._request(
                    "POST",
                    path,
                    json_data={"merchantId": self.merchant_id},
                    action="balance_check",
                    log_context=log_context,
                )
                last_result = mid_result
                if mid_result.get("success"):
                    return mid_result

        return last_result

    def validation(
        self,
        operator_id: str,
        customer_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validation API – validate consumer (prepaid). Payload per PDF: amt, cn, op, cir, planCode?, adParams.
        For bill fetch use view_bill() instead.
        """
        path = self._get_path("validation")
        extra = extra_params or {}
        cir = extra.get("cir", "")
        ad_params = {k: v for k, v in extra.items() if k not in ("cir", "amt", "planCode", "agentId")}
        op_val = self._op_int(operator_id)
        payload = {
            "amt": extra.get("amt", "1"),
            "cn": customer_id,
            "op": str(op_val) if op_val is not None else operator_id,
            "cir": cir or "",
            "adParams": ad_params,
        }
        if extra.get("planCode"):
            payload["planCode"] = extra["planCode"]
        # Postman UAT: agentId required in Validation payload
        agent_id = extra.get("agentId") or self.agent_id
        if agent_id:
            payload["agentId"] = agent_id
        return self._request("POST", path, json_data=payload, action="validation", log_context=log_context)

    def view_bill(
        self,
        operator_id: str,
        customer_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        View Bill API – POST /recharge/v3/retailerViewbill.
        - Plain body (encrypted when enabled): cn, op, cir, adParams — **cir key hamesha**; value tabhi bhejo
          jab operator/ request / sheet se circle mile. Circle na ho to **cir: ""** (empty string), placeholder
          jaise "1" mat bhejo (galat circle par BLR016).
        - Response: {"success": true, "data": [{"billAmount", "billdate", "dueDate", "userName", ...}]}
        """
        path = self._get_path("view_bill")  # /recharge/v3/retailerViewbill
        extra = dict(extra_params) if extra_params else {}
        cir_raw = extra.pop("cir", None)
        if cir_raw is None or (isinstance(cir_raw, str) and not cir_raw.strip()):
            cir_raw = extra.pop("circle", None)
        cir_val = str(cir_raw).strip() if cir_raw not in (None, "") else ""
        op_val = self._op_int(operator_id)
        op_str = str(op_val) if op_val is not None else operator_id
        ad_params = extra if isinstance(extra, dict) else {}
        # Field order per doc: cn, op, cir (always present; empty when no circle), adParams
        payload = {"cn": customer_id, "op": op_str, "cir": cir_val, "adParams": ad_params}
        return self._request("POST", path, json_data=payload, action="view_bill", log_context=log_context)

    def recharge(
        self,
        operator_id: str,
        customer_id: str,
        amount: str,
        ref_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Recharge/Payment API – POST /recharge/v3/retailerPayment.
        Payload per Postman UAT: cn, op, cir, amt, reqid, remitterName, customerMobile,
        paymentRefID, paymentMode, agentId, paymentAccountInfo (all optional except cn, op, amt, reqid).
        """
        path = self._get_path("recharge")
        extra = extra_params or {}
        op_val = self._op_int(operator_id)
        payment_account_info_raw = str(extra.get("paymentAccountInfo", "") or "").strip()
        payment_account_info_digits = "".join(ch for ch in payment_account_info_raw if ch.isdigit())
        # For FASTag/biller flows where Mobikwik expects local mobile/account, strip country code 91.
        if len(payment_account_info_digits) == 12 and payment_account_info_digits.startswith("91"):
            payment_account_info = payment_account_info_digits[2:]
        else:
            payment_account_info = payment_account_info_raw
        payload = {
            "cn": customer_id,
            "op": str(op_val) if op_val is not None else operator_id,
            "cir": extra.get("cir", ""),
            "amt": amount,
            "reqid": ref_id,
            "remitterName": extra.get("remitterName", ""),
            "customerMobile": extra.get("customerMobile", ""),
            "paymentRefID": extra.get("paymentRefID", ref_id),
            "paymentMode": extra.get("paymentMode", "Cash"),
            "agentId": extra.get("agentId") or self.agent_id or "",
            "paymentAccountInfo": payment_account_info,
        }
        # Allow extra_params to override any key
        for k, v in extra.items():
            if k not in payload and v is not None:
                payload[k] = v
        return self._request("POST", path, json_data=payload, action="recharge", log_context=log_context)

    def transaction_status(self, ref_id: str, log_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Transaction Status Check API – POST /recharge/v3/retailerStatus. Body: txId (reqid from Recharge) or refId."""
        path = self._get_path("transaction_status")
        # Postman UAT: body is { "txId": "<reqid from Recharge>" }; refId accepted as fallback
        body = {"txId": ref_id}
        return self._request("POST", path, json_data=body, action="transaction_status", log_context=log_context)

    # -------------------------------------------------------------------------
    # Legacy / compatibility (operators, fetch_bill, pay_bill, pay_status)
    # -------------------------------------------------------------------------

    def get_operators(self, category: Optional[str] = None, log_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get list of operators/billers (BBPS). Uses operators path or balance/validation params per API Kit."""
        path = self._get_path("operators")
        params = {}
        if category:
            params["category"] = category
        return self._request("GET", path, params=params, require_token=True, action="operators", log_context=log_context)

    def fetch_bill(
        self,
        operator_id: str,
        customer_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch bill – uses View Bill API (bill details); Validation is for prepaid only."""
        return self.view_bill(
            operator_id=operator_id,
            customer_id=customer_id,
            subscriber_id=subscriber_id,
            extra_params=extra_params,
            log_context=log_context,
        )

    def pay_bill(
        self,
        operator_id: str,
        customer_id: str,
        amount: str,
        ref_id: str,
        subscriber_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        log_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pay bill – uses Recharge API (new)."""
        return self.recharge(
            operator_id=operator_id,
            customer_id=customer_id,
            amount=amount,
            ref_id=ref_id,
            subscriber_id=subscriber_id,
            extra_params=extra_params,
            log_context=log_context,
        )

    def pay_status(self, ref_id: str, log_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Check payment status – uses Transaction Status Check API (new)."""
        return self.transaction_status(ref_id=ref_id, log_context=log_context)
