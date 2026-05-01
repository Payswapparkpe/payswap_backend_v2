# MCP Credential and Access Model

This policy defines secure MCP access for Payswap/ParkPe environments.

## Core Rules
- Use least privilege by default.
- Use separate credentials for local, staging, and production.
- Use read-only credentials for all production MCP servers.
- Never store tokens in tracked config files; store only placeholders in examples.
- Rotate MCP credentials on a fixed schedule or immediately after incident exposure.

## Access Baseline by Server

| Server | Identity | Minimum scope | Notes |
| --- | --- | --- | --- |
| Git | machine user/token | repository read (write only in local) | Avoid admin scopes |
| Fetch | none/API key if vendor docs require | fetch-only | Use allowlist for domains |
| Filesystem | local process user | explicit path allowlist | Restrict to repo and docs paths |
| Postgres | dedicated DB role | SELECT on approved schemas | No DDL/DML permissions |
| Redis | dedicated ACL user | read-only commands on approved key prefixes | Disable mutating commands |
| Sentry | scoped token | read project issues/events | No org-admin scopes |
| GitHub | bot PAT/GitHub App | repo read, pull-request read, checks read | Add write only if explicitly needed |
| Slack | bot token | channel read/send in selected channels | Restrict channel membership |
| Time | none | timezone conversion only | No secret required |

## Environment Separation
- **Local**: developer-scoped credentials; can use controlled write for Git/Filesystem only.
- **Staging**: shared service accounts, read-only data tools, full audit logging.
- **Production**: isolated service accounts, read-only data tools, mandatory approval workflow for any elevated action.

## Secret Storage Standard
- Use environment variables loaded from local `.env` (ignored by git) or secret manager in hosted environments.
- Example config files must use `${VAR_NAME}` placeholders only.
- Maintain a credential inventory with owner, creation date, scope, and rotation date.

## Rotation and Revocation
- Rotate all MCP tokens every 90 days.
- Rotate immediately on suspected leakage.
- Revoke credentials for team members leaving the project on the same day.

## Audit Requirements
- Log: timestamp, actor, server, tool, target resource, result status.
- Retain logs for incident review and postmortems.
- Redact secrets from all logs and error traces.
