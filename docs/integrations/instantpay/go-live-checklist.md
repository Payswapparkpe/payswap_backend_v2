# Instantpay Go-Live Checklist

Use this checklist before enabling Instantpay modules in production.

## Credentials & Access

- [ ] `INSTANTPAY_CLIENT_ID` configured in production secret store.
- [ ] `INSTANTPAY_CLIENT_SECRET` configured in production secret store.
- [ ] `INSTANTPAY_ENCRYPTION_KEY` configured and validated.
- [ ] `INSTANTPAY_ENVIRONMENT=PRODUCTION` set for prod.
- [ ] Outbound IP whitelist shared and confirmed with Instantpay.

## Security

- [ ] Secrets masked in logs and error responses.
- [ ] PII fields masked in debug logs.
- [ ] Request signatures and timestamps validated.
- [ ] Replay protection via idempotency keys enabled.

## API Readiness

- [ ] All target endpoints enabled in `/api/v2/urls.py`.
- [ ] API key permission matrix updated for all `service.action` keys.
- [ ] Partner-to-vendor assignment tested for Instantpay flows.
- [ ] Transaction status endpoint returns deterministic state.

## Functional QA

- [ ] AEPS withdraw / balance / statement tested in sandbox.
- [ ] DMT + domestic + nepal remittance tested.
- [ ] Credit card bill payment tested.
- [ ] RC verify + challan lookup tested.
- [ ] DigiLocker init + status tested.
- [ ] BIN lookup tested.
- [ ] Credit report + score simulator tested.
- [ ] Merchant onboarding tested.

## Reconciliation & Support

- [ ] Transaction records persisted with partner and vendor references.
- [ ] Failed calls include normalized error codes.
- [ ] Reconciliation reports match Instantpay dashboard.
- [ ] Runbook created for support/escalation.

## Post Go-Live

- [ ] Dashboard/alerts configured for Instantpay failure rates and latency.
- [ ] Daily reconciliation job scheduled.
- [ ] Rollback/kill-switch validated.
