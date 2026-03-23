---
name: Project Deep Cleanup and Internal Service
overview: Payswap project me deep cleanup karke sirf essential services rakhenge. Naming: Backend = Payswap Hub (Django), Frontend = Parkpe (B2C) + Payswap (B2B, Parkpe jaisa). Unused vendors, api/enterprise, api/governance, v2 AEPS/DMT hataenge. Internal Service alag se banega; dono frontends Payswap Hub APIs use karenge.
todos: []
isProject: false
---

# Project Deep Cleanup aur Internal Service Plan

## Quick Reference

| Item | Value |
| ---- | ----- |
| **Backend** | Payswap Hub (Django) – saari APIs yahan |
| **Frontend** | Parkpe (B2C) + Payswap (B2B) – dono Payswap Hub APIs use karte hain |
| **API Flow** | Payswap Hub → Parkpe \| Payswap Hub → Payswap |
| **Internal Service** | Payswap Hub ke andar – dono frontends yahan se manage |
| **Remove** | enterprise, governance, Euronet, PayPoint, Instantpay, Leegality, Invincible Ocean, v2 AEPS/DMT, payswap-governance |
| **Keep** | SMTP, Kaleyra, Mobikwik, Cashfree Verification, Cashfree PG, Connect, VoucherX, Auth |

---

## Naming Convention

| Layer | Name | Location |
| ----- | ---- | -------- |
| **Backend** | **Payswap Hub** | Django project (`core/`, `api/`, `portal/`) |
| **Frontend App 1** | **Parkpe** | Consumer B2C – `frontend-space/projects/parkpe/` |
| **Frontend App 2** | **Payswap** | B2B consumer app – `frontend-space/projects/payswap/` (Parkpe jaisa, B2B) |
| **Internal Service** | (to be built) | Payswap Hub ke andar – Portal/API; Parkpe + Payswap manage |

**Note:** Payswap frontend = B2B app (Parkpe jaisa hi), NOT admin tool. Dono Parkpe aur Payswap Payswap Hub se APIs use karenge. **Internal Service Payswap Hub me hi banega** – dono frontend apps ko yahan se manage kiya jayega (Portal Django ya api/internal).

**API structure:**
- Saari APIs **Payswap Hub** me rahengi (Django: api/, portal/)
- Payswap Hub → **Parkpe** frontend (B2C APIs)
- Payswap Hub → **Payswap** frontend (B2B APIs)

**Renames:** `APP_NAME` → "Payswap Hub", admin title → "Payswap Hub Admin"

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────┐
│              Payswap Hub (Django)                │
│  ┌─────────────────┐  ┌─────────────────────┐   │
│  │ APIs (api/)     │  │ Internal Service    │   │
│  │                 │  │ Parkpe + Payswap    │   │
│  │                 │  │ manage (Portal/     │   │
│  │                 │  │ api/internal)        │   │
│  └────────┬────────┘  └─────────────────────┘   │
└───────────┼──────────────────────────────────────┘
            │
    ┌───────┴───────┐
    ▼               ▼
┌─────────────┐  ┌─────────────┐
│ Parkpe B2C  │  │ Payswap B2B  │
└─────────────┘  └─────────────┘
```

---

## Phase 1: Payswap Hub Backend Cleanup

### 1.1 Unused Vendors Remove
Euronet, PayPoint AEPS/DMT, Instantpay, Leegality, Invincible Ocean – delete files, config, templates, handler registry.

### 1.2 V2 API – AEPS/DMT Remove
Delete `api/v2/aeps_views.py`, `api/v2/dmt_views.py`; remove paths from `api/v2/urls.py`; update vendor_router.

### 1.3 api/enterprise + api/governance Remove
- Delete `api/enterprise/`, `api/governance/` folders
- Remove from `api/urls.py`: enterprise, control paths
- `api/urls_dashboard.py`: keep only ParkPe summary, pincode
- Delete `test_governance_control.py`; remove Enterprise tests from `test_analytics.py`
- Portal: Remove governance URLs, views, templates, sidebar links, control_center_overview

### 1.4 payswap-governance Angular Remove
Delete `frontend-space/projects/payswap-governance/`; update `angular.json`.

---

## Phase 2: Parkpe Frontend Cleanup

- Parking, FASTag, Challan – nav se remove; routes collapse/placeholder
- Keep: Home, Auth, Dashboard, Connect, BBPS, Payment, Vouchers, Profile, Settings

---

## Phase 3: Internal Service – Design (Baad me)

**Internal Service = Payswap Hub ke andar** (Portal Django ya api/internal)
- Dono Parkpe aur Payswap frontends ko Payswap Hub se manage
- Admin/ops dashboard – reports, roles, project config
- Roles: Business, Technical, Sales, Operations, Super
- Reports: technical, financial, operations, business

---

## Phase 4: Internal Service Build (Baad me)

Payswap Hub me hi build – Portal views/templates expand ya `api/internal/` extend. Payswap B2B frontend alag consumer app rahega.

---

## Phase 5: Portal Cleanup (Optional)

Skip for now. Baad me redundant dashboards remove.

---

## Phase 6: Naming + Docs

- `APP_NAME` = "Payswap Hub"
- Update docs, .env.example (remove removed vendor keys)

---

## Execution Order

1. Phase 1 – Backend cleanup
2. Phase 2 – Parkpe cleanup
3. Phase 6 – Naming + Docs
4. Phase 3+4 – Internal Service (later)

---

## Estimated Scope

| Phase | Effort | Files |
| ----- | ------ | ----- |
| Phase 1 | High | ~35 files |
| Phase 2 | Low | ~5 files |
| Phase 6 | Low | ~3 files |
