# BBPS Categories: Bharat Connect vs ParkPe

Bharat Connect (formerly Bharat Bill Payment System – BBPS) is run by NPCI. The public categories page (https://www.bharat-connect.com/categories/) may be restricted; this doc compares **official BBPS/Bharat Connect categories** (from Axis Bank, NPCI, RBI sources) with **ParkPe’s current list**.

## Official Bharat Connect–eligible categories (NPCI / Axis Bank)

| Category | ParkPe code | In ParkPe? |
|----------|-------------|------------|
| Electricity | `electricity` | ✅ Yes |
| Water | `water` | ✅ Yes |
| Gas | `gas` | ✅ Yes |
| Telecom (Post-paid) | `mobile_postpaid`, `landline`, `broadband` | ✅ Yes |
| Direct-to-Home (DTH) | `dth` | ✅ Yes |
| Municipal Tax | `municipal_taxes` | ✅ Yes |
| Education Institutions | `education` | ✅ Yes |
| Insurance Premium | `insurance` | ✅ Yes |
| EMIs / Loan repayment | `loan_repayment` | ✅ Yes |
| Housing Societies | — | ❌ No |
| Hospitals | — | ❌ No |
| Mutual Funds | — | ❌ No |
| Recurring Deposits | — | ❌ No |
| Clubs | — | ❌ No |

ParkPe also has:

- **`subscription`** – OTT / recurring subscriptions (Bharat Connect may list under DTH/Telecom or as a separate type depending on BOU).

## Where it’s defined

- **Backend (API):** `api/bbps_parkpe/views.py` → `PARKPE_BBPS_CATEGORIES`
- **Frontend (groups/labels):** `bbps-internal.component.ts` → `CATEGORY_GROUPS`  
  Categories are filtered by what the backend returns from `GET /api/bbps/categories` (or ParkPe’s equivalent), so the API list is the source of truth; frontend only groups/labels them.

## Conclusion

- **Bharat Connect categories we support:** Electricity, Water, Gas, DTH, Telecom (mobile postpaid, landline, broadband), Municipal Tax, Education, Insurance, EMIs/Loan repayment.  
- **Extra in ParkPe:** `subscription`.  
- **In Bharat Connect but not in ParkPe:** Housing Societies, Hospitals, Mutual Funds, Recurring Deposits, Clubs.  

To add any of the missing five, add the category code to `PARKPE_BBPS_CATEGORIES` and ensure operator data (DB/Excel or aggregator) exists for that category.

**References**

- [Axis Bank – Categories under BBPS](https://axisbank.com/business-banking/bharat-bill-payment-system/customers/categories-under-bbps)
- [RBI – BBPS](https://www.rbi.org.in/commonman/english/scripts/Notification.aspx?Id=2304)
- [NPCI Bharat Connect (Wikipedia)](https://en.wikipedia.org/wiki/Bharat_Connect)
- [Dataful – Bharat Connect billers dataset (state/category-wise)](https://dataful.in/datasets/20893/)
