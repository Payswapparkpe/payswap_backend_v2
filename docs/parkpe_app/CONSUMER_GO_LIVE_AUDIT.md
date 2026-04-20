# ParkPe consumer system — go-live audit deliverable

Generated from codebase analysis (`frontend/projects/parkpe`) plus Angular production compile check (2026-04-19). This document implements the **Screen_ID matrix**, **nav graph**, **control inventory** (shell + major patterns), **API/variable mapping**, **E2E flow status**, and **P0–P3 gap list**.

**Build status:** `npx ng build parkpe --configuration=development` — **pass** (warnings: optional chaining in `payment-receipt.component.ts` template only).

---

## 1. Authoritative screen matrix (Screen_ID × route × layout)

| Screen_ID | Full path (pattern) | Component (src path) | Parent layout | Guards / notes |
|-----------|---------------------|----------------------|---------------|------------------|
| SCR-001 | `/` → `/home` | `features/home/home.component` | none | `homeEntryGuard`; authed → `getPostLoginRoute()` |
| SCR-002 | `/connect/scan/:qrCode` | `features/connect/connect-scan-result/connect-scan-result.component` | none | Public |
| SCR-003 | `/auth/login` | `features/auth/login/login.component` | none | `guestGuard` |
| SCR-004 | `/auth/register` | `features/auth/register/register.component` | none | `guestGuard` |
| SCR-005 | `/auth/forgot-password` | `features/auth/forgot-password/forgot-password.component` | none | `guestGuard` |
| SCR-006 | `/fleet/login` | `login.component` (reuse) | none | `guestGuard` |
| SCR-007 | `/unlock` | `features/security/session-lock/session-lock.component` | none | `authGuard` |
| SCR-008 | `/dashboard` | `features/dashboard/dashboard.component` | `AppLayoutComponent` | `authGuard`, `sessionLockGuard` |
| SCR-009 | `/fleet/interest` | `features/fleet/fleet-interest.component` | AppLayout | Not `isFleetWorkspace` nav (shell treats as consumer) |
| SCR-010 | `/settings` | `features/settings/settings.component` | AppLayout | |
| SCR-011 | `/notifications` | `features/notifications/notification-inbox.component` | AppLayout | |
| SCR-012 | `/profile/view` | `features/profile/profile-view/profile-view.component` | AppLayout | |
| SCR-013 | `/profile/edit` | `features/profile/profile-edit/profile-edit.component` | AppLayout | |
| SCR-014 | `/connect` → `/connect/vehicles` | redirect | | |
| SCR-015 | `/connect/info` | `connect-landing/connect-landing.component` | AppLayout | |
| SCR-016 | `/connect/scan` | `connect-scan/connect-scan.component` | AppLayout | |
| SCR-017 | `/connect/chats` | `connect-chats-shell` | AppLayout | |
| SCR-018 | `/connect/chats/:threadId` | `connect-thread-chat/connect-thread-chat.component` | AppLayout | child outlet |
| SCR-019 | `/connect/vehicles` | `connect-vehicles-shell` | AppLayout | list + outlet |
| SCR-020 | `/connect/vehicles/add` | `connect-vehicle-form` | AppLayout | child |
| SCR-021 | `/connect/vehicles/:id/edit` | `connect-vehicle-form` | AppLayout | child |
| SCR-022 | `/connect/vehicles/:id` | `connect-vehicle-detail` | AppLayout | child |
| SCR-023 | `/connect/app` | `connect-app-embed` | AppLayout | |
| SCR-024 | `/parking/list` | `parking-list` | AppLayout | |
| SCR-025 | `/parking/slot/:locationId` | `parking-slot-select` | AppLayout | |
| SCR-026 | `/parking/booking/:slotId` | `parking-booking` | AppLayout | |
| SCR-027 | `/parking/detail/:bookingId` | `parking-detail` | AppLayout | |
| SCR-028 | `/bbps` | `bbps-internal/bbps-internal.component` | AppLayout | Single-page funnel |
| SCR-029 | `/fastag`, `/fastag/recharge` | `fastag-form` | AppLayout | |
| SCR-030 | `/fastag/confirm` | `fastag-confirm` | AppLayout | |
| SCR-031 | `/challan` | `challan-shell` | AppLayout | search + outlet |
| SCR-032 | `/challan/detail/:id` | `challan-detail` | AppLayout | child |
| SCR-033 | `/challan/pay/:id` | `challan-pay` | AppLayout | child |
| SCR-034 | `/vouchers` | `vouchers-page` | AppLayout | |
| SCR-035 | `/vouchers/list`, `/vouchers/list/:id` | `voucher-list-detail` | AppLayout | |
| SCR-036 | `/vouchers/:id` | `voucher-detail` | AppLayout | |
| SCR-037 | `/payment` → `/payment/history` | redirect | | |
| SCR-038 | `/payment/checkout` | `payment-page` | AppLayout | |
| SCR-039 | `/payment/status` | `payment-status` | AppLayout | |
| SCR-040 | `/payment/callback/:gateway` | `payment-callback` | AppLayout | return from PG |
| SCR-041 | `/payment/receipt/:transactionId`, `/payment/invoice/:transactionId` | `payment-receipt` | AppLayout | |
| SCR-042 | `/payment/history` | `payment-history-shell` (+ nested receipt) | AppLayout | |
| SCR-043 | `/payment/reports`, `/payment/reports/payments` | `reports-shell` + `payment-report` | AppLayout | |
| SCR-044 | `/payment/reports/voucher-statement` | `voucher-statement` | AppLayout | |

