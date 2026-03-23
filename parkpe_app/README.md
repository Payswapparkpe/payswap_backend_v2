# ParkPe Flutter App

iOS and Android app for ParkPe – Smart Parking & Payments (Connect, BBPS, FASTag, Challan, Vouchers, Payments). Same backend API as the ParkPe Angular app; Forest Green theme, dark mode, multi-language support.

## Requirements

- Flutter SDK (3.10+)
- Xcode (iOS) / Android Studio or SDK (Android)
- Backend running at `API_BASE_URL` (see below)

## Setup

1. **Clone and enter project**
   ```bash
   cd parkpe_app
   ```

2. **Configure API URL**
   - Copy `.env` and set `API_BASE_URL` to your backend (e.g. `http://localhost:8000/api` or `https://api.yourdomain.com/api`).
   - For Android emulator use `http://10.0.2.2:8000/api` to point to host machine.

3. **Install dependencies**
   ```bash
   flutter pub get
   ```

## Run

- **iOS simulator:** `flutter run` (select iOS device)
- **Android emulator:** `flutter run` (select Android device)
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

Uses the same Django API as the ParkPe Angular app: `/api/auth/*`, `/api/dashboard/*`, `/api/connect/*`, `/api/bbps/*`, `/api/payment/*`, `/api/voucher/*`. Send `X-App: parkpe` and `Authorization: Bearer <token>` where required.
