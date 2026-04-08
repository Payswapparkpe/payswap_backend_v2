# Payswap / ParkPe — project status

Internal handoff and **ClickUp-style** reference. High level only—not a full product or API spec. **Do not** commit secrets; configure credentials via `.env` locally.

---

## 1. Payswap Django backend

Paths: `portal/`, `api/`, `core/`.

### Completed

- **VoucherX bulk issuance → ParkPe user link by mobile** — For ParkPe brand rows with a `mobile_number` column, bulk task resolves a unique `Profile` by normalized phone and sets `metadata.parkpe_user_id` on create. See [`portal/tasks/voucher_tasks.py`](../portal/tasks/voucher_tasks.py).
- **ParkPe API: claim voucher** — `POST /api/voucher/vouchers/claim` (JWT): voucher code + PIN, PIN verification, transactional update of `parkpe_user_id`, audit logging. See [`api/parkpe_api/views.py`](../api/parkpe_api/views.py), [`api/parkpe_api/voucher_urls.py`](../api/parkpe_api/voucher_urls.py).
- **ParkPe API: list/detail enrichment** — Responses include `parkpeLinked` and `linkedUserPhone` where applicable. Same views module as above.
- **Tests** — Claim flow and mobile resolver helpers: [`api/tests/test_parkpe_voucher_claim.py`](../api/tests/test_parkpe_voucher_claim.py).
- **Portal: voucher detail — mapped user** — Shows mapped user mobile or “Not mapped” on voucher view. [`portal/views/legacy.py`](../portal/views/legacy.py) (VoucherDetailView context), [`portal/templates/portal/vouchers/vouchers/detail.html`](../portal/templates/portal/vouchers/vouchers/detail.html).
- **Portal: users** — Dashboard-style list (tabs, search, date range, badges, actions); **edit** and **delete** routes/views; soft deactivate; **permanent delete** for super-admin role. [`portal/views/user_views.py`](../portal/views/user_views.py), [`portal/urls.py`](../portal/urls.py), templates under `portal/templates/portal/users/` (`list.html`, `edit.html`, `delete.html`).
- **Email: default SMTP TLS** — [`portal/mail_backends.py`](../portal/mail_backends.py) (`PayswapSMTPBackend` uses certifi CA for STARTTLS); [`core/settings.py`](../core/settings.py) sets `EMAIL_BACKEND` to that backend.
- **Email provider** — Brevo removed from config narrative; default SMTP is Microsoft 365–style (`smtp.office365.com`, TLS). Settings in [`core/config.py`](../core/config.py); values only in `.env` (not documented here).

### Backlog / blocked

- **Microsoft 365 SMTP authentication** — If sending still fails with `535`, fix tenant/mailbox: SMTP AUTH enabled, correct password or **app password** (MFA), security policies.
- **Optional** — Send mail via **Microsoft Graph** + OAuth if basic SMTP is disallowed long term.
- **CI** — Keep GitHub frontend/backend jobs green; align env secrets with docs.
- **Security** — Rotate any credentials that were exposed; keep `.env` out of VCS.
- **Voucher codebase** — Follow-up audit: dead code removal and docs.

---

## 2. ParkPe Angular

Path: [`frontend-space/projects/parkpe`](../frontend-space/projects/parkpe).

### Completed

- **Vouchers** — Buy/list/detail; **link existing voucher** (code + PIN) wired to backend + mock; list/detail show linked mobile / not linked. Feature code under `src/app/features/voucher/`; API in `src/app/core/api/`, models in `src/app/core/models/voucher.model.ts`.
- **App scope (summary)** — Auth (login/register/forgot), dashboard, Connect (vehicles, QR), parking, BBPS, FASTag, payment flows and reports, settings, session lock/unlock, home. Lazy routes and guards as in `app.routes.ts`.

### Backlog

- E2E / QA against real API for voucher claim and list.
- Copy and i18n polish for voucher linking and errors.
- Optional product analytics on claim success and list loads.

---

## 3. Payswap Angular

Path: [`frontend-space/projects/payswap`](../frontend-space/projects/payswap).

### Completed

- **Landing / shell** — Minimal app: e.g. `/` → landing; see `app.routes.ts`. Shared pieces (toast, services) as present in repo.

### Backlog

- Expand beyond landing if the Payswap hub roadmap requires dashboards or internal tools.
- Align with `api/v1` (runtime-config, control tower) if those UIs are in scope.
- CI: stable `ng build` for the `payswap` project.

---

## Appendix — ClickUp-style one-liners

Copy into lists; prefix with your own status tags (`[DONE]`, `[TODO]`, `[BLOCKED]`).

**Payswap Django — done**

- `[DONE]` VoucherX bulk ParkPe auto-link by mobile (`parkpe_user_id` in metadata)
- `[DONE]` API `POST /api/voucher/vouchers/claim` with PIN + row lock
- `[DONE]` API voucher list/detail `parkpeLinked` + `linkedUserPhone`
- `[DONE]` Tests `test_parkpe_voucher_claim.py`
- `[DONE]` Portal voucher detail mapped user mobile / Not mapped
- `[DONE]` Portal users dashboard + edit/delete + permanent delete (super admin)
- `[DONE]` `PayswapSMTPBackend` + `EMAIL_BACKEND`
- `[DONE]` Default Microsoft 365 SMTP env pattern (no Brevo in config story)

**Payswap Django — backlog**

- `[TODO]` Fix Microsoft 365 SMTP 535 (SMTP AUTH / app password / policy)
- `[TODO]` Optional: Graph API mail if SMTP blocked
- `[TODO]` CI stabilize GitHub jobs
- `[TODO]` Voucher audit cleanup + docs
- `[TODO]` Rotate leaked vendor/SMTP credentials if any

**ParkPe Angular — done**

- `[DONE]` Voucher claim UI + real/mock API
- `[DONE]` Linked phone on voucher list/detail
- `[DONE]` Core app features (auth, dashboard, connect, parking, BBPS, FASTag, payment, settings, session lock)

**ParkPe Angular — backlog**

- `[TODO]` QA E2E voucher flows
- `[TODO]` Copy/i18n for voucher linking

**Payswap Angular — done**

- `[DONE]` Landing + minimal shell

**Payswap Angular — backlog**

- `[TODO]` Hub UI beyond landing
- `[TODO]` CI `ng build payswap`
