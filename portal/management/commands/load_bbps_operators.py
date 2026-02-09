"""
Load BBPS operators from Mobikwik/Operators.xlsx into portal_bbps_operator table.
Use for initial load and sync. All BBPS operations (Mobikwik, Euronet) use this data.
"""
import os
from django.conf import settings
from django.core.management.base import BaseCommand


def _val(v, default=None):
    if v is None:
        return default
    if hasattr(v, "__iter__") and not isinstance(v, str):
        try:
            import pandas as pd
            if pd.isna(v):
                return default
        except Exception:
            pass
    s = str(v).strip()
    return s if s else default


class Command(BaseCommand):
    help = "Load BBPS operators from Mobikwik/Operators.xlsx into DB"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default=None,
            help="Path to Operators.xlsx (default: <BASE_DIR>/Mobikwik/Operators.xlsx)",
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
            path = os.path.join(base, "Mobikwik", "Operators.xlsx")
        if not path or not os.path.isfile(path):
            self.stdout.write(self.style.ERROR(f"Operators file not found: {path}"))
            return

        try:
            import pandas as pd
        except ImportError:
            self.stdout.write(self.style.ERROR("pandas required: pip install pandas openpyxl"))
            return

        if options.get("clear"):
            n = BBPSOperator.objects.count()
            BBPSOperator.objects.all().delete()
            self.stdout.write(f"Cleared {n} existing BBPS operators.")

        bbps_only = options.get("bbps_only", True) and not options.get("no_bbps_only")

        try:
            df = pd.read_excel(path, sheet_name="Operator")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to read Excel: {e}"))
            return

        if df.empty:
            self.stdout.write("Sheet 'Operator' is empty.")
            return

        df.columns = [str(c).strip() for c in df.columns]
        if bbps_only and "BBPS Enabled" in df.columns:
            col = df["BBPS Enabled"]
            mask = col.fillna(False).astype(str).str.upper().str.strip().isin(("TRUE", "1", "YES"))
            df = df[mask]

        def get_op_value(row):
            for col in ("op", "Operator Id", "Operator ID", "OperatorId", "Mobikwik Op"):
                if col not in row:
                    continue
                v = row.get(col)
                if v is None or (hasattr(v, "__iter__") and not isinstance(v, str) and pd.isna(v)):
                    continue
                s = str(v).strip()
                if s.isdigit():
                    return s
                if s:
                    return s
            return None

        created = updated = 0
        for _, row in df.iterrows():
            biller_id = row.get("Biller ID")
            if pd.isna(biller_id) or not str(biller_id).strip():
                continue
            biller_id = str(biller_id).strip()

            op_val = get_op_value(row)
            name = _val(row.get("Operator Name"), "Unknown")
            cat = _val(row.get("Category"), "")
            view_bill = _val(row.get("ViewBill"))
            name_label = _val(row.get("Name")) or _val(row.get("cn")) or "Consumer ID"
            regex = _val(row.get("Regex"))
            ad1 = _val(row.get("ad1 with regex")) if "ad1 with regex" in row else _val(row.get("ad1"))
            ad2 = _val(row.get("ad2"))
            ad3 = _val(row.get("ad3"))
            ad4 = _val(row.get("ad4"))
            ad9 = _val(row.get("ad9"))
            additional_params = _val(row.get("Additional Params for payment API"))

            bbps_enabled = True
            if "BBPS Enabled" in row:
                v = row["BBPS Enabled"]
                if v is not None and not (hasattr(v, "__iter__") and not isinstance(v, str) and pd.isna(v)):
                    bbps_enabled = str(v).strip().upper() in ("TRUE", "1", "YES")

            obj, was_created = BBPSOperator.objects.update_or_create(
                biller_id=biller_id,
                defaults={
                    "op": op_val,
                    "name": name,
                    "category": cat,
                    "view_bill": view_bill,
                    "customer_label": name_label,
                    "regex": regex,
                    "ad1": ad1,
                    "ad2": ad2,
                    "ad3": ad3,
                    "ad4": ad4,
                    "ad9": ad9,
                    "additional_params": additional_params,
                    "bbps_enabled": bbps_enabled,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"BBPS operators: {created} created, {updated} updated. Total in DB: {BBPSOperator.objects.count()}"
        ))
