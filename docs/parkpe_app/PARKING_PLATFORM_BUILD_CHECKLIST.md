# Parking Platform Build Checklist

Use this as execution tracker during implementation.

## Sprint 0
- [ ] Run migration `0087_parking_models` in staging
- [ ] Add `setup_parking_demo_data` management command
- [ ] Validate `parking/` API route auth and permissions
- [ ] Add smoke tests: create booking, entry, exit
- [ ] Add owner role access tests

## Sprint 1 (Customer)
- [ ] Parking list with map + search is production-ready
- [ ] Slot selection handles zone and vehicle filters
- [ ] Booking form validates payload and date windows
- [ ] Voucher deduction is idempotent
- [ ] QR ticket generation is stable
- [ ] WhatsApp/email ticket notifications sent reliably
- [ ] Booking history and cancellation flows verified

## Sprint 2 (Owner/Operator)
- [ ] Entry/exit verifier works on low bandwidth
- [ ] Owner dashboard metrics validated
- [ ] Revenue report totals reconcile with transactions
- [ ] Daily rollup and monthly report tasks scheduled
- [ ] Ticket print template validated on thermal format

## Sprint 3 (Admin)
- [ ] Location onboarding flow in hub
- [ ] Role templates and assignment approvals
- [ ] Pricing rule governance workflow
- [ ] Exception queue and audit workflows
- [ ] Reconciliation dashboard and exports

## Sprint 4 (Go-Live)
- [ ] Load testing complete with sign-off
- [ ] VAPT complete and remediated
- [ ] Monitoring and alerting rules active
- [ ] Runbook and on-call ownership ready
- [ ] Production go/no-go checklist signed

## Outsource Tracks
- [ ] Map provider contract active
- [ ] WhatsApp BSP onboarding complete
- [ ] Security testing vendor engaged
- [ ] FASTag bank/acquirer discussion initiated
- [ ] IoT/ANPR vendor shortlist completed

