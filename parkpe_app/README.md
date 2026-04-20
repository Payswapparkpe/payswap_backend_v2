# ParkPe Flutter App

iOS and Android app for ParkPe – Smart Parking & Payments (Connect, BBPS, FASTag, Challan, Vouchers, Payments). Same backend API as the ParkPe Angular app; Forest Green theme, dark mode, multi-language support.

## CI

Repository root GitHub Actions runs **`flutter pub get`**, **`flutter analyze --no-fatal-infos --no-fatal-warnings`**, and **`flutter test`** in `parkpe_app/` on pushes/PRs to `main` / `develop`.

See also: [docs/parkpe_app/MVP_SPRINTS.md](../docs/parkpe_app/MVP_SPRINTS.md), [docs/parkpe_app/FCM_AND_DEEP_LINKS.md](../docs/parkpe_app/FCM_AND_DEEP_LINKS.md).

## Requirements

- Flutter SDK (3.10+)
- Xcode (iOS) / Android Studio or SDK (Android)
- Backend running at `API_BASE_URL` (see below)

**Fonts:** Poppins is bundled under `fonts/` (see `pubspec.yaml`). The app does **not** download fonts from the network at runtime, so macOS sandbox / offline runs work without `fonts.gstatic.com` errors.

## Setup

1. **Clone and enter project**
   ```bash
   cd parkpe_app
   ```
   If your shell prompt already shows `parkpe_app`, you are in this folder — do not run `cd parkpe_app` again.

2. **Configure API URL**
   - Copy `.env.example` to `.env` and set `API_BASE_URL` to your backend. Use a **trailing slash** (e.g. `http://localhost:8000/api/`) — the app also normalizes this, so paths like `auth/otp/request` resolve to `/api/auth/...` and not `/apiauth/...`.
   - **macOS / iOS simulator:** `http://localhost:8000/api/`
   - **Android emulator:** `http://10.0.2.2:8000/api/`
   - **Physical device (same Wi‑Fi as your dev machine):** `http://<your-lan-ip>:8000/api/`

3. **Install dependencies**
   ```bash
   flutter pub get
   ```

## Run

From the repository root you can use **`make parkpe-app`** (see root `Makefile`). Override device: **`make parkpe-app DEVICE=macos`** or **`DEVICE=chrome`**.

- **iOS simulator:** `flutter run` (select iOS device)
- **Android emulator:** `flutter run` (select Android device)
- **macOS (desktop):** `flutter run -d macOS` works for UI checks; Android/iOS are the supported targets for release. **`Failed to foreground app; open returned 1`** is a harmless macOS quirk — the app still builds; focus the Dock icon if the window stays behind other apps.
- **Release (Android):** `flutter build apk --release`
- **Release (iOS):** `flutter build ios --release` (then open `ios/Runner.xcworkspace` in Xcode and archive)

## Features

- **Auth:** Login (email/phone + password), Register (OTP), Forgot password
- **Dashboard:** Summary cards, quick actions (Bills, Vouchers, Connect, Payments, FASTag, Challan)
- **BBPS:** Category → Operator → Consumer ID → Fetch bill → Pay (PG flow)
- **Connect:** Vehicles list, add vehicle, vehicle detail with QR, scan QR (camera)
- **Payments:** Transaction history
- **Vouchers:** List, detail, reveal PIN
- **FASTag / Challan:** UI in place; backend “coming soon” message until APIs are available
- **Profile:** View profile, logout
- **Settings:** Theme (Light / Dark / System), Language (10 languages), Notifications placeholder

## Project structure

- `lib/core/` – theme, env, router, constants, settings providers
- `lib/data/` – API client, repositories, models
- `lib/features/` – auth, dashboard, bbps, connect, payment, voucher, fastag, challan, profile, settings

## Backend

Uses the same Django API as the ParkPe Angular app: `/api/auth/*`, `/api/dashboard/*`, `/api/connect/*`, `/api/bbps/*`, `/api/payment/*`, `/api/voucher/*`.

HTTP client ([`lib/data/api/api_client.dart`](lib/data/api/api_client.dart)): default headers include **`X-App: parkpe`** and **`Authorization: Bearer <token>`** after login; **401** triggers refresh via `POST .../v1/auth/token/refresh/` (SimpleJWT), same as web.

Repositories obtain a shared [`ApiClient`](lib/core/providers/api_providers.dart) from **`apiClientProvider`** (Riverpod).
