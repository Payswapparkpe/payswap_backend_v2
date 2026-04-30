# MCP Incident Triage Pilot (BBPS/Voucher)

This pilot validates whether MCP reduces incident MTTR for BBPS and voucher failures.

## Pilot Objective
- Compare baseline incident handling vs MCP-assisted handling.
- Measure reduction in Mean Time To Resolution (MTTR).

## Scope
- Incident types:
  - BBPS fetch-bill / pay failures (Mobikwik, Euronet, partner errors).
  - Voucher rollback or mismatch incidents.
- Duration: first 10 qualifying incidents (or 2 weeks, whichever comes first).

## MCP Tool Stack for Pilot
- Fetch: vendor docs and latest API behavior.
- Postgres (read-only): request/transaction state verification.
- Redis (read-only): idempotency and retry-key inspection.
- Sentry: exception timeline and code-path correlation.
- Git: identify recent changes touching failure surface.

## Operational Flow
1. **Intake**: capture incident id, reference id, environment, timestamp.
2. **Error evidence**:
   - Pull Sentry issue or logs by correlation id/reference id.
   - Classify failure stage: request validation, vendor call, callback, settlement, rollback.
3. **State verification**:
   - Use Postgres read-only checks to verify request state and final ledger/service state.
   - Use Redis read-only checks to verify idempotency/lock/retry markers.
4. **Spec verification**:
   - Use Fetch to confirm current vendor contract (required field, signature rule, status map).
5. **Change correlation**:
   - Use Git server to review last merged changes touching impacted modules.
6. **Resolution and closure**:
   - Apply fix or operational workaround.
   - Record root cause category and total elapsed time.

## Metrics to Capture
- `time_to_detect_minutes`
- `time_to_identify_root_cause_minutes`
- `time_to_resolve_minutes`
- `total_mttr_minutes`
- `root_cause_category` (code, config, vendor, data, infra)
- `mcp_tools_used` (comma-separated)

## Success Criteria
- At least 25% MTTR improvement vs baseline.
- At least 70% of pilot incidents resolved without escalation to manual deep dive.
- Root-cause confidence marked as high in at least 80% of pilot incidents.

## Logging Template
Use `docs/mcp/templates/incident_pilot_log.csv` for each pilot incident.

## Review Cadence
- Daily during pilot: quick review of open incidents.
- End of pilot: publish summary with:
  - baseline MTTR
  - pilot MTTR
  - delta percentage
  - recommendation to expand or revise
