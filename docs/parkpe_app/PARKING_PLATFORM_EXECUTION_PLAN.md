# Parkpe Parking Platform Execution Plan

## Objective
Build a market-ready Parkpe parking platform for app + web + hub operations with:
- live location and slot discovery
- booking and voucher payment
- ticketing (QR, print, WhatsApp, email)
- owner/operator dashboards
- admin control and reporting
- phase-2 readiness for FASTag, ANPR, and IoT

## Current Build Status (Codebase)
- Backend parking API exists under `backend/api/parkpe_api/parking_views.py` and `parking_urls.py`.
- Domain models exist under `backend/portal/models/parking.py` (location, slot, booking, ticket, revenue, operator).
- Core services exist under `backend/portal/services/parking_service.py` and `parking_notification_service.py`.
- Celery tasks exist under `backend/portal/tasks/parking_tasks.py`.
- Angular customer parking flow exists under `frontend/projects/parkpe/src/app/features/parking/*`.
- Hub parking owner views exist under `backend/portal/views/parking_owner_views.py` and `portal/templates/portal/parking/*`.

---

## 1) Customer Experience: screens, facilities, services

### A. Mandatory customer screens
1. Parking home (map + list)
2. Location detail (rates, amenities, availability)
3. Slot selection (zone/floor view)
4. Booking and payment
5. Ticket detail and history
6. Active session screen (entry/exit status)

### B. Customer facilities and services
- Nearby parking discovery by geolocation
- Search by city/area/landmark
- Real-time slot availability
- Vehicle type filtering (2W/4W/EV)
- Time-based estimate before payment
- Voucher payment flow
- Booking confirmation with QR ticket
- WhatsApp and email ticket delivery
- Ticket re-send and download
- Booking cancel (policy based)
- Booking history and receipts

### C. Customer service SLAs
- Booking API p95 latency < 500ms
- Ticket delivery attempt in < 30s
- Slot consistency: no double booking under concurrency
- Uptime target: 99.9% for booking APIs

---

## 2) Parking Owner/Operator Model

### A. Roles (recommended)
1. Owner
2. Operations Manager
3. Attendant/Gate Operator
4. Finance Analyst
5. Support/Dispute Handler

### B. Role responsibilities
- Owner:
  - pricing, staff assignment, revenue and settlement oversight
- Manager:
  - occupancy control, slot maintenance, shift and exception handling
- Attendant:
  - entry/exit verification, manual override, print ticket
- Finance:
  - daily closure, gross/net reconciliation, payout and tax exports
- Support:
  - disputes, cancellation exceptions, ticket correction workflows

### C. Owner-facing modules
- Live occupancy dashboard
- Slot health board (available/reserved/blocked/maintenance)
- Booking feed and gate operations
- Revenue analytics (daily/weekly/monthly)
- Settlement and commission statements
- Audit trail viewer

### D. Reports pack (owner)
- Daily bookings report
- Occupancy heatmap by hour
- Utilization by zone/floor
- Revenue (gross, net, commission, tax)
- No-show/cancellation report
- Overstay report
- Operator activity and exception report

---

## 3) Admin E2E (Hub) Flow

### A. Admin modules
- Parking location onboarding and geofence setup
- Slot/zoning master configuration
- Owner/operator onboarding and role assignment
- Pricing governance and approval
- Exceptions and fraud/risk queue
- Settlement control panel
- System audit and compliance logs

### B. E2E operating sequence
1. Admin creates location and geofence
2. Admin configures zones and slots
3. Admin assigns owner and operator roles
4. Admin sets rate cards and rules
5. Customer books and pays via voucher
6. Gate operator verifies entry QR
7. Exit closes session and computes final amount
8. Revenue and commission rollups update
9. Monthly settlement statements generated
10. Admin audits exceptions and disputes

### C. Admin reports
- City-wise occupancy and throughput
- Revenue and settlement dashboards
- SLA breach dashboards
- Reconciliation and failure buckets
- Audit and compliance extracts

---

## 4) Outsourcing Requirements

### A. Mandatory outsource/partner integrations
- Maps provider: MapmyIndia/Mappls production contract
- WhatsApp Business API provider
- SMTP/Email provider (SES/Sendgrid)
- SMS OTP provider (fallback channel)
- PDF and print integration support
- Security testing vendor (VAPT/API pentest)

### B. Phase-2 outsource tracks
- FASTag acquiring bank + certification partner
- ANPR vendor for number plate recognition
- IoT/barrier hardware vendor with AMC
- NOC/monitoring partner for 24x7 ops

### C. Governance for outsourcing
- Contracted uptime SLAs
- DLP/privacy clauses and data residency
- Incident response timelines
- Joint UAT and DR drill commitments

---

## 5) Delivery Roadmap (Build Plan)

### Sprint 0 (1 week): Hardening and readiness
- finalize API contracts and error codes
- add seed data command for parking demo
- enable role-to-location permission checks
- add smoke tests for booking and exit

### Sprint 1 (2 weeks): Customer MVP
- map/list discovery
- slot selection and booking
- voucher payment and ticket issue
- booking history and cancellation

Acceptance:
- end-to-end booking to ticket in staging
- no double-booking in concurrent test

### Sprint 2 (2 weeks): Operator and owner cockpit
- gate verification workflows
- owner dashboards and reports
- daily revenue rollups and exports

Acceptance:
- operator can run live entry/exit cycle
- owner gets daily and monthly reports

### Sprint 3 (2 weeks): Admin and controls
- onboarding workflows
- pricing governance
- exception queues and audits

Acceptance:
- admin can configure full location independently
- all critical actions audit logged

### Sprint 4 (2 weeks): Stabilization + go-live
- performance tuning
- load tests
- VAPT fixes
- operational runbooks

Acceptance:
- go-live checklist signed off by product, ops, and security

---

## 6) Team Shape
- Backend: 2 engineers
- Frontend web: 1 engineer
- Mobile Flutter: 1 engineer
- QA automation: 1 engineer
- DevOps/SRE: shared
- Product + Ops: shared

---

## 7) Immediate Next Execution Items
1. Run migrations and seed sample parking data.
2. Add API integration tests for booking/entry/exit.
3. Add role-wise permission matrix in hub.
4. Wire ticket PDF generation endpoint.
5. Add CI checks for parking module coverage.

