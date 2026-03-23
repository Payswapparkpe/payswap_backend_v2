# Phase 8 Validation Logs

Recorded outputs from Phase 8 lockdown validation. Re-run periodically to confirm stability.

## Commands

| Log file | Command |
|----------|---------|
| audit_partners.txt | `python manage.py audit_partners` |
| generate_invoices.txt | `python manage.py generate_invoices --no-pdf` |
| fraud_scan.txt | `python manage.py fraud_scan --dry-run` |
| enterprise_export.txt | `python manage.py enterprise_export --output=.../enterprise_export.json` |
| compliance_pack.txt | `python manage.py compliance_pack --output=.../compliance_pack` |
| reconcile_daily.txt | `python manage.py reconcile_daily --dry-run` |
| test_analytics.txt | `pytest api/tests/test_analytics.py -v` |
| test_governance_and_smoke.txt | `pytest api/tests/test_partner_governance.py api/tests/test_production_smoke.py -v` |

## Artifacts

- `enterprise_export.json` — Enterprise export for the run.
- `compliance_pack/` — Directory with soc2_pack.json, iso_pack.json, rbi_audit.json, bank_due_diligence.json.

## When to re-run

- Before each production deploy (or use `scripts/pre_deploy_check.sh`).
- After DB or config changes.
- Weekly for audit trail.
