# API Management aur Partner Assignment – Plan

Yeh plan batata hai ki **integrated APIs ko kaise manage karein**, **API Explorer par kaise test karein**, aur **partners ko kaunsi APIs deni hain**.

---

## 1. Overview: Kya kya integrate hai?

| Service | Vendor(s) | Use case |
|--------|-----------|----------|
| **BBPS** (Bill Pay) | Euronet, Mobikwik | Operators, fetch bill, pay bill, status |
| **AEPS** | PayPoint | Balance, withdrawal, mini statement, agent, 2FA |
| **DMT** | PayPoint DMT | Register sender, add beneficiary, remit, status |
| **KYC / Verification** | Cashfree, Instantpay | PAN, Aadhaar, Bank, DL, GST, Face, etc. |
| **SMS / OTP** | Kaleyra | Send SMS, OTP send/verify |
| **Payment** | Cashfree PG | Create order, status, refund |
| **E-Sign** | Leegality | Document e-sign (agar use ho) |

Har vendor ke andar **multiple APIs** hote hain (e.g. PayPoint: balance_enquiry, cash_withdrawal, add_agent). In sabko **manage**, **test**, aur **partners ko assign** karna hai.

---

## 2. APIs ko manage kaise karein?

### 2.1 Vendor aur API list ready karna

- **Command:**  
  `python manage.py seed_vendor_apis`  
- **Kya karta hai:**  
  - `ApiVendor` records banata/update karta (PayPoint, Euronet, Mobikwik, Cashfree, Kaleyra, etc.)  
  - Har vendor ke liye `VendorApi` entries (api_code, name, purpose)  
- **Kab chalana hai:**  
  - Naya environment setup  
  - Naya vendor add karne par (pehle `seed_vendor_apis` me vendor + APIs add karo, phir command chalao)

### 2.2 Vendor status aur partner mapping dekhna

- **Screen:** **Vendor Management Dashboard**  
- **URL:** `/admin/partners/vendors/dashboard/`  
- **Kya dikhega:**  
  - Saare vendors, unke API count, kitne partners assigned  
  - **Partner–Vendor matrix:** kis partner ko kis service ke liye kaunsa vendor (BBPS, AEPS, DMT, KYC, SMS, Payment)  
- **Use:**  
  - Ye screen par saari integrated APIs (vendor-wise) manage hone ka overview milta hai  
  - Kaunse partner ko kaunsi vendor/API mil rahi hai, yahi se verify karo

### 2.3 Naya vendor / API add karna (future)

- **Vendor:** `portal/management/commands/seed_vendor_apis.py` me `VENDORS` aur `VENDOR_APIS` me entry add karo, phir `seed_vendor_apis` chalao  
- **Handler:** Agar API call koi custom code se ho rahi ho to `portal/services/execution_engine.py` / `handler_registry` me handler register karna hoga  
- **API Explorer:** Vendor/API seed hone ke baad automatically API Explorer me sidebar me aa jayega (view vendor list + APIs DB se leta hai)

---

## 3. API Explorer par APIs ko test kaise karein?

### 3.1 API Explorer kahan hai?

- **URL:** `/api-explorer/`  
- **Access:** Login (admin/super) ke baad  
- **Tabs:**  
  - **Our APIs** – Portal APIs (v1/v2) + Vendors (category-wise)  
  - **Postman** – Postman sync  
  - **Vendor Testing** – Same as Our APIs, lekin focus “vendor APIs test” par

### 3.2 Test karne ke do modes

| Mode | Kab use karein | Kya hota hai |
|------|-----------------|---------------|
| **Admin** | Apne system credentials se sab kuch try karna | Koi partner context nahi; direct vendor API try hoti hai (system credentials) |
| **Partner simulation** | Partner ke nazariye se dekhna ki unko kya dikhega / chalega | Partner select karo → us partner ke **assigned vendors** ke hisaab se hi test hota hai; agar partner ko wo vendor assigned nahi hai to error aayega |

### 3.3 Step‑by‑step: API Explorer se test

1. **Login** karo (admin/super).  
2. **API Explorer** kholo: `/api-explorer/`.  
3. **Tab choose karo:**  
   - **Our APIs** ya **Vendor Testing** – left side par **Portal APIs** + **Vendors** (BBPS, AEPS, DMT, KYC, SMS, Payment, etc.) list hoga.  
4. **Vendor expand karo** (e.g. Euronet, PayPoint) → uske andar **APIs** list (e.g. Get Operators, Fetch Bill, Pay Bill).  
5. **Koi API select karo** → URL aur body auto-set ho jayenge (e.g. `/services/api-vendors/euronet/apis/fetch_bill/try/`).  
6. **Testing mode choose karo:**  
   - **Admin** – bina partner ke test (system level).  
   - **Partner simulation** – dropdown se **Partner** select karo; request us partner ke vendor assignment ke hisaab se validate hogi.  
7. **Body (JSON)** me zarurat ho to payload bharo.  
   - Partner simulation me `testing_mode` aur `partner_id` auto add ho jate hain (Explorer khud karta hai).  
8. **Send** dabao → response right side par dikhega.  
9. Agar partner simulation me **vendor not assigned** ho to 403 / clear message aayega – matlab partner ko wo API/vendor nahi di gayi.

### 3.4 Kya verify karna hai test se?

- **Admin mode:**  
  - Har important vendor API (BBPS fetch/pay, AEPS balance, DMT remit, KYC verify, SMS send, Payment create) ek baar run karke response check karo.  
