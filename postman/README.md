# Payswap Postman Collection

Saari APIs ka ek hi collection – Portal (Admin) BBPS Test, API v2 (BBPS, KYC, Payments, SMS, AEPS, DMT, Vouchers), Euronet EnService (External UAT), Mobikwik BBPS (External UAT).

**Agar import ke baad "this collection is empty" dikhe:** Purani collection delete karein, phir ye file dubara Import karein (File → Import → Upload Files → `Payswap_API_Collection.postman_collection.json`).

## Postman mein kaise add karein (Import)

1. **Postman** open karein (local system pe jo installed hai).
2. **File → Import** (ya drag‑and‑drop zone).
3. **Upload** pe click karein aur ye file choose karein:
   ```
   postman/Payswap_API_Collection.postman_collection.json
   ```
   Ya is folder ko drag‑and‑drop karein.
4. **Import** dabayein – collection left sidebar mein "Payswap - All APIs" ke naam se aa jayega.

## Collection variables set karein

Collection open karein → **Variables** tab:

| Variable        | Initial Value           | Use |
|-----------------|-------------------------|-----|
| `base_url`      | `http://localhost:8000` | Portal / API v2 base URL |
| `service_id`    | `1`                     | BBPS service id (DB se; agar alag hai to change karein) |
| `vendor_euronet`  | `euronet`             | Euronet vendor param |
| `vendor_mobikwik` | `mobikwik`            | Mobikwik vendor param |
| `api_key`       | (blank / apna key)      | API v2 ke liye Api-Key header |
| `csrftoken`     | (blank)                 | Portal login ke baad cookie se copy karke set karein |

## Folders (APIs)

- **Portal - Auth** – Login (session ke liye); Portal requests ke pehle run karein, cookies enable rakhein.
- **Portal - BBPS Test (Euronet)** – 1 Balance, 2 Get Billers, 3 Operators, 4 Fetch Bill, 5 Pay Bill, 6 Status.
- **Portal - BBPS Test (Mobikwik)** – same 6 with vendor=mobikwik.
- **API v2 - BBPS** – GET operators, POST fetch/pay, GET status (Api-Key auth).
- **API v2 - KYC** – PAN verify, verification status.
- **API v2 - Payments** – Initiate, status.
- **API v2 - SMS** – Send SMS, OTP send.
- **API v2 - AEPS** – Balance, status.
- **API v2 - DMT (PayPoint)** – Register Sender, Add Beneficiary, Remit, Transaction Status, Get Beneficiaries (Api-Key auth; dmt.* permissions).
- **API v2 - Vouchers** – Issue, balance.
- **Euronet EnService (External UAT)** – Direct Euronet UAT (5 requests); credentials body mein hain.
- **Mobikwik BBPS (External UAT)** – Token, Balance, View Bill, Recharge, Status; token variable set karein.

## Portal requests (Admin) ke liye

1. Browser mein `http://localhost:8000/signin/` khol ke login karein.
2. DevTools → Application → Cookies se `csrftoken` aur `sessionid` copy karein.
3. Collection variable `csrftoken` mein csrftoken paste karein.
4. Postman mein **Settings → General → Send cookies with requests** ON karein, ya har request mein **Headers** mein manually `Cookie: sessionid=...; csrftoken=...` add karein.

Ya **Portal - Auth → Login** request run karein (username/password body mein bhar ke); uske baad Postman cookies save kar leta hai (same domain).

## File location

- Collection: `postman/Payswap_API_Collection.postman_collection.json`
- Isi project ke andar; git commit karke team share kar sakti hai.
