# ParkPe – Android Studio में Run करें

यह app **सिर्फ Android और iOS** के लिए है। Web / macOS support नहीं है।

---

## ⚠️ ज़रूरी: Device Select करें

अगर error आए: *"No macOS desktop project configured"* तो इसका मतलब **Run target "macOS"** चुना हुआ है।  
**पहले Android emulator select करें**, फिर Run करें।

---

## विधि A: Terminal से (सबसे आसान)

Android Studio में **View → Tool Windows → Terminal** खोलें, फिर:

```bash
cd /Users/sandeepsuda/Desktop/Projects/payswap/parkpe_app
flutter run -d android
```

यह सीधे Android emulator/device पर चलाएगा। पहले emulator start कर लें (नीचे देखें)।

---

## विधि B: Android Studio Run बटन से

### 1. Android Emulator चालू करें

- **Tools → Device Manager** (या बाएँ साइड Devices बटन)
- कोई emulator select करके **▶ Play** दबाएं
- Boot होने तक (30–60 सेकंड) इंतज़ार करें

### 2. Backend चलाएं (अलग Terminal में)

```bash
cd /Users/sandeepsuda/Desktop/Projects/payswap
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

### 3. Device चुनें और Run करें

- ऊपर की **toolbar** में Run बटन के बगल में **device dropdown** दिखेगा
- वहाँ से **Android emulator** चुनें (जैसे `sdk gphone64 arm64` या `Pixel 7 API 36`)
- **macOS** या **Chrome** न चुनें
- फिर **▶ Run** दबाएं

---

## .env (API URL)

- Android emulator: `API_BASE_URL=http://10.0.2.2:8000/api` (already set)
- Physical Android device (same Wi‑Fi): अपने Mac का IP use करें, जैसे `http://192.168.1.x:8000/api`
- iOS simulator: `http://localhost:8000/api`

## Supported Platforms

- ✅ Android
- ✅ iOS  
- ❌ Web (removed)
