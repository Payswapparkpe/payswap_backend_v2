# FCM, डीप लिंक, डिवाइस टोकन — रनबुक (`parkpe_app`)

## लक्ष्य

- **Push:** Connect chat + campaign notifications मोबाइल तक पहुंचें
- **Deep links:** push payload से app route खुले
- **डिवाइस रजिस्ट्रेशन:** login के बाद token backend में auto-upsert हो

## क्लाइंट (Flutter) — implemented

| टॉपिक | पैकेज / काम |
|--------|-------------|
| FCM bootstrap | `firebase_core` + `firebase_messaging` |
| Token registration | `POST /api/dashboard/notifications/push-token` (`token`, `devicePlatform`, `appPlatform`) |
| Token refresh | `onTokenRefresh` पर backend update |
| Deep link open | `onMessageOpenedApp` + `getInitialMessage` |

**डीप लिंक मैपिंग (current):**

- `/connect/chats/<id>` → app `/connect` tab खोलता है
- अन्य `/...` route → same route पर `GoRouter.go()`

## बैकएंड (Django) — implemented

- `DevicePushToken` model पहले से उपयोग में है (idempotent update by token)
- `NotificationOrchestrator` push channel अब FCM HTTP v1 call करता है
- `connect_chat_notifications` push now sends FCM + delivery log
- invalid/unregistered token मिलने पर token `is_active=False` mark

## Firebase / Apple console checklist

1. Firebase project में Android + iOS app add करें
2. Android के लिए `google-services.json` in `parkpe_app/android/app/`
3. iOS के लिए `GoogleService-Info.plist` in `parkpe_app/ios/Runner/`
4. Apple Developer में APNs Auth Key (`.p8`) बनाकर Firebase iOS app settings में upload करें
5. Firebase service account JSON backend deployment secret में रखें (git में नहीं)

## Backend env checklist

- `NOTIFICATIONS_PUSH_ENABLED=true`
- `FCM_PROJECT_ID=<firebase-project-id>`
- `FCM_SERVICE_ACCOUNT_PATH=/secure/path/firebase-service-account.json`
  - या `FCM_SERVICE_ACCOUNT_JSON={...}`

## सुरक्षा

- service account JSON repo में commit न करें
- डीप लिंक/data payload में PII न डालें
- token failures (unregistered) पर inactive mark रखें, repeated retries avoid करें

---

CI में FCM credential files commit नहीं होंगी; runtime/device testing के लिए local files + deployment secrets use करें.