**Fleet (boundary only, not consumer-depth):** `fleet/control-center`, `fleet/vehicles`, `fleet/drivers`, `fleet/trips`, `fleet/compliance` — all `fleetAuthGuard`.

---

## 2. Navigation graph (primary inbound / outbound)

### 2.1 App shell ([`app-layout.component.html`](frontend/projects/parkpe/src/app/layouts/app-layout/app-layout.component.html))

| Control | Action | Outbound |
|---------|--------|----------|
| Brand / “Dashboard” icon | `routerLink` | `shellHomePath` → `/dashboard` (consumer) or `/fleet/control-center` (fleet) |
| Nav track (`navItems`) | `routerLink` | Each `item.path` (consumer: parking, bbps, vouchers, fastag, challan, payment/history, payment/reports, connect) |
| Consumer → Fleet | `goFleetWorkspace()` | `/fleet/control-center` if `isFleetUser()` else `/fleet/interest` |
| Fleet → Consumer | `goIndividualHome()` | `/dashboard` |
| Notifications | `openNotifications()` | `/notifications` (disabled in fleet shell — handler returns early) |
| Account menu | Profile | `/profile/view` |
| | Settings | `/settings` |
| | Lock | `sessionLock.lock('manual')` → expect `/unlock` |
| | Logout | `auth.logout()` |
| Drawer | Same links + Settings + Notifications (consumer) | |

**Unread badge:** `getNotificationUnreadCount()` — errors clear badge to 0 (silent).

### 2.2 Programmatic `Router.navigate` (consumer-relevant)

| Source file | Navigates to |
|-------------|--------------|
| `home.component.ts` | `/auth/login`, `/auth/register` |
| `login.component.ts` | `returnUrl` query or `getPostLoginRoute()` |
| `register.component.ts` | `/dashboard` |
| `session-lock.component.ts` | `returnUrl` after unlock |
| `connect-scan.component.ts` | `/connect/scan/:code` |
| `connect-vehicle-form.component.ts` | `/connect/vehicles`, `/connect/vehicles/:id` |
| `connect-vehicle-detail.component.ts` | `/connect/vehicles`, `/connect/chats/:threadId` |
| `bbps-internal.component.ts` | `/payment/status` (+ query/state) |
| `fastag-form` | `/fastag/confirm` |
| `fastag-confirm` | `/dashboard` |
| `challan-detail` | `/challan/pay/:id` |
| `challan-pay` | `/payment/status?status=success` |
| `parking-list` | `/parking/slot/:locationId` |
| `parking-slot-select` | `/parking/booking/:id`, `/parking/list` |
| `parking-booking` | `/parking/detail/:bookingId` |
| `payment-page`, `payment-callback`, vouchers | `/payment/status` |
| `payment-status` | `/payment/receipt/:orderRef`, `/vouchers` |
| `notification-inbox` | `navigateByUrl(deepLink)` |
| `profile-edit` | `/profile/view` |

### 2.3 Orphan / stale route references (resolved)

