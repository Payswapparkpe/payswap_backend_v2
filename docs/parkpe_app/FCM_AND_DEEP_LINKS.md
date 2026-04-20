# FCM, यूनिवर्सल लिंक्स, डिवाइस टोकन — डिज़ाइन (`parkpe_app`)

## लक्ष्य

- **Push:** ट्रांज़ैक्शन, Connect चैट, चालान/FASTag अलर्ट
- **Deep links:** वेब URL जैसे Connect स्कैन (`/connect/scan/:qrCode`) ऐप में खोलें
- **डिवाइस रजिस्ट्रेशन:** बैकएंड को FCM/APNs टोकन भेजना

## क्लाइंट (Flutter)

| टॉपिक | पैकेज / काम |
|--------|-------------|
| FCM | `firebase_core` + `firebase_messaging` (या समान) |
| लोकल नोटिफिकेशन | `flutter_local_notifications` (फोरग्राउंड डिस्प्ले) |
| यूनिवर्सल लिंक्स | `app_links` — Android App Links + iOS Associated Domains |
| सुरक्षित स्टोरेज | मौजूदा `flutter_secure_storage` पैटर्न के साथ |

**डीप लिंक मैपिंग (उदाहरण):**

- `https://<domain>/connect/scan/<qrCode>` → `GoRouter` पर `/connect/scan-result?code=`
- पेमेंट कॉलबैक URL → मौजूदा WebView/PG फ्लो के साथ

## बैकएंड (Django) — अभी / आगे

- वर्तमान में समर्पित `DeviceRegistration` मॉडल रिपो में स्पष्ट नहीं है; उत्पादन से पहले जोड़ें:
  - फ़ील्ड: `user`, `fcm_token` / `apns_token`, `platform` (`ios` \| `android`), `app_version`, `updated_at`
  - एंडपॉइंट: `POST /api/.../devices/register` (JWT), idempotent अपडेट
- `notification_orchestrator` में मोबाइल चैनल — FCM HTTP v1 सर्विस अकाउंट

## सुरक्षा

- टोकन रोटेशन लॉगआउट पर इनवैलिडेट
- डीप लिंक में PII न डालें; QR कोड पहले से पब्लिक लुकअप से वैलिडेट करें

---

CI में FCM शामिल नहीं — लोकल `google-services.json` / `GoogleService-Info.plist` सीक्रेट्स के रूप में रखें।
