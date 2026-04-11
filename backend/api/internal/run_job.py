"""
Simplified management command runner for /internal/run-job/.
No api_management dependency.
"""
import io
import logging
from django.core.management import call_command

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = frozenset([
    "audit_partners",
    "reconcile_daily",
    "run_billing_cycle",
    "generate_invoices",
    "fraud_scan",
    "compliance_pack",
    "enterprise_export",
    "simulate_vendor_down",
    "backup_verify",
    "resend_pending_emails",
    "fix_stuck_batches",
    "process_batch_sync",
    "reconcile_pending_parkpe_orders",
])

DRY_RUN_COMMANDS = frozenset(["simulate_vendor_down", "backup_verify"])


def run_command_sync(command_name: str, dry_run: bool = False) -> tuple[bool, str, str]:
    """Run management command. Returns (success, message, output)."""
    if command_name not in ALLOWED_COMMANDS:
        return False, f"Command not allowed: {command_name}", ""
    out = io.StringIO()
    err = io.StringIO()
    kwargs = {}
    if dry_run and command_name in DRY_RUN_COMMANDS:
        kwargs["dry_run"] = True
    try:
        call_command(command_name, stdout=out, stderr=err, **kwargs)
        combined = (out.getvalue() + "\n" + err.getvalue()).strip()
        return True, "Command completed.", combined[:5000]
    except Exception as e:
        logger.exception("run_job: %s failed", command_name)
        return False, str(e)[:500], err.getvalue()[:2000]
