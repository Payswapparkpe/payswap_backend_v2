# MCP Server Shortlist (Implemented)

This shortlist is finalized for Payswap/ParkPe and mapped to environment policy.

## Tier 1 - Immediate

| Server | Primary use | Local | Staging | Prod |
| --- | --- | --- | --- | --- |
| Git | Diff/context/search during development and review | RW | RO | RO |
| Fetch | Vendor/API documentation lookup (Mobikwik, Cashfree, BBPS specs) | RO | RO | RO |
| Filesystem | Controlled codebase and runbook access | Scoped RW | Scoped RO | Scoped RO |
| Postgres | Read-only diagnostics (reconciliation, settlement, BBPS states) | RO | RO | RO |
| Sentry | Error-to-code triage for backend and frontend incidents | RO | RO | RO |

## Tier 2 - Ops and Release

| Server | Primary use | Local | Staging | Prod |
| --- | --- | --- | --- | --- |
| Redis | Inspect idempotency, OTP/rate-limit keys, queue state | RO | RO | RO |
| GitHub | PR checks, review comments, release issue tracking | RO | RO | RO |
| Slack | Incident and release communication workflows | Optional | RO | RO |
| Time | Timezone-safe settlement and release-window calculations | RO | RO | RO |

## Rollout Gates
1. Enable Tier 1 in local first.
2. Move Tier 1 to staging after credential scoping and audit logs.
3. Enable Tier 2 after release playbook dry run.
4. Keep production access read-only unless explicit exception is approved.

## De-scoped for now
- Memory and Sequential Thinking are deferred until measurable benefit is shown in the BBPS/voucher incident pilot.
- Browser automation MCP is optional because this repository already supports UI testing flows through existing tooling.
