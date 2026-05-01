# Credential Rotation Runbook

## Scope
- Application secrets in `.env` and deployment secret stores.
- API keys, signing keys, OAuth client secrets, SMTP credentials, and S3 keys.
- Seeded local credentials created by `python manage.py seed_data`.

## Immediate Actions
- Rotate any credential previously shared in code, screenshots, logs, or chat.
- Invalidate older keys after new keys are confirmed live.
- Re-deploy backend/frontend services with the new secret set.

## Local Seeding Safety
- `seed_data` now avoids hardcoded passwords.
- Use `SEED_DEFAULT_PASSWORD` for deterministic local testing only.
- Optionally provide role-specific values like `SEED_PASSWORD_ADMIN`.
- Never use seeded credentials outside local/dev environments.

## CI Secret Scanning
- CI already runs Gitleaks in `.github/workflows/ci.yml`.
- Keep the secrets job mandatory on `main` and `develop` pull requests.

## Verification Checklist
- Login and critical API paths work with rotated credentials.
- Old credentials fail authentication.
- Sentry/notifications continue to report after rotation.
- Audit trail updated with rotation timestamp and owner.