Previously unused BBPS step components and `challan-search` referenced obsolete paths; **those files were removed** — single-screen [`bbps-internal`](frontend/projects/parkpe/src/app/features/bbps/bbps-internal/) and [`challan-shell`](frontend/projects/parkpe/src/app/features/challan/challan-shell/) remain authoritative.

---

## 3. State / API mapping (high-signal)

### 3.1 [`MobilityStateStore`](frontend/projects/parkpe/src/app/core/stores/mobility-state.store.ts)

| Signal / key | Persists | Writers | Consumers |
|--------------|----------|---------|-----------|
| `dashboardSummary` | localStorage | Dashboard after `getDashboardSummary` | Dashboard overview |
| `connectVehicles` | localStorage | Dashboard `loadConnectVehicles`, Connect flows | Dashboard cards, refresh |
| `connectVehicleListRevision` | no | `notifyConnectVehicleListChanged` | Vehicle list refresh |
| `paymentStatusSnapshot` | localStorage | Payment flows | Recovery / status messaging |
| `connectQrSnapshot` | localStorage | Connect QR flows | |

**Consistency risk:** Snapshot can be **stale** vs server; dashboard refetches vehicles on load but summary may lag until API returns.

### 3.2 `RealApiService` — methods used by consumer flows (non-fleet)

Auth & profile: `login`, `fleetLogin`, `requestLoginOtp`, `verifyLoginOtp`, `register*`, `forgotPassword`, `getProfile`, `updateProfile`, `logout`, PIN/passkey/security methods.

Payments & vouchers: `getGateways`, `createOrder`, `verifyPayment`, `getVouchers`, `getVoucherDetail`, `revealVoucherPin`, `claimVoucher`, `getTransaction`, `getDashboardSummary`.

BBPS: `getCategories`, `getOperators`, `fetchBill`, `payBill`, `payCart`, favorites + saved bills CRUD.

Parking: `getLocations`, `getSlots`, `createBooking`, `getBooking`.

FASTag / challan: `createRechargeOrder`, `searchChallans`, `getChallan`.

Notifications: `getNotificationBanners`, `getNotificationFeed`, `getNotificationUnreadCount`, `markNotificationRead`, `registerPushToken`.

**Connect** uses **parallel `ConnectService` + `HttpClient`** to `/api/.../connect/...` (vehicles, QR, scanner OTP, chat, calls) — not duplicated in `RealApiService` for those paths.

### 3.3 Dashboard (`DashboardComponent`)

| State / variable | Source |
|------------------|--------|
| `summary` | `MobilityStateStore` + `getDashboardSummary()` |
| `connectVehicles` | store + `ConnectService.getVehicles()` |
| `recentTransactions` | API transactions |
| `spendingChartData` | trends API |
| `showBillingAddressBanner` | `auth.userSignal().billingAddressComplete === false` |
| `quickActions` | static routes incl. `comingSoon` |
| `overviewTilesComingSoon` | static flags |

---

## 4. Control coverage methodology (per screen)

For each **Screen_ID** row in §1:

1. Open component `.html` — enumerate `routerLink`, `(click)`, `submit`, `(ngSubmit)`.
2. Map loading/error branches (`@if`, `[disabled]`).
3. Match `.ts` handlers to §3 API tables.

**Shell:** Fully enumerated in §2.1.

**Deep components:** Largest bundles (lazy chunks): `home`, `connect-vehicle-detail`, `bbps-internal`, `dashboard`, `settings`, `connect-thread-chat` — prioritize manual QA time here.

---

## 5. E2E flow catalog — verification status

| Flow_ID | Steps | Static review | Runtime staging |
|---------|-------|---------------|-------------------|
| F-01 | `/home` → register → `/dashboard` | OK — `register` navigates to dashboard | Run on staging |
| F-02 | `/home` → login → `getPostLoginRoute()` (`/dashboard` or `/fleet/control-center`) | OK | Run |
| F-03 | Logout clears session | `auth.logout()` — verify implementation | Run |
| F-04 | Session lock `/unlock` → return URL | `session-lock.component` uses `returnUrl` | Run |
| F-05 | Dashboard quick actions + nav `comingSoon` | Flags present — **must QA** tap behavior on Parking/FASTag/Challan | Run |
| F-06 | Connect vehicle CRUD + chats | Routes + `ConnectService` mapped | Run |
| F-07 | Public `/connect/scan/:qrCode` | Public component + scanner APIs | Run |
| F-08 | BBPS internal → pay → `/payment/status` | `bbps-internal` navigates | Run + PG sandbox |
| F-09 | Vouchers → checkout → callback → receipt | Wired via payment stack | Run + sandbox |
| F-10 | History → receipt; reports tabs | Routes OK | Run |
| F-11 | Profile/settings; billing banner clears | Banner ↔ settings | Run |
| F-12 | Notifications deep link | `navigateByUrl(deepLink)` — **validate URL allowlist server-side** | Run |
| F-13 | Parking / FASTag / Challan linear | Stub/real APIs in `RealApiService` | Run |

