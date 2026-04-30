# Trusted MCP Servers for Payswap/ParkPe

This list prioritizes trusted publishers (official org ownership + active maintenance).

## Use now (high trust + high fit)

1. **Git (official MCP reference)**
   - Source: `modelcontextprotocol/servers` (`mcp-server-git`)
   - Why: best fit for code review, diff tracing, regression analysis.

2. **Filesystem (official MCP reference)**
   - Source: `@modelcontextprotocol/server-filesystem` (Anthropic publisher on npm)
   - Why: safe scoped access to repo and docs for agents.

3. **Fetch (official MCP reference)**
   - Source: `modelcontextprotocol/servers` (`mcp-server-fetch`, run with `uvx`)
   - Why: live vendor doc checks for Mobikwik/Cashfree/BBPS changes.

4. **Time (official MCP reference)**
   - Source: `modelcontextprotocol/servers` (`mcp-server-time`, run with `uvx`)
   - Why: IST/UTC settlement and release-window accuracy.

## Add next (trusted vendor-owned)

5. **GitHub MCP (official by GitHub)**
   - Source: `github/github-mcp-server`
   - Why: PR checks, release blockers, issue triage.

6. **Sentry MCP (official by Sentry)**
   - Source: `getsentry/sentry-mcp`, hosted endpoint `https://mcp.sentry.dev/mcp`
   - Why: production error diagnosis directly in coding workflow.

## Optional (data troubleshooting)

7. **Postgres MCP (official MCP package)**
   - Source: `@modelcontextprotocol/server-postgres`
   - Why: read-only DB diagnostics for reconciliation and incident triage.

## Trust filter to apply before installing any MCP

- Publisher is official org (`modelcontextprotocol`, `github`, `getsentry`) or verified vendor.
- Recent commits/releases in last 60-90 days.
- Clear permissions model (read-only where possible).
- No hardcoded secrets; supports env vars.
- Scope can be restricted (repo path, DB role, channel allowlist).

## Recommendation for this repo

- Keep `.cursor/mcp.json` on official reference servers for day-to-day coding.
- Add GitHub + Sentry as next phase for release and incident workflows.
- Add Postgres read-only only after dedicated DB readonly user is created.
