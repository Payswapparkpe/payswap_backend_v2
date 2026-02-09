# Services Are Vendor-Orchestrated, Step-Based Flows

## Migration

Run after dependencies (e.g. `simple_history`) are installed:

```bash
python manage.py migrate portal
```

- **0030_add_vendor_flow_models:** Adds `Service.category`, `ApiVendor`, `VendorApi`, and `ServiceFlowStep`. Backward-compatible.
- **0031_add_service_category_safe:** Ensures `portal_service.category` exists (safe if DB was restored or 0030 partially applied). No-op when column already present.
- **0032_...:** Syncs `simple_history` (adds `category` to `historicalservice`) and renames an index on `emailqueue`. Created by `makemigrations` when models and history diverge.

---

## Concept

- **Vendor ≠ Service.** Vendors (PayPoint, Euronet, M2P, etc.) are first-class entities that provide APIs.
- **API ≠ Transaction.** Each Vendor API is one callable capability (e.g. "Add Agent", "Balance Enquiry").
- **Services are orchestrated flows.** A service (AEPS, DMT, BBPS) is an ordered sequence of steps; each step is a (Vendor, VendorApi) pair. Execution order is defined in data (ServiceFlowStep), not in code.
- **Same API can be reused** across multiple services.

## Model Summary

| Model | Purpose |
|-------|---------|
| **ApiVendor** | Vendor entity (name, code, is_active, description). |
| **VendorApi** | One API capability under a vendor (name, api_code, api_type, purpose, endpoint_url, http_method, timeout, retry). `api_type`: SETUP / VALIDATION / AUTH / TRANSACTION / 2FA / QUERY. `purpose`: one-line description for orchestration. |
| **Service** | Final product (AEPS, DMT, BBPS). Has optional `category` for grouping. |
| **ServiceFlowStep** | One step in a service flow: (service, vendor, vendor_api, step_order, step_name, is_mandatory, halt_on_failure). Order is unique per service. Execution is **data-driven** from DB. |

**Important:** Vendor page alone is not enough. Until Service flow steps (Vendor → APIs in serial order) are defined per service, the system cannot do scalable, auditable orchestration. Flow must come from DB, not hardcoded Python.

## Execution Engine

- **ServiceExecutionEngine** runs a service by:
  1. Loading `ServiceFlowStep` for the service, ordered by `step_order`.
  2. For each step: resolving a **handler** by (vendor_code, api_code), then calling the handler with (step, context, payload).
  3. Storing each step result in `context` for later steps; if a step fails and `halt_on_failure` is True, the flow stops.
- **No vendor-specific logic in the engine.** Handlers are registered per (vendor_code, api_code). New vendors are added by registering handlers and configuring steps in admin.
- **Usage:** `get_execution_engine().execute(service_code, payload, user_id=..., agent_id=...)` returns `{ success, error, step_results, final_result }`.

### Handler registration

Handlers are registered per `(vendor_code, api_code)`. Default handlers for **PayPoint AEPS** and **PayPoint DMT** are registered in `portal.services.handler_registry` and invoked from `PortalConfig.ready()`.

To add a new vendor or API:

```python
from portal.services.execution_engine import register_handler

def my_handler(step, context, payload):
    # step: ServiceFlowStep; context: dict (accumulated results); payload: request payload
    # Call your vendor client, then return {"success": bool, "result": ..., "error": ...}
    result = my_vendor_client.some_api(**payload)
    return {"success": result.get("success", False), "result": result, "error": result.get("error")}

register_handler("my_vendor", "my_api_code", my_handler)
```

Register in `portal/services/handler_registry.py` (and call from `ready()`) or in `AppConfig.ready()` so handlers are available at runtime.

## Seed data (real vendors and APIs)

Run once (or when adding new vendors):

```bash
python manage.py seed_vendor_apis
```

This creates/updates **ApiVendor** and **VendorApi** for: PayPoint (AEPS), PayPoint DMT, Euronet, Cashfree, Cashfree PG, Kaleyra, Mobikwik, Instantpay, Leegality. Use `--dry-run` to preview.

After seeding, define **ServiceFlowStep** per service in Django Admin (Services → &lt;service&gt; → Service flow steps) so execution order is data-driven.

## Admin

- **ApiVendor:** Create/edit vendors; inline VendorApi list.
- **VendorApi:** Create/edit APIs (name, api_code, api_type, purpose, http_method, retry_allowed).
- **Service:** **ServiceFlowStep** inline: add/reorder steps (step_order), set vendor, vendor_api, is_mandatory, halt_on_failure.
- **ServiceFlowStep:** Standalone admin for steps; reorder by changing `step_order`. All changes are auditable (Django admin history).

## Portal Pages (super/admin)

- **GET /services/** – Services list; link to API Vendors.
- **GET /services/<id>/** – Service detail: **Service Flow (Orchestration)** section shows ordered steps. Staff see "Edit flow in Admin". If no steps, message + link to add in Admin.
- **GET /services/api-vendors/** – API Vendors list (all vendors; active/inactive badge). Link to Services.
- **GET /services/api-vendors/<vendor_code>/** – Vendor detail with APIs table; staff see “Edit in Admin”.

## API Endpoints (Frontend)

- **GET /api/v2/vendors/** – List vendors.
- **GET /api/v2/vendors/<code>/** – Vendor detail with list of APIs.
- **GET /api/v2/services/** – List services; optional `?category=AEPS`.
- **GET /api/v2/services/<code>/flow/** – Ordered steps for a service (vendor, vendor_api, step_order, step_name, is_mandatory, halt_on_failure). Frontend must NOT guess step order; use this response.

## Success Criteria

- New vendor: add ApiVendor + VendorApi rows and register handlers in code; no change to core engine.
- Service flow order: change ServiceFlowStep.step_order in admin; no deploy.
- Same API in multiple services: use the same VendorApi in multiple ServiceFlowStep rows.
- Frontend: render vendor list, vendor APIs, and per-service ordered steps from the APIs above; no vendor-specific logic in frontend.