- **Partner simulation:**  
  - 2–3 partners ke liye alag‑alag vendors assign karke (next section) phir Explorer me unhi partners ko select karke test karo – sirf assigned vendors wale APIs success honi chahiye.

---

## 4. Partners ko kaunsi API deni hai?

Concept: **Partner ko “API” direct nahi dete; partner ko **service + vendor** dete ho.**  
- Service = BBPS, AEPS, DMT, KYC, SMS, Payment  
- Vendor = us service ke liye kaunsa provider (e.g. BBPS → Euronet ya Mobikwik).  
Partner ko jo vendor assign hota hai, usi ke through saari related APIs use hoti hain (e.g. Euronet assign hai to fetch_bill, pay_bill, operators sab Euronet se).

### 4.1 Naya partner onboard karte waqt

- **URL:** `/admin/partners/onboard/`  
- **Form me:**  
  - Company details, contact, address  
  - **Vendor assignments (optional):**  
    - Har service (BBPS, AEPS, DMT, KYC, SMS, Payment) ke liye:  
      - Kaun‑kaunse **vendors** allow karne hain (checkboxes)  
      - Kaun **primary** hoga (dropdown)  
- **Save:** Partner create hota hai + vendor assignments save ho jati hain.  
- **Result:** Is partner ke liye ab wahi vendors/APIs allow honge jo aapne assign kiye.

### 4.2 Existing partner ko vendors change karna

- **URL:** `/admin/partners/<partner_id>/vendors/`  
- **Screen:** “Vendor Assignment” – partner name/code upar dikhega.  
- **Har service ke liye (BBPS, AEPS, DMT, KYC, SMS, Payment):**  
  - Checkboxes: kaun‑kaunse vendors **allow** karne  
  - Primary: dropdown se **primary vendor** select  
- **Save Assignments** → ab partner ko sirf yahi vendors (aur unki APIs) use karne denge.

### 4.3 Default vendors (agar assign na kiya ho)

- **Command:**  
  `python manage.py assign_default_vendors`  
- **Kya karta hai:**  
  - Jin partners ke paas kisi service ke liye koi assignment nahi hai, unhe default vendor assign ho jata hai (e.g. BBPS → Mobikwik, AEPS/DMT → PayPoint, KYC → Cashfree, SMS → Kaleyra, Payment → Cashfree PG).  
- **Kab use karein:**  
  - Purane partners jo pehle “vendor assignment” se nahi the, unhe ek baar default set karne ke liye.

### 4.4 Partner ko “kaunsi API” di – summary

| Aap kya decide karte ho | Partner ko kya milta hai |
|-------------------------|---------------------------|
| Service = BBPS, Primary vendor = Euronet | Partner BBPS ki saari APIs **Euronet** se use karega (operators, fetch_bill, pay_bill, status) |
| Service = BBPS, Primary = Mobikwik | Partner BBPS **Mobikwik** se use karega |
| Service = AEPS, Primary = PayPoint | AEPS ki saari APIs (balance, withdrawal, agent, etc.) **PayPoint** se |
| Multiple vendors allow (e.g. BBPS me Euronet + Mobikwik) | Primary wala default; baaki ko aap future me primary bana sakte ho ya API me `vendor` param se use karwa sakte ho (agar support ho) |

---

## 5. End‑to‑end workflow (short)

1. **Setup:**  
   `seed_vendor_apis` chalao → vendors + APIs DB me aa jaye.  
2. **Manage / overview:**  
   `/admin/partners/vendors/dashboard/` se dekh lo kaunse vendors/APIs active hain, kaunse partners ko kya assigned hai.  
3. **Test:**  
   - `/api-explorer/` → Our APIs / Vendor Testing  
   - Pehle **Admin** mode me important APIs test karo (BBPS, AEPS, DMT, KYC, SMS, Payment).  
   - Phir **Partner simulation** me 1–2 partners select karke test karo taaki assigned vendor/API sahi kaam kare.  
4. **Partners ko API dena:**  
   - **Naya partner:** `/admin/partners/onboard/` → form me vendor assignments bharo.  
   - **Purana partner:** `/admin/partners/<id>/vendors/` → service‑wise vendors + primary set karo.  
5. **Defaults (optional):**  
   Jinke paas assignment nahi hai unke liye `assign_default_vendors` chala do.

---

## 6. Quick reference – URLs

| Kaam | URL |
|------|-----|
| API Explorer (test) | `/api-explorer/` |
| Vendor Management Dashboard | `/admin/partners/vendors/dashboard/` |
| Partner list | `/admin/partners/list/` |
| Partner detail | `/admin/partners/<partner_id>/` |
| Partner vendor assignment | `/admin/partners/<partner_id>/vendors/` |
| Onboard new partner | `/admin/partners/onboard/` |

---

## 7. Commands summary

| Command | Kab use karein |
|---------|-----------------|
| `python manage.py seed_vendor_apis` | Vendors + Vendor APIs DB me create/update karna |
| `python manage.py assign_default_vendors` | Un partners ko default vendors dena jinke paas assignment nahi |
| `python manage.py create_internal_api_keys` | Payswap/Parkpe jaise internal apps ke liye API keys (optional; internal apps ke liye) |

Is plan ko follow karke aap integrated APIs ko manage kar sakte ho, API Explorer par sahi se test kar sakte ho, aur decide kar sakte ho ki partners ko kaunsi API (service + vendor) deni hai.
