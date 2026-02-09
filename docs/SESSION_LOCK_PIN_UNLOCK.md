# Session Lock & PIN Unlock (Backend)

**PIN is a secondary unlock mechanism, not a replacement for OTP/2FA.**

- **Primary authentication:** OTP / 2FA (full sign-in).
- **Session:** 5-minute inactivity timeout (Django session).
- **After expiry:** User is soft-locked; they can re-enter the dashboard by entering a **user-defined 4-digit PIN** without repeating OTP/2FA, provided they have set a PIN and are within the allowed window.

## Security principles

- OTP/2FA is the **only** way to perform a full login. PIN cannot be used for first login.
- PIN is **hashed** (Django `make_password` / `check_password`); never stored or logged in plaintext.
- PIN attempts are **rate-limited**: after 5 failed attempts, PIN unlock is blocked for 30 minutes; only OTP/2FA login is allowed during that period.
- PIN unlock is **time-bound**: allowed only within a window (e.g. 24 hours) from the last full OTP/2FA login (`last_full_auth_at`).

## Audit logging (file only)

PIN-related events are logged to **logs/audit.log** (logger `portal.audit`). Logged events: PIN set, PIN unlock success, PIN unlock failure, PIN lockout triggered, forced OTP re-authentication. **Never logged:** PIN, PIN hash, OTP, or any secrets.

## Endpoints

- **POST /auth/set-pin/** – Set 4-digit PIN (user must be fully authenticated via OTP/2FA).
- **GET/POST /auth/unlock-with-pin/** – Re-unlock with PIN after session expiry (identity from signed `lock_identity` cookie).

## Flow summary

1. User signs in with OTP/2FA → session created, `last_full_auth_at` set, `lock_identity` cookie set.
2. After 5 minutes of inactivity, session expires.
3. On next request to a protected path, middleware redirects to `/auth/unlock-with-pin/` if the user has a valid lock cookie, a PIN set, and is not locked / within window.
4. Correct PIN → new session, dashboard access. Wrong PIN 5 times → PIN locked for 30 minutes; user must sign in again with OTP/2FA.
