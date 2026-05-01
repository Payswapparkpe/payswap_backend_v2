# MCP Adoption for Payswap/ParkPe

This directory contains an implementation-ready MCP rollout for Payswap/ParkPe.

## Files
- `server-shortlist.md`: Tier-1/Tier-2 MCP servers with local/staging/prod-readonly fit.
- `credential-and-access-model.md`: least-privilege credential and secret handling standard.
- `incident-triage-pilot.md`: BBPS/voucher incident pilot flow and MTTR measurement format.
- `release-day-ops-playbook.md`: GitHub/Slack/Time integration for release coordination.
- `cursor-mcp.example.json`: example Cursor MCP configuration with placeholders.
- `quickstart-cursor.md`: fast setup and copy-paste prompts for day-to-day agent use.
- `trusted-servers-shortlist.md`: trusted publisher-first MCP recommendations.

## Enabled now
- Project-ready MCP config: `.cursor/mcp.json`
- Active stable servers:
  - `payswap-git`
  - `payswap-fetch`
  - `payswap-filesystem`
  - `payswap-time`

## Scope
- Focused on current stack: Django, DRF, PostgreSQL, Redis, Celery, Angular.
- Designed for secure rollout with read-only-first access in non-local environments.
- Aligned with existing CI and operational workflows already present in this repository.
