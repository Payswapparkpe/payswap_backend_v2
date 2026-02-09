# Mobikwik BBPS – Biller logo / icon support

## Current state

- **Parkpe operator list** (`GET /api/bbps/operators?category=...`) uses operators from:
  1. **DB** (`portal_bbps_operator`) – loaded via `load_bbps_operators`
  2. **Excel** (`Mobikwik/Operators.xlsx`) – if DB is empty  
  It does **not** call Mobikwik’s operator API for this list.

- **Mobikwik client** (`portal/services/vendors/mobikwik.py`) has `get_operators(category)` which calls:
  - Path: `GET /recharge/v1/rechargePlansAPI` (from `DEFAULT_PATHS["operators"]`)
  - Used by: Portal test UI, API v2 BBPS, and `BBPSService.get_operators()`.

- **Biller logo in API**: The Parkpe operator response is built in `api/bbps_parkpe/views.py` via `_map_operator_to_angular()`, which already passes through `op.get("logo")`. So if an operator dict has a `logo` (or `logoUrl`) field, it can be exposed to the frontend. Right now DB and Excel do not provide `logo`, so the field is not set.

## Does Mobikwik API return biller logo/icon?

- In **this codebase** we do not have Mobikwik’s official API spec that documents the **exact** operator/biller list response (e.g. whether it includes `logo`, `icon`, `imageUrl`, or similar).
- **Public search** did not find Mobikwik BBPS documentation that explicitly mentions biller/operator logo or icon URLs in the operator list response.
- The path we use for “operators” is **rechargePlansAPI**, which is often used for recharge **plans**; a separate “billers list” API might exist with different fields (e.g. logo). That would need to be confirmed from Mobikwik’s API kit / PDF / developer portal.

**Recommendation:**  
Ask **Mobikwik support** or check their **BBPS / RT-Recharge & Bill Payment API** documentation (from your onboarding/API kit) for:

- Whether the **operator/biller list** response includes a logo or icon URL (e.g. `logo`, `icon`, `imageUrl`, `billerLogo`).
- The exact endpoint and response shape for “list billers” if it is different from `rechargePlansAPI`.

## If Mobikwik provides logo URL

1. **Option A – Use Mobikwik operator list for Parkpe**  
   Change Parkpe’s `/api/bbps/operators` to call `BBPSService.get_operators(category)` (Mobikwik) and map the response. If each item has a logo URL, include it in `_map_operator_to_angular()` (e.g. `op.get("logo")` or `op.get("billerLogo")`) and the frontend can show it.

2. **Option B – Keep DB/Excel as source, add logo in DB**  
   Add a `logo_url` (or `icon_url`) field to `portal.models.BBPSOperator` and in the Excel loader. When Mobikwik provides logos, either:
   - Sync from Mobikwik into DB, or  
   - Manually maintain logo URLs in Excel/DB.  
   Then in `api/bbps_parkpe/views.py`, when building the operator dict from DB/Excel, set `"logo": op.get("logo_url")` (and in `_map_operator_to_angular` use that), so the existing pass-through continues to work.

## If Mobikwik does not provide logo

- You can still support logos by:
  - Adding optional `logo_url` (or `icon_url`) to `BBPSOperator` and Excel.
  - Filling it from your own assets or a third‑party source and exposing it via the same `logo` field in the API.

## Summary

| Question | Answer |
|----------|--------|
| Can we fetch biller logo from Mobikwik today? | Not confirmed from our code or public docs; need Mobikwik API spec / support. |
| Does our API support logo? | Yes – `_map_operator_to_angular()` already includes `op.get("logo")`. |
| Where do Parkpe operators come from? | DB and Excel only; Mobikwik operator API is not used for Parkpe’s list. |
| Next step | Confirm with Mobikwik whether operator/biller list includes logo/icon URL; then either use their list (Option A) or add `logo_url` to DB/Excel and pass it through (Option B). |
