# Cursor MCP Quickstart (Usable Now)

This setup makes MCP immediately usable in this repository for agent workflows.

## 1) What is already configured

- Project-level MCP config is added at `.cursor/mcp.json`.
- It enables 4 stable servers out of the box:
  - `payswap-git`
  - `payswap-fetch`
  - `payswap-filesystem`
  - `payswap-time`

## 2) Environment variables to set

Add these to your shell profile (`~/.zshrc`) or export before launching Cursor:

```bash
export MCP_TIME_DEFAULT_TZ="Asia/Kolkata"
```

Restart Cursor after setting env vars.

## 3) Optional advanced servers

- Use `docs/mcp/cursor-mcp.example.json` for Postgres/Redis/Sentry/GitHub/Slack.
- Replace placeholder package names with your selected maintained servers.
- Keep all secrets in env vars only.
- Trusted shortlist is documented in `docs/mcp/trusted-servers-shortlist.md`.

## 4) Agent prompts that now work well

Use these directly in chat:

```text
Vendor BBPS error aa raha hai. payswap-fetch se latest Mobikwik doc check karo, payswap-git se recent changes dekho, root cause batao.
```

```text
Last 3 commits me parking-owner auth flow me kya badla, summarize karo aur regression risk identify karo.
```

```text
Settlement cutoff IST aur UTC dono me calculate karo for tomorrow 11:30 PM IST.
```

```text
docs aur backend code read karke voucher rollback troubleshooting checklist banao.
```

## 5) Team policy

- Local: read/write only where needed.
- Staging/Prod: read-only-first.
- Never commit tokens or DSNs.

