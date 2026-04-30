# Release-Day MCP Ops Playbook

This playbook integrates GitHub, Slack, and Time MCP servers for coordinated release execution.

## Goal
- Shorten release triage loops.
- Keep one source of truth for checks, blockers, and rollout decisions.

## Roles
- **Release Lead**: owns go/no-go and timeline.
- **Backend Owner**: Django/Celery/DB checks.
- **Frontend Owner**: Angular and ParkPe checks.
- **Ops Observer**: monitors incidents and communication hygiene.

## Pre-Release Checklist (T-60 to T-15)
1. Use GitHub MCP to pull:
   - open PR checks
   - failing workflows
   - required reviews status
2. Use Time MCP to confirm:
   - release window in IST and UTC
   - partner/vendor quiet-hours constraints (if any)
3. Post Slack MCP status update in release channel:
   - target version/branch
   - planned start and end window
   - current blockers

## Live Release Workflow
1. **Start message** (Slack MCP):
   - deployment started
   - owner assignments
2. **Check loop every 10 minutes**:
   - GitHub MCP: workflow runs, rollback PR state, hotfix PR readiness.
   - Time MCP: elapsed time and cutoff reminders.
3. **Blocker handling**:
   - Open incident thread in Slack via MCP.
   - Link CI run / commit / issue references from GitHub MCP.
4. **Decision points**:
   - Continue rollout if checks remain green.
   - Trigger rollback if critical failures exceed threshold.

## Post-Release (T+0 to T+30)
1. GitHub MCP: validate final checks and merged rollback readiness state.
2. Slack MCP: publish release completion message and known issues.
3. Time MCP: stamp closure time in both IST and UTC.
4. Create post-release note with:
   - duration
   - incidents
   - rollback actions (if any)

## Channel Conventions
- `#release-war-room`: real-time control.
- `#ops-alerts`: incident escalation.
- `#engineering`: broad status updates.

## Minimum Data Points per Release
- start_time_ist
- start_time_utc
- end_time_ist
- end_time_utc
- ci_failures_count
- incident_count
- rollback_invoked (yes/no)
