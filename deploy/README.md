# Deploy

Deployment-related files for Payswap.

## Contents

- **systemd/** – Systemd unit files for Celery worker and beat. See `systemd/README.md` for usage.

## Quick reference

- Run migrations and collectstatic on the server before starting services.
- Use `.env` (or env vars) for all secrets; never commit production `.env`.
