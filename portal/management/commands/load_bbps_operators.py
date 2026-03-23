"""Load BBPS operators workbook into portal_bbps_operator table."""
import os
from django.conf import settings
from django.core.management.base import BaseCommand

from portal.services.bbps_operators_loader import (
    DEFAULT_OPERATOR_FILES,
    parse_operator_workbook,
)


class Command(BaseCommand):
    help = "Load BBPS operators from Mobikwik Operators.xlsx into portal_bbps_operator"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default=None,
            help="Path to Operators .xlsx (default: first of mobikwik/Operators (13).xlsx, Mobikwik/Operators.xlsx)",
        )
        parser.add_argument(
            "--sheet",
            type=str,
            default="Operator",
            help="Sheet name (default: Operator)",
        )
        parser.add_argument(
            "--all-sheets",
            action="store_true",
            help="Parse all sheets and ingest operator-like rows from each.",
        )
        parser.add_argument(
            "--include-sheets",
            type=str,
            default="",
            help="Comma-separated sheet names to include (used with --all-sheets).",
        )
        parser.add_argument(
            "--exclude-sheets",
            type=str,
            default="",
            help="Comma-separated sheet names to exclude (used with --all-sheets).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing BBPS operators before load",
        )
        parser.add_argument(
            "--bbps-only",
            action="store_true",
            default=True,
            help="Load only rows where BBPS Enabled is True/1/Yes (default: True)",
        )
        parser.add_argument(
            "--no-bbps-only",
            action="store_true",
            help="Load all rows regardless of BBPS Enabled",
        )

    def handle(self, *args, **options):
        from portal.models import BBPSOperator

        base = getattr(settings, "BASE_DIR", None)
        path = options.get("path")
        if not path and base:
            path = None
            for rel in DEFAULT_OPERATOR_FILES:
                candidate = os.path.join(base, rel)
                if os.path.isfile(candidate):
                    path = candidate
                    self.stdout.write(f"Using operators file: {rel}")
                    break
        if path and base and not os.path.isabs(path):
            path = os.path.join(base, path)
        if not path or not os.path.isfile(path):
            self.stdout.write(self.style.ERROR(f"Operators file not found: {path}"))
            return

        if options.get("clear"):
            n = BBPSOperator.objects.count()
            BBPSOperator.objects.all().delete()
            self.stdout.write(f"Cleared {n} existing BBPS operators.")

        bbps_only = options.get("bbps_only", True) and not options.get("no_bbps_only")
        all_sheets = bool(options.get("all_sheets"))
        include_sheets = [s.strip() for s in str(options.get("include_sheets") or "").split(",") if s.strip()]
        exclude_sheets = [s.strip() for s in str(options.get("exclude_sheets") or "").split(",") if s.strip()]
        sheet = (options.get("sheet") or "Operator").strip() or "Operator"

        parsed = parse_operator_workbook(
            path,
            bbps_enabled_only=bbps_only,
            sheet_names=None if all_sheets else [sheet],
            include_sheets=include_sheets or None,
            exclude_sheets=exclude_sheets or None,
        )
        operators = parsed.get("operators") or []
        if not operators:
            self.stdout.write(self.style.WARNING("No operators parsed from workbook with current filters."))
            return

        created = updated = 0
        for op in operators:
            _, was_created = BBPSOperator.objects.update_or_create(
                biller_id=str(op.get("biller_id") or "").strip(),
                defaults={
                    "op": op.get("op"),
                    "name": op.get("name") or "Unknown",
                    "category": op.get("category") or "",
                    "view_bill": op.get("view_bill") or "",
                    "circle": op.get("circle") or "",
                    "customer_label": op.get("customer_label") or "Consumer ID",
                    "regex": op.get("regex"),
                    "ad1": op.get("ad1"),
                    "ad2": op.get("ad2"),
                    "ad3": op.get("ad3"),
                    "ad4": op.get("ad4"),
                    "ad9": op.get("ad9"),
                    "additional_params": op.get("additional_params"),
                    "bbps_enabled": bool(op.get("bbps_enabled", True)),
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        sheet_stats = parsed.get("sheet_stats") or {}
        for sheet_name, stats in sheet_stats.items():
            self.stdout.write(
                f"[{sheet_name}] rows={stats.get('rows', 0)} parsed={stats.get('parsed', 0)} skipped={stats.get('skipped', 0)} rejected={stats.get('rejected', 0)}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"BBPS operators: {created} created, {updated} updated. Total in DB: {BBPSOperator.objects.count()}"
        ))
