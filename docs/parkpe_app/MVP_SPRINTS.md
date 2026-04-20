# ParkPe Flutter (`parkpe_app`) — MVP स्प्रिंट ब्रेकडाउन

वेब पैरिटी मास्टर प्लान की **फेज़ 1** को निम्न स्प्रिंट में बाँटें (टीम वेलोसिटी के अनुसार समायोजित करें)।

## Sprint 0 — इन्फ्रा (पहले से आंशिक)

- [x] `parkpe_app` रिपो रूट, `flutter analyze` / `flutter test` CI (`.github/workflows/ci.yml` में `flutter` जॉब)
- [x] एकल `ApiClient` (`apiClientProvider`) + JWT refresh + `X-App: parkpe`
- `.env.example` + लोकल `API_BASE_URL`

## Sprint 1 — Auth + शेल

- लॉगिन / रजिस्टर / फॉरगॉट पैरिटी बैकएंड (`auth/*`)
- स्प्लैश / ऑनबोर्डिंग / `MainShell` टैब नेव स्टेबल
- ऐप रीस्टार्ट पर `restoreSession` + राउटर रीडायरेक्ट

## Sprint 2 — Home + Activity

- डैशबोर्ड समरी API (`/api/dashboard/*`) व वेब के समान KPI
- पेमेंट हिस्ट्री (`payment/history`) पूरी लिस्ट + पेजिंग
- नोटिफिकेशन इनबॉक्स (`/notifications` या समकक्ष API)

## Sprint 3 — Pay हब

- चेकआउट → स्टेटस → रसीद फ्लो (`payment/checkout`, `status`, `receipt`)
- BBPS एक फ्लो (`bbps/*`, `X-App` हेडर)
- FASTag + चालान स्क्रीन को लाइव API से जोड़ना (जहाँ बैकएंड तैयार)

## Sprint 4 — Connect

- वाहन CRUD, QR डिस्प्ले, कैमरा स्कैन (`connect/*`)
- चैट थ्रेड लिस्ट + मैसेज पोलिंग (वेब के अनुरूप)
- डीप लिंक स्कैन रिज़ल्ट (`FCM_AND_DEEP_LINKS.md`)

## Sprint 5 — Polish

- सेशन लॉक / बायोमेट्रिक (वेब `/unlock` पैरिटी)
- रिपोर्ट्स (`payment/reports/*`) अगर MVP में शामिल
- पुश नोटिफिकेशन (FCM) पहला कट

---

**नोट:** `app ui/` फ़ोल्डर रिपो में अलग डेमो है — ParkPe MVP इसमें न लिखें।
