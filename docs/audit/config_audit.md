# Phase 0 Audit — Step 9: Config & Feature Flags Audit

**Read-only audit. No code changes.**

---

## 1. Settings overview (core/settings.py)

Key config sources: `core.config.payswap_config` (Pydantic from .env) and `os.environ` for a few governance/sampling vars.

| Area | Key variables |
|------|----------------|
| App | AUTH_USER_MODEL, SECRET_KEY, DEBUG, V2_PLACEHOLDER_MODE, ALLOWED_HOSTS, RUNNING_TESTS |
| DB | DATABASES (from payswap_config.get_database_config()) |
| Cache | CACHES (Redis from payswap_config.get_redis_config()), GOV_KILL_SWITCH_CACHE_KEY |
| Celery | CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TIMEZONE, CELERY_TASK_*, CELERY_WORKER_POOL |
| Email | EMAIL_*, DEFAULT_FROM_EMAIL (from payswap_config) |
| CORS | CORS_ALLOW_ALL_ORIGINS (DEBUG), CORS_ALLOWED_ORIGINS, CORS_ALLOW_CREDENTIALS, CORS_ALLOW_HEADERS |
| Logging | LOGGING (file handlers: app, finance, security, audit, email, error), LOG_LEVEL from config |
| API | API_LOG_SAMPLE_RATE, API_GOVERNANCE_ENFORCE, API_GOVERNANCE_KILL_SWITCH, API_GOVERNANCE_BALANCE_CHECK_ENABLED, API_GOVERNANCE_MIN_BALANCE |
| REST/JWT | REST_FRAMEWORK, SIMPLE_JWT, throttle rates (anon, user, connect_*, auth_*) |
| Middleware | RequestID, APILogging, APIRegistryEnforce, APIKeyIPWhitelist, APIKeyUsageLogging, ProfileCompletion, MFARequired, SessionLock |

---

## 2. Env vars: .env.example vs usage

.env.example documents many vars. core/config.py (PayswapConfig) defines the canonical set used by the app; extra keys in .env are ignored (extra="ignore").

**Documented in .env.example and used in config/settings:**  
APP_NAME, APP_ENV, DEBUG, SECRET_KEY, ALLOWED_HOSTS, TIMEZONE, DATABASE_URL, REDIS_URL, CELERY_*, ENCRYPTION_KEY, SIGNING_SECRET, JWT_*, KALEYRA_*, SMTP_*, CASHFREE_*, MOBIKWIK_*, EURONET_*, PAYPOINT_*, AWS S3, LOG_LEVEL, PAYSWAP_LOG_*, SENTRY_*, TRUSTED_PROXY_IPS, CORS_*, PARKPE SMTP, PARKPE_VOUCHER_BRAND_ID, DATA_GOV_IN_*, INSTANTPAY_*, LEGALITY_*, EXPLORER_DEFAULT_*.

**Set in settings.py from os.environ (not in PayswapConfig):**  
API_LOG_SAMPLE_RATE, API_GOVERNANCE_ENFORCE, API_GOVERNANCE_KILL_SWITCH, API_GOVERNANCE_BALANCE_CHECK_ENABLED, API_GOVERNANCE_MIN_BALANCE. These are not listed in .env.example but are documented in comments in settings.py.

**Possible gap:** .env.example does not list API_LOG_SAMPLE_RATE or API_GOVERNANCE_*; operators might not know to set them.

---

## 3. Feature flags: list and usage

**Model:** api_management.FeatureFlag (code, description, enabled_by_default), api_management.FeatureFlagOverride (scope_type, scope_id, feature_flag, enabled, rollout_pct).

**Resolution:** api_management/feature_flags.py — is_feature_enabled(code, partner, app_name, user), is_feature_enabled_for_request(request, code). Precedence: user override > partner override > app override > default.

**Where flags are read in code:**  
- api_management/middleware.py (API governance): is_feature_enabled_for_request(request, "api_access"). When False, returns 503 for that request (per-partner/per-app/per-user kill).

**Governance UI/API:**  
- api/governance/views_control.py — ControlFeatureFlagsView lists and patches FeatureFlag/FeatureFlagOverride.  
- portal/views/governance/settings.py — feature_flags list for Django governance settings page.

**Flag codes in code:** Only "api_access" is passed to is_feature_enabled_for_request. Any other flag codes (e.g. created in admin or via API) are not checked in application code unless added elsewhere; they are “defined” but effectively unused for behavior.

---

## 4. Findings: unused, duplicate, dead

- **Unused / dead config:**  
  - No vars in settings or config were found that are never read; PayswapConfig uses the vars it defines.  
  - V2_PLACEHOLDER_MODE is read in settings (SIMPLE_JWT not directly; JWT_* from config). Used in code for v2 placeholder behavior — not dead.

- **Feature flags:**  
  - Only "api_access" is used in code (middleware). Other flags created in DB/admin have no effect unless code is added to check them. So: one “live” flag; others may be “unused” or reserved for future use.  
  - No duplicate semantics (e.g. two flags for the same thing) observed.

- **Duplicate semantics:**  
  - Kill switch: GOV_KILL_SWITCH_CACHE_KEY (Redis) is toggled by Governance and Super Admin; API_GOVERNANCE_KILL_SWITCH in env is a separate, env-based kill (settings: “when True, all /api/ return 503”). Two mechanisms: (1) Redis key (UI-toggled), (2) env var. Not duplicate flags but two ways to achieve “kill API” — doc should clarify both.

- **.env.example vs env:**  
  - API_LOG_SAMPLE_RATE and API_GOVERNANCE_* are not in .env.example; worth adding so production/staging can set them without reading settings.py.

---

*End of Step 9 — Config Audit.*
