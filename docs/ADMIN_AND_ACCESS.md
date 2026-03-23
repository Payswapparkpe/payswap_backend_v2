# Admin Users, Access & Rules

## 1. Sabse zyada power / access kiske paas hai

**Project mein sabse zyada power aur access sirf ek type ke user ke paas hai:**

| Role          | Hierarchy | Django Admin | Permissions / Access |
|---------------|-----------|--------------|----------------------|
| **super_admin** | 100 (highest) | Yes (is_staff + is_superuser) | Full: all permissions, run-job, hub RBAC, demote others, create superuser. |
| admin         | 90        | Typically Yes | Portal admin views, users, vouchers, BBPS, services; not run-job / super-only. |
| employee      | 50        | No (usually) | Limited admin-like access as per code. |
| super_distributor | 45  | No           | Distributor hierarchy. |
| distributor   | 40        | No           | Distributor. |
| retailer      | 30        | No           | Retailer. |
| customer      | 20        | No           | End user / B2C. |

**Conclusion:** **Super Admin** (role `super_admin` + `is_superuser=True` + `is_staff=True`) ke paas **sabse zyada power** hai — Django admin, backend run-job, hub RBAC, aur jahan code `super_admin` / `is_superuser` check karta hai wahan full access.  
Abhi project mein yeh typically **sandeepsuda (ID: 10)** hai.

---

## 2. Mobile number rule – ek hi role ya koi bhi role, duplicate nahi

**Rule:** **Ek hi role ke do users ka mobile number same nahi hona chahiye; aur is project mein to koi bhi do users ka mobile same nahi ho sakta.**

- **Database level:** `Profile.phone` pe **unique=True** hai — pure project mein **har user ka mobile number unique** hona zaroori hai (chahe role kuch bhi ho).
- **Dhyan rahe:** Naye user create karte waqt ya profile update karte waqt yeh rule hamesha follow karo: **same role ho ya different, do users ka mobile number same nahi.**

Agar same number do users ko assign kiya gaya to DB unique constraint ki wajah se save fail ho jayega.

---

## 3. MFA reset (admin login ke liye)

Agar koi admin user MFA ki wajah se login nahi kar pa raha:

```bash
python manage.py reset_mfa_for_phone <10-digit-mobile>
# Example: python manage.py reset_mfa_for_phone 9461001200
```

Us user ka MFA off ho jayega; phir woh bina OTP sign in kar sakta hai.