**Note:** Runtime column requires your **staging URL**, **credentials**, and **payment sandbox**; not executed in CI here.

---

## 6. Fleet boundary checklist (light)

| Check | Expected |
|-------|----------|
| Consumer shell `navItems` | Consumer paths when URL not under `/fleet` (except `/fleet/interest`) |
| `goFleetWorkspace` | Fleet users → control center; others → interest |
| Notifications | Hidden/zero in fleet workspace |
| Post-login route | `isFleetUser` → `/fleet/control-center` |

---

## 7. Gap register (P0–P3)

| ID | Sev | Area | Finding | Owning layer |
|----|-----|------|---------|--------------|
| G-01 | ~~P3~~ | BBPS | Orphan BBPS step components removed (`bbps-category-select`, `bbps-operator-select`, `bbps-bill-fetch`, `bbps-pay`) — `bbps-internal` remains the only route | Done |
| G-02 | ~~P3~~ | Challan | Unused `challan-search.component.ts` removed (search lives in `challan-shell`) | Done |
| G-03 | P2 | UX | Nav + dashboard mark Parking, FASTag, Challan `comingSoon` — must match real feature flags to avoid “dead premium” feel | Product + FE |
| G-04 | P2 | Data | `getVehicleConnectNotificationCount` uses optional `connect_unread_count` on vehicle — may always be 0 until API populates | API + FE |
| G-05 | P2 | Notifications | Deep links passed to `navigateByUrl` — risk if backend sends arbitrary URLs | API contract + FE validate |
| G-06 | ~~P3~~ | Build | `payment-receipt` customer fields — optional chain removed per `Transaction` typing | Done |
| G-07 | P3 | Marketing | `/home` ecosystem may link external Connect URL vs in-app `/connect` — consistency | Content |

**P0/P1:** None identified from **static analysis only**. Re-run after staging E2E (payment capture, webhook, session expiry, BBPS biller failures).

---

## 8. Exit criteria (plan)

- [x] Screen matrix (§1) covers all `app.routes` + feature lazy routes.
- [x] Nav graph documents shell + programmatic routes + orphan references.
- [x] API/store mapping for core consumer paths.
- [x] P0–P3 register with owners.
- [ ] Staging E2E executed (owner: QA) — fill §5 runtime column.

---

## 9. References (code)

- Routes: [`app.routes.ts`](frontend/projects/parkpe/src/app/app.routes.ts)
- Shell: [`app-layout.component.ts`](frontend/projects/parkpe/src/app/layouts/app-layout/app-layout.component.ts)
- API surface: [`real-api.service.ts`](frontend/projects/parkpe/src/app/core/api/real-api.service.ts)
- Connect HTTP: [`connect.service.ts`](frontend/projects/parkpe/src/app/features/connect/services/connect.service.ts)

---

## 10. Implemented fixes (engineering follow-up)

| Change | Purpose |
|--------|---------|
| `MobilityStateStore.sessionResumedTick` + `notifySessionResumed()` | Tab visibility → dashboards refetch instead of trusting only localStorage snapshots |
| `AppLayoutComponent` `@HostListener('document:visibilitychange')` | Calls `notifySessionResumed()` when tab visible |
| `DashboardComponent` `effect()` on `sessionResumedTick` | Reloads summary, transactions, trends, vehicles, billing banner after resume |
| `notification-inbox.component` | User-visible feedback when `deepLink` is empty, external `http(s)`, or invalid |
| `payment-receipt` template | NG8107 warnings addressed (`customer` is required on `Transaction`) |
| Deleted unused BBPS/Challan components | Removes dead routes / confusion (see G-01, G-02) |
