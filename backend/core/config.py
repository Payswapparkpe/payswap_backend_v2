"""
Secure Environment Configuration using Pydantic Settings
File: core/config.py
"""

from pathlib import Path
from typing import Any, Literal, Optional, Tuple
from functools import lru_cache

from pydantic import Field, SecretStr, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Monorepo layout: repo_root/backend/core/config.py — .env usually stays at repo root.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_ROOT.parent


def _resolve_env_file() -> str | None:
    for path in (_REPO_ROOT / ".env", _BACKEND_ROOT / ".env"):
        if path.is_file():
            return str(path)
    return None


_settings_kwargs: dict[str, Any] = {
    "env_file_encoding": "utf-8",
    "case_sensitive": True,
    "extra": "ignore",
}
_env_file = _resolve_env_file()
if _env_file:
    _settings_kwargs["env_file"] = _env_file


class PayswapConfig(BaseSettings):
    """Secure application settings using Pydantic."""

    model_config = SettingsConfigDict(**_settings_kwargs)

    # ============================================================================
    # APPLICATION
    # ============================================================================
    APP_NAME: str = Field(default="Payswap Hub")
    APP_ENV: Literal["development", "staging", "production"] = Field(default="development")
    DEBUG: bool = Field(default=False)
    # When True, v2 payment/SMS status/delivery endpoints return explicit placeholder responses (BUG-005).
    V2_PLACEHOLDER_MODE: bool = Field(default=True, description="v2 payment/SMS return placeholder data; set False when real integrations are live")
    SECRET_KEY: SecretStr = Field(..., min_length=50)
    ALLOWED_HOSTS: str = Field(default="localhost,127.0.0.1")
    TIMEZONE: str = Field(default="Asia/Kolkata")

    # ============================================================================
    # DATABASE
    # ============================================================================
    DATABASE_URL: PostgresDsn = Field(...)

    # ============================================================================
    # REDIS
    # ============================================================================
    REDIS_URL: RedisDsn = Field(...)

    # ============================================================================
    # CELERY
    # ============================================================================
    CELERY_BROKER_URL: RedisDsn = Field(...)
    CELERY_RESULT_BACKEND: RedisDsn = Field(...)
    CELERY_TIMEZONE: str = Field(default="Asia/Kolkata")

    # ============================================================================
    # SECURITY
    # ============================================================================
    ENCRYPTION_KEY: SecretStr = Field(..., min_length=32)
    SIGNING_SECRET: SecretStr = Field(..., min_length=32)
    JWT_SIGNING_KEY: SecretStr = Field(..., min_length=32)
    JWT_ACCESS_TOKEN_LIFETIME: int = Field(
        default=900,
        description="Access token lifetime in seconds. 900 = 15 min; active users extend via refresh (ParkPe API).",
    )
    JWT_REFRESH_TOKEN_LIFETIME: int = Field(
        default=86400 * 7,
        description="Refresh token lifetime in seconds. 7 days so active users stay logged in.",
    )

    # ============================================================================
    # SMS - KALEYRA (India Region). Same gateway for Portal (MFA, signup) and ParkPe (auth, scanner OTP).
    # ============================================================================
    KALEYRA_API_KEY: SecretStr = Field(...)
    KALEYRA_SID: str = Field(...)
    # Sender ID/Header (DLT) – must match DLT registration, e.g. PYSWAP
    KALEYRA_HEADER_PAYSWAP: str = Field(default="PYSWAP")
    # OTP Template ID – DLT Reg_otp (see DLT/template-data.csv). Body in kaleyra.py must match exactly.
    KALEYRA_OTP_TEMPLATE_ID: str = Field(default="1007640321725099860")
    # Base URL: India only. Use api.in.kaleyra.io (no https://, no /v1 – code adds them).
    KALEYRA_BASE_URL: str = Field(default="api.in.kaleyra.io")
    # Optional: separate base URL for Kaleyra Voice (click-to-call). If set, used for voice API only.
    KALEYRA_VOICE_BASE_URL: Optional[str] = Field(default=None, description="Voice API base (e.g. api.in.kaleyra.io) if different from KALEYRA_BASE_URL")

    # ============================================================================
    # DOCUMENT VERIFICATION
    # ============================================================================
    CASHFREE_API_KEY: Optional[SecretStr] = Field(default=None)
    CASHFREE_API_SECRET: Optional[SecretStr] = Field(default=None)
    CASHFREE_PUBLIC_KEY: Optional[str] = Field(
        default=None,
        description="Cashfree public key (PEM format) for signature generation. Required if IP is not whitelisted."
    )
    CASHFREE_PUBLIC_KEY_PATH: Optional[str] = Field(
        default=None,
        description="Path to Cashfree public key file (alternative to CASHFREE_PUBLIC_KEY)"
    )
    CASHFREE_VERIFICATION_ENVIRONMENT: str = Field(
        default="PRODUCTION",
        description="SANDBOX or PRODUCTION for Cashfree Verification APIs (Vehicle RC, etc.). Independent of PG.",
    )
    # Optional: use these for Vehicle RC if set; else CASHFREE_API_KEY/SECRET (from Verification Suite dashboard)
    CASHFREE_VERIFICATION_API_KEY: Optional[SecretStr] = Field(default=None, description="Cashfree Verification API key (Vehicle RC). If not set, CASHFREE_API_KEY is used.")
    CASHFREE_VERIFICATION_API_SECRET: Optional[SecretStr] = Field(default=None, description="Cashfree Verification API secret. If not set, CASHFREE_API_SECRET is used.")
    INVINCIBLE_OCEAN_API_KEY: Optional[SecretStr] = Field(default=None)
    INVINCIBLE_OCEAN_API_SECRET: Optional[SecretStr] = Field(default=None)
    
    # ============================================================================
    # LEGALITY (Document Signing & Stamp Paper)
    # ============================================================================
    LEGALITY_AUTH_TOKEN: Optional[SecretStr] = Field(default=None)
    LEGALITY_PRIVATE_SALT: Optional[SecretStr] = Field(default=None)
    
    # ============================================================================
    # CASHFREE PAYMENT GATEWAY (PG)
    # ============================================================================
    CASHFREE_PG_CLIENT_ID: Optional[SecretStr] = Field(default=None)
    CASHFREE_PG_CLIENT_SECRET: Optional[SecretStr] = Field(default=None)
    CASHFREE_PG_PARTNER_KEY: Optional[SecretStr] = Field(default=None)
    CASHFREE_PG_CLIENT_SIGNATURE: Optional[SecretStr] = Field(default=None)
    CASHFREE_PG_PARTNER_MERCHANT_ID: Optional[str] = Field(default=None)
    CASHFREE_PG_ENVIRONMENT: str = Field(default='SANDBOX', description='SANDBOX or PRODUCTION')

    # (Razorpay PG removed; ParkPe uses Cashfree only.)

    # ============================================================================
    # MOBIKWIK BBPS (Bharat Bill Payment System) – New API (Token + Encrypted Payload)
    # UAT docs: Token Generation, Balance Check, Validation, View Bill, Recharge, Transaction Status
    # Request body (when required): encryptedSessionKey, encryptedPayload, keyVersion, iv
    # ============================================================================
    MOBIKWIK_BBPS_ENABLED: bool = Field(default=False, description='Enable Mobikwik BBPS integration')
    MOBIKWIK_BBPS_CLIENT_ID: Optional[str] = Field(default=None, description='Mobikwik BBPS Client ID (for Token API)')
    MOBIKWIK_BBPS_CLIENT_SECRET: Optional[SecretStr] = Field(default=None, description='Mobikwik BBPS Client Secret (for Token API)')
    MOBIKWIK_BBPS_MERCHANT_ID: Optional[str] = Field(default=None, description='Mobikwik BBPS Merchant ID')
    MOBIKWIK_BBPS_API_KEY: Optional[SecretStr] = Field(default=None, description='Mobikwik BBPS API Key (optional if using token)')
    MOBIKWIK_BBPS_SECRET_KEY: Optional[SecretStr] = Field(default=None, description='Mobikwik BBPS Secret Key (checksum)')
    MOBIKWIK_BBPS_BASE_URL: str = Field(
        default='https://alpha3.mobikwik.com',
        description='Mobikwik BBPS API base URL (UAT: alpha3.mobikwik.com; B2B production: rapi-b2b.mobikwik.com)'
    )
    MOBIKWIK_BBPS_ENVIRONMENT: str = Field(default='UAT', description='UAT or PRODUCTION')
    MOBIKWIK_BBPS_USE_ENCRYPTION: bool = Field(
        default=False,
        description='Use encrypted request body (encryptedSessionKey, encryptedPayload, keyVersion, iv)'
    )
    MOBIKWIK_BBPS_PLAIN_JSON_UAT: bool = Field(
        default=False,
        description='When True and UAT, force plain JSON (no encryption). Default False: use encryption when MOBIKWIK_BBPS_USE_ENCRYPTION=True per RT-Recharge doc.'
    )
    MOBIKWIK_BBPS_MEMBER_ID: Optional[str] = Field(
        default=None,
        description='Balance Check API: onboarded email (memberId). If set, Balance Check sends memberId instead of merchantId per Mobikwik doc.'
    )
    MOBIKWIK_BBPS_AGENT_ID: Optional[str] = Field(
        default=None,
        description='Validation & Recharge APIs: agentId (e.g. MK01MK01INB523643654). Required in UAT per Postman collection.'
    )
    MOBIKWIK_BBPS_PUBLIC_KEY: Optional[SecretStr] = Field(
        default=None,
        description='Mobikwik public key (PEM) for encrypting session key when MOBIKWIK_BBPS_USE_ENCRYPTION=True'
    )
    MOBIKWIK_BBPS_PUBLIC_KEY_PATH: Optional[str] = Field(
        default='Mobikwik/public_key.pem',
        description='Path to Mobikwik public key PEM (relative to backend BASE_DIR, or absolute). Gitignored folder Mobikwik/ — copy PEM from onboarding zip. Used if MOBIKWIK_BBPS_PUBLIC_KEY not set.'
    )
    MOBIKWIK_BBPS_KEY_VERSION: str = Field(default='1.0', description='Key version for encrypted payload (match Mobikwik README, e.g. 1.0)')
    MOBIKWIK_BBPS_TOKEN_PATH: Optional[str] = Field(
        default=None,
        description='Override token API path (e.g. /oauth/token or /v1/token). Set from Mobikwik RT-Recharge & Bill Payment API doc if token fails.'
    )
    MOBIKWIK_BBPS_TOKEN_USE_ENCRYPTION: bool = Field(
        default=False,
        description='When True, Token API POST body uses encryptedSessionKey/encryptedPayload (same as bill APIs). Default False: plain clientId/clientSecret JSON per Mobikwik UAT Postman (works for many rapi-b2b token calls).',
    )
    MOBIKWIK_BBPS_TOKEN_PLAIN_JSON: bool = Field(
        default=False,
        description='When True, never encrypt Token API body (overrides MOBIKWIK_BBPS_TOKEN_USE_ENCRYPTION). Use only if Mobikwik explicitly requires it.',
    )
    MOBIKWIK_BBPS_TOKEN_EXPIRY_TIMEZONE: str = Field(
        default='Asia/Kolkata',
        description='IANA timezone for naive Mobikwik token expiryTime (YYYY-MM-DD HH:mm:ss) from token API',
    )
    MOBIKWIK_BBPS_UAT_VERBOSE_LOG: bool = Field(
        default=False,
        description='When True, log full request/response (sanitized) and cURL template per API to LogEntry for UAT/onboarding. Off in production.'
    )
    MOBIKWIK_BBPS_LOG_SANITIZE: bool = Field(
        default=True,
        description='When False (UAT), log request/response with actual values (no masking of cn, refId, etc). Production me True rakhna.'
    )
    MOBIKWIK_BBPS_RETRY_ON_FAILURE: bool = Field(
        default=True,
        description='When True, retry once on timeout or 5xx after 2s delay. Both attempts logged when UAT_VERBOSE_LOG is on.'
    )
    MOBIKWIK_BBPS_REQUEST_TIMEOUT: float = Field(
        default=60.0,
        description='HTTP timeout in seconds for Mobikwik API calls (view_bill, recharge, etc). UAT can be slow; 60s recommended.'
    )

    # ============================================================================
    # EURONET BBPS (Bharat Connect / EFT APME) – Single endpoint EnService
    # UAT: https://epayuat.eftapme.com/ENServiceAES256/API/EnService
    # ============================================================================
    EURONET_BBPS_ENABLED: bool = Field(default=False, description='Enable Euronet BBPS integration')
    EURONET_BBPS_BASE_URL: str = Field(
        default='https://epayuat.eftapme.com/ENServiceAES256/API',
        description='Euronet EnService API base URL (UAT: epayuat.eftapme.com)'
    )
    EURONET_BBPS_MERCHANT_CODE: Optional[str] = Field(default=None, description='Euronet Merchant Code (e.g. PAY)')
    EURONET_BBPS_USERNAME: Optional[str] = Field(default=None, description='Euronet Username (e.g. PAY_01)')
    EURONET_BBPS_PASSWORD: Optional[SecretStr] = Field(default=None, description='Euronet User Pass')
    EURONET_BBPS_STORE_CODE: Optional[str] = Field(default=None, description='Euronet Store Code (e.g. PAY_01)')
    EURONET_BBPS_CHANNEL_CODE: str = Field(default='INT', description='Channel Code (e.g. INT for Internet Banking)')
    EURONET_BBPS_AGENT_ID: Optional[str] = Field(default=None, description='Euronet Agent id (e.g. EU01EU02000000000001)')
    EURONET_BBPS_SALT: Optional[str] = Field(default=None, description='Euronet Salt Value for hash')
    EURONET_BBPS_ENCRYPTION_KEY: Optional[SecretStr] = Field(default=None, description='Euronet Encryption key (from UAT details)')

    # ============================================================================
    # PAYPOINT AEPS (Aadhaar Enabled Payment System)
    # Docs: https://docs.paypointindia.co.in/api/paypoint-aeps-api/paypoint/overview
    # UserCode, Password, IdentificationCode must be encrypted via Encrypt API before each request.
    # ============================================================================
    PAYPOINT_AEPS_ENABLED: bool = Field(default=False, description='Enable PayPoint AEPS integration')
    PAYPOINT_AEPS_BASE_URL: str = Field(
        default='https://api.paypointindia.co.in',
        description='PayPoint AEPS API base URL (from PayPoint contract; IP whitelist required)'
    )
    PAYPOINT_AEPS_USER_CODE: Optional[str] = Field(default=None, description='PayPoint UserCode (encrypted via Encrypt API before use)')
    PAYPOINT_AEPS_PASSWORD: Optional[SecretStr] = Field(default=None, description='PayPoint Password (encrypted via Encrypt API before use)')
    PAYPOINT_AEPS_IDENTIFICATION_CODE: Optional[str] = Field(default=None, description='PayPoint IdentificationCode (encrypted via Encrypt API before use)')
    PAYPOINT_AEPS_KEY: Optional[SecretStr] = Field(default=None, description='PayPoint Key (provided by PayPoint; not encrypted)')
    PAYPOINT_AEPS_ENVIRONMENT: str = Field(default='UAT', description='UAT or PRODUCTION')

    # ============================================================================
    # PAYPOINT DMT (Domestic Money Transfer)
    # Docs: https://docs.paypointindia.co.in/api/paypoint-dmt-api/dmt-api/overview
    # Same Encrypt API as AEPS; UserCode, Password, IdentificationCode encrypted before each request.
    # ============================================================================
    PAYPOINT_DMT_ENABLED: bool = Field(default=False, description='Enable PayPoint DMT integration')
    PAYPOINT_DMT_BASE_URL: str = Field(
        default='https://api.paypointindia.co.in',
        description='PayPoint DMT API base URL (IP whitelist required)'
    )
    PAYPOINT_DMT_USER_CODE: Optional[str] = Field(default=None, description='PayPoint DMT UserCode (encrypted via Encrypt API before use)')
    PAYPOINT_DMT_PASSWORD: Optional[SecretStr] = Field(default=None, description='PayPoint DMT Password (encrypted via Encrypt API before use)')
    PAYPOINT_DMT_IDENTIFICATION_CODE: Optional[str] = Field(default=None, description='PayPoint DMT IdentificationCode (encrypted via Encrypt API before use)')
    PAYPOINT_DMT_KEY: Optional[SecretStr] = Field(default=None, description='PayPoint DMT Key (provided by PayPoint; not encrypted)')
    PAYPOINT_DMT_ENVIRONMENT: str = Field(default='UAT', description='UAT or PRODUCTION')

    # ============================================================================
    # EMAIL (Microsoft 365 / Outlook SMTP by default; smtp.office365.com:587 + TLS)
    # ============================================================================
    SMTP_HOST: str = Field(default="smtp.office365.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(...)
    SMTP_PASSWORD: SecretStr = Field(...)
    SMTP_USE_TLS: bool = Field(default=True)
    SMTP_DEFAULT_FROM: str = Field(default="no-reply@payswap.in")

    # ============================================================================
    # EMAIL SMTP Parkpe (optional – voucher emails; if unset, uses default SMTP above)
    # ============================================================================
    SMTP_HOST_Parkpe: Optional[str] = Field(default=None, description="Optional separate host for ParkPe voucher mail")
    SMTP_PORT_Parkpe: Optional[int] = Field(default=587)
    SMTP_USER_Parkpe: Optional[str] = Field(default=None)
    SMTP_PASSWORD_Parkpe: Optional[SecretStr] = Field(default=None)
    SMTP_USE_TLS_Parkpe: bool = Field(default=True)
    SMTP_DEFAULT_FROM_Parkpe: Optional[str] = Field(default=None)
    PARKPE_SMTP_SSL_VERIFY: bool = Field(default=True, description="Set false in dev if SSL verify fails (e.g. macOS)")
    PARKPE_VOUCHER_BRAND_ID: Optional[int] = Field(
        default=None,
        description="Gift Voucher Brand ID for ParkPe (VoucherX). When set, ParkPe buy-voucher uses this brand to issue vouchers.",
    )
    PARKPE_REQUIRE_BILLING_ADDRESS: bool = Field(
        default=False,
        description="When True, ParkPe blocks voucher PG create-order, BBPS pay, and Connect RC-view pay until profile billing address is complete.",
    )
    PARKPE_BACKEND_SECRET: Optional[SecretStr] = Field(
        default=None,
        description="Secret for Parkpe backend service-to-service auth (register order, webhook relay). Send as Authorization: Bearer <secret> or X-Parkpe-Backend-Key.",
    )
    # data.gov.in Pincode API (All India Pincode Directory) – for address lookup by pincode
    DATA_GOV_IN_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for data.gov.in (get from https://data.gov.in). Used for pincode-to-address lookup.",
    )
    DATA_GOV_IN_PINCODE_RESOURCE_URL: str = Field(
        default="https://api.data.gov.in/resource/5c2f62fe-5afa-4119-a499-fec9d604d5bd",
        description="data.gov.in resource URL for All India Pincode Directory.",
    )

    # ============================================================================
    # INSTANTPAY API
    # ============================================================================
    INSTANTPAY_CLIENT_ID: Optional[SecretStr] = Field(default=None, description="Instantpay API Client Id")
    INSTANTPAY_CLIENT_SECRET: Optional[SecretStr] = Field(default=None, description="Instantpay API Client Secret")
    INSTANTPAY_ENCRYPTION_KEY: Optional[SecretStr] = Field(default=None, description="Instantpay API Encryption Key")
    INSTANTPAY_AUTH_CODE: Optional[SecretStr] = Field(default=None, description="Instantpay X-Ipay-Auth-Code header value")
    INSTANTPAY_ENDPOINT_IP: Optional[str] = Field(default=None, description="Instantpay X-Ipay-Endpoint-Ip header value")
    INSTANTPAY_REPORT_BANK_PROFILE_ID: Optional[str] = Field(default="0", description="Instantpay reports bankProfileId")
    INSTANTPAY_REPORT_ACCOUNT_NUMBER: Optional[str] = Field(default=None, description="Instantpay reports accountNumber")
    INSTANTPAY_ENVIRONMENT: Literal["SANDBOX", "PRODUCTION"] = Field(
        default="SANDBOX", description="Instantpay environment: SANDBOX or PRODUCTION"
    )
    INSTANTPAY_BASE_URL: Optional[str] = Field(
        default=None,
        description="Instantpay API base URL (e.g. https://api.instantpay.in). Defaults by environment if not set.",
    )

    # ============================================================================
    # NOTIFICATIONS ORCHESTRATOR
    # ============================================================================
    NOTIFICATIONS_ENABLED: bool = Field(default=True, description="Master switch for unified notification center dispatch.")
    NOTIFICATIONS_PUSH_ENABLED: bool = Field(default=False, description="Enable real push provider dispatch (FCM/APNS).")
    NOTIFICATIONS_ROLLOUT_PERCENT: int = Field(default=100, description="Progressive rollout percentage (0-100).")
    NOTIFICATIONS_RATE_LIMIT_PER_USER: int = Field(default=50, description="Max non-failed notifications per user per hour.")

    # ============================================================================
    # AWS S3 (optional for local/dev; required when using S3 storage)
    # ============================================================================
    S3_ACCESS_KEY: Optional[SecretStr] = Field(default=None)
    S3_SECRET_KEY: Optional[SecretStr] = Field(default=None)
    S3_BUCKET: str = Field(default="payswap-documents")
    S3_REGION: str = Field(default="ap-south-1")
    S3_ENDPOINT_URL: Optional[str] = Field(default=None)

    # ============================================================================
    # LOGGING
    # ============================================================================
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    PAYSWAP_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="DEBUG")
    PAYSWAP_LOG_TEXT_FORMAT: bool = Field(default=False)
    PAYSWAP_LOG_ENABLE_API_CONTEXT: bool = Field(default=True)
    PAYSWAP_MASK_SHOW_START: int = Field(default=4)
    PAYSWAP_MASK_SHOW_END: int = Field(default=3)
    PAYSWAP_LOG_RETENTION_DAYS: int = Field(default=30)
    PAYSWAP_LOG_DIR: str = Field(default="logs")

    # ============================================================================
    # SENTRY
    # ============================================================================
    SENTRY_ENABLED: bool = Field(default=False)
    SENTRY_DSN: Optional[SecretStr] = Field(default=None)
    SENTRY_ENVIRONMENT: Optional[str] = Field(default=None)

    # ============================================================================
    # TRUSTED PROXY (VAPT-002/003)
    # ============================================================================
    # Comma-separated IPs or CIDRs of load balancer/WAF. When REMOTE_ADDR is in this list,
    # client IP is taken from X-Forwarded-For (leftmost). Otherwise X-Forwarded-For is ignored.
    TRUSTED_PROXY_IPS: str = Field(
        default="",
        description="Comma-separated trusted proxy IPs/CIDRs (e.g. 10.0.0.1,172.16.0.0/12)",
    )

    # ============================================================================
    # CORS
    # ============================================================================
    CORS_ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:4200,http://127.0.0.1:4200,http://localhost:4201,http://127.0.0.1:4201,http://localhost:4202,http://127.0.0.1:4202"
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True)

    # API Explorer: optional default API key to pre-fill header inputs (e.g. key you use for testing)
    EXPLORER_DEFAULT_API_KEY: Optional[str] = Field(default=None, description="Pre-fill API Key / Authorization in API Explorer")
    # API Explorer: optional extra headers (JSON) to auto-include on every request.
    # Example: {"X-Security-Key":"...","X-Client-Id":"..."}
    EXPLORER_DEFAULT_HEADERS: Optional[str] = Field(
        default=None,
        description="JSON object of extra headers to auto-include in API Explorer requests",
    )

    # ============================================================================
    # SOCIAL AUTHENTICATION (OAuth)
    # ============================================================================
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = Field(default=None)
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[SecretStr] = Field(default=None)
    FACEBOOK_OAUTH_APP_ID: Optional[str] = Field(default=None)
    FACEBOOK_OAUTH_APP_SECRET: Optional[SecretStr] = Field(default=None)
    APPLE_OAUTH_CLIENT_ID: Optional[str] = Field(default=None)
    APPLE_OAUTH_TEAM_ID: Optional[str] = Field(default=None)
    APPLE_OAUTH_KEY_ID: Optional[str] = Field(default=None)
    APPLE_OAUTH_PRIVATE_KEY: Optional[SecretStr] = Field(default=None)

    # ============================================================================
    # VALIDATORS
    # ============================================================================
    @model_validator(mode="after")
    def validate_debug_mode(self):
        """Validate DEBUG is False in production."""
        if self.APP_ENV == "production" and self.DEBUG:
            raise ValueError("DEBUG must be False in production")
        return self

    @model_validator(mode="after")
    def set_sentry_environment(self):
        if self.SENTRY_ENABLED and not self.SENTRY_ENVIRONMENT:
            self.SENTRY_ENVIRONMENT = self.APP_ENV
        return self

    # ============================================================================
    # PROPERTIES
    # ============================================================================
    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",")]

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",")]

    @property
    def trusted_proxy_ips_list(self) -> list[str]:
        """Trusted proxy IPs/CIDRs for client IP resolution (VAPT-002/003)."""
        if not self.TRUSTED_PROXY_IPS or not self.TRUSTED_PROXY_IPS.strip():
            return []
        return [ip.strip() for ip in self.TRUSTED_PROXY_IPS.split(",") if ip.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    # ============================================================================
    # SECURE ACCESSORS
    # ============================================================================
    def get_secret_key(self) -> str:
        return self.SECRET_KEY.get_secret_value()

    def get_encryption_key(self) -> str:
        return self.ENCRYPTION_KEY.get_secret_value()

    def get_signing_secret(self) -> str:
        return self.SIGNING_SECRET.get_secret_value()

    def get_jwt_signing_key(self) -> str:
        return self.JWT_SIGNING_KEY.get_secret_value()

    def get_smtp_password(self) -> str:
        return self.SMTP_PASSWORD.get_secret_value()

    def get_parkpe_smtp_password(self) -> str:
        """Parkpe SMTP password for voucher emails. Returns empty string if not configured."""
        if self.SMTP_PASSWORD_Parkpe is None:
            return ""
        return self.SMTP_PASSWORD_Parkpe.get_secret_value()

    def is_parkpe_smtp_configured(self) -> bool:
        """True if Parkpe SMTP is configured (host, user, password)."""
        return bool(
            self.SMTP_HOST_Parkpe
            and self.SMTP_USER_Parkpe
            and self.SMTP_PASSWORD_Parkpe
        )

    def get_kaleyra_api_key(self) -> str:
        return self.KALEYRA_API_KEY.get_secret_value()
    
    def get_cashfree_api_key(self) -> str:
        return self.CASHFREE_API_KEY.get_secret_value() if self.CASHFREE_API_KEY else ""
    
    def get_cashfree_api_secret(self) -> str:
        return self.CASHFREE_API_SECRET.get_secret_value() if self.CASHFREE_API_SECRET else ""
    
    def get_invincible_ocean_api_key(self) -> str:
        return self.INVINCIBLE_OCEAN_API_KEY.get_secret_value() if self.INVINCIBLE_OCEAN_API_KEY else ""
    
    def get_invincible_ocean_api_secret(self) -> str:
        return self.INVINCIBLE_OCEAN_API_SECRET.get_secret_value() if self.INVINCIBLE_OCEAN_API_SECRET else ""
    
    def get_leegality_auth_token(self) -> str:
        return self.LEGALITY_AUTH_TOKEN.get_secret_value() if self.LEGALITY_AUTH_TOKEN else ""
    
    def get_leegality_private_salt(self) -> str:
        return self.LEGALITY_PRIVATE_SALT.get_secret_value() if self.LEGALITY_PRIVATE_SALT else ""
    
    def get_cashfree_pg_client_id(self) -> str:
        return self.CASHFREE_PG_CLIENT_ID.get_secret_value() if self.CASHFREE_PG_CLIENT_ID else ""
    
    def get_cashfree_pg_client_secret(self) -> str:
        return self.CASHFREE_PG_CLIENT_SECRET.get_secret_value() if self.CASHFREE_PG_CLIENT_SECRET else ""
    
    def get_cashfree_pg_partner_key(self) -> str:
        return self.CASHFREE_PG_PARTNER_KEY.get_secret_value() if self.CASHFREE_PG_PARTNER_KEY else ""
    
    def get_cashfree_pg_client_signature(self) -> str:
        return self.CASHFREE_PG_CLIENT_SIGNATURE.get_secret_value() if self.CASHFREE_PG_CLIENT_SIGNATURE else ""

    def get_s3_access_key(self) -> str:
        return self.S3_ACCESS_KEY.get_secret_value() if self.S3_ACCESS_KEY else ""

    def get_s3_secret_key(self) -> str:
        return self.S3_SECRET_KEY.get_secret_value() if self.S3_SECRET_KEY else ""

    def get_sentry_dsn(self) -> str:
        return self.SENTRY_DSN.get_secret_value() if self.SENTRY_DSN else ""

    def get_instantpay_client_id(self) -> str:
        return self.INSTANTPAY_CLIENT_ID.get_secret_value() if self.INSTANTPAY_CLIENT_ID else ""

    def get_instantpay_client_secret(self) -> str:
        return self.INSTANTPAY_CLIENT_SECRET.get_secret_value() if self.INSTANTPAY_CLIENT_SECRET else ""

    def get_instantpay_encryption_key(self) -> str:
        return self.INSTANTPAY_ENCRYPTION_KEY.get_secret_value() if self.INSTANTPAY_ENCRYPTION_KEY else ""

    def get_instantpay_auth_code(self) -> str:
        return self.INSTANTPAY_AUTH_CODE.get_secret_value() if self.INSTANTPAY_AUTH_CODE else ""

    def get_instantpay_endpoint_ip(self) -> str:
        return self.INSTANTPAY_ENDPOINT_IP or ""

    def get_instantpay_report_bank_profile_id(self) -> str:
        return self.INSTANTPAY_REPORT_BANK_PROFILE_ID or "0"

    def get_instantpay_report_account_number(self) -> str:
        return self.INSTANTPAY_REPORT_ACCOUNT_NUMBER or ""

    def is_instantpay_configured(self) -> bool:
        return bool(
            self.INSTANTPAY_CLIENT_ID and self.INSTANTPAY_CLIENT_SECRET and self.INSTANTPAY_ENCRYPTION_KEY
        )

    # ============================================================================
    # CONFIG GENERATORS
    # ============================================================================
    def get_database_config(self) -> dict:
        """Generate Django database configuration."""
        import dj_database_url
        config = dj_database_url.parse(str(self.DATABASE_URL))
        
        # Phase 3.1: Add connection pooling for better performance
        config.setdefault('CONN_MAX_AGE', 600)  # 10 minutes connection pooling
        config.setdefault('OPTIONS', {})
        config['OPTIONS'].setdefault('connect_timeout', 10)
        # Add statement timeout (30 seconds) - only for PostgreSQL
        if 'postgresql' in str(self.DATABASE_URL).lower() or 'postgres' in str(self.DATABASE_URL).lower():
            config['OPTIONS'].setdefault('options', '-c statement_timeout=30000')
        
        return config

    def get_redis_config(self) -> dict:
        """Generate Redis cache configuration."""
        return {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": str(self.REDIS_URL),
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "CONNECTION_POOL_KWARGS": {"max_connections": 50},
                },
                "KEY_PREFIX": f"{self.APP_NAME.lower()}",
                "TIMEOUT": 300,
            }
        }

    def get_celery_config(self) -> dict:
        """Generate Celery configuration."""
        return {
            "broker_url": str(self.CELERY_BROKER_URL),
            "result_backend": str(self.CELERY_RESULT_BACKEND),
            "timezone": self.CELERY_TIMEZONE,
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
            "task_track_started": True,
            "task_time_limit": 1800,
            "task_soft_time_limit": 1500,
            "broker_connection_retry_on_startup": True,
        }

    def get_email_config(self) -> dict:
        """Generate email configuration."""
        return {
            "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_HOST": self.SMTP_HOST,
            "EMAIL_PORT": self.SMTP_PORT,
            "EMAIL_USE_TLS": self.SMTP_USE_TLS,
            "EMAIL_HOST_USER": self.SMTP_USER,
            "EMAIL_HOST_PASSWORD": self.get_smtp_password(),
            "DEFAULT_FROM_EMAIL": self.SMTP_DEFAULT_FROM,
        }

    def get_email_config_parkpe(self) -> dict:
        """Generate Parkpe email configuration for voucher system."""
        return {
            "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_HOST": self.SMTP_HOST_Parkpe or "",
            "EMAIL_PORT": self.SMTP_PORT_Parkpe or 587,
            "EMAIL_USE_TLS": self.SMTP_USE_TLS_Parkpe,
            "EMAIL_HOST_USER": self.SMTP_USER_Parkpe or "",
            "EMAIL_HOST_PASSWORD": self.get_parkpe_smtp_password(),
            "DEFAULT_FROM_EMAIL": self.SMTP_DEFAULT_FROM_Parkpe or (self.SMTP_USER_Parkpe or ""),
        }

    def get_s3_config(self) -> dict:
        """Generate S3 storage configuration."""
        config = {
            "AWS_ACCESS_KEY_ID": self.get_s3_access_key(),
            "AWS_SECRET_ACCESS_KEY": self.get_s3_secret_key(),
            "AWS_STORAGE_BUCKET_NAME": self.S3_BUCKET,
            "AWS_S3_REGION_NAME": self.S3_REGION,
            "AWS_S3_FILE_OVERWRITE": False,
            "AWS_DEFAULT_ACL": "private",
            "AWS_S3_SIGNATURE_VERSION": "s3v4",
        }
        if self.S3_ENDPOINT_URL:
            config["AWS_S3_ENDPOINT_URL"] = self.S3_ENDPOINT_URL
        return config


@lru_cache()
def get_settings() -> PayswapConfig:
    """Get cached settings instance."""
    return PayswapConfig()


# Convenience instance
payswap_config = get_settings()


def _secret_str_value(val: Any) -> Optional[str]:
    if val is None:
        return None
    if hasattr(val, "get_secret_value"):
        return val.get_secret_value()
    return str(val)


def get_cashfree_pg_credentials() -> Tuple[Optional[str], Optional[str]]:
    """Return (client_id, client_secret) for Cashfree PG from .env (single default account)."""
    cid = _secret_str_value(getattr(payswap_config, "CASHFREE_PG_CLIENT_ID", None))
    csec = _secret_str_value(getattr(payswap_config, "CASHFREE_PG_CLIENT_SECRET", None))
    return (cid, csec)


def get_parkpe_backend_secret() -> Optional[str]:
    """Return Parkpe backend secret for service-to-service auth (register order, webhook relay)."""
    return _secret_str_value(getattr(payswap_config, "PARKPE_BACKEND_SECRET", None))

