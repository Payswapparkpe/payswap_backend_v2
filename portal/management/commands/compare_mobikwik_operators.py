"""
Compare BBPS operators: our DB vs Mobikwik API (per category).
Shows how many operators we have in DB vs how many Mobikwik returns for each category.
If Mobikwik API is not configured or returns 0 (e.g. in UAT), only DB counts are shown.
Run after: python manage.py load_bbps_operators (so DB is populated from Mobikwik/Operators.xlsx).
"""
from django.core.management.base import BaseCommand

# Categories we support (ParkPe) – same as api/bbps_parkpe/views.py
PARKPE_CATEGORIES = [
    "electricity",
    "water",
    "gas",
    "dth",
    "broadband",
    "mobile_postpaid",
    "landline",
    "insurance",
    "loan_repayment",
    "municipal_taxes",
    "education",
    "subscription",
]


class Command(BaseCommand):
    help = "Compare BBPS operators: DB vs Mobikwik API per category"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fetch-mobikwik",
            action="store_true",
            help="Call Mobikwik API to get operator count per category (requires MOBIKWIK_BBPS_* configured)",
        )

    def handle(self, *args, **options):
        from portal.models import BBPSOperator
        from portal.services.bbps_operators_loader import load_bbps_operators_from_db

        fetch_mobikwik = options.get("fetch_mobikwik", False)
        mobikwik_counts = {}
        if fetch_mobikwik:
            from portal.services.bbps_service import BBPSService
            bbps = BBPSService(vendor="mobikwik")
            if not bbps.is_available():
                self.stdout.write(self.style.WARNING(
                    "Mobikwik BBPS not configured or disabled. Skipping Mobikwik API fetch. "
                    "Set MOBIKWIK_BBPS_* in .env and use --fetch-mobikwik to compare."
                ))
            else:
                for cat in PARKPE_CATEGORIES:
                    cat_param = cat.upper().replace(" ", "_")
                    result = bbps.get_operators(category=cat_param)
                    ops = result.get("operators") or []
                    mobikwik_counts[cat] = len(ops) if isinstance(ops, list) else 0

        # DB counts (bbps_enabled + is_active)
        self.stdout.write("\n--- BBPS operators: DB vs Mobikwik (per category) ---\n")
        total_db = 0
        for cat in PARKPE_CATEGORIES:
            cat_upper = cat.upper().replace(" ", "_")
            db_ops = load_bbps_operators_from_db(bbps_enabled_only=True, category=cat_upper)
            db_count = len(db_ops)
            total_db += db_count
            mobikwik_count = mobikwik_counts.get(cat, "–")
            if mobikwik_count != "–":
                diff = db_count - mobikwik_count
                diff_str = f"  (diff: {diff:+d})" if diff != 0 else ""
                self.stdout.write(
                    f"  {cat_upper:20}  DB: {db_count:4}   Mobikwik API: {mobikwik_count:4}{diff_str}"
                )
            else:
                self.stdout.write(f"  {cat_upper:20}  DB: {db_count:4}   Mobikwik API: – (use --fetch-mobikwik to fetch)")

        self.stdout.write(f"\n  {'TOTAL':20}  DB: {total_db:4}")
        self.stdout.write("")
        if total_db == 0:
            self.stdout.write(self.style.WARNING(
                "No operators in DB. Load from Excel: python manage.py load_bbps_operators\n"
                "Ensure Mobikwik/Operators.xlsx exists (get latest from Mobikwik if needed)."
            ))
        else:
            self.stdout.write(
                "Operators in our app come from DB (portal_bbps_operator), loaded via:\n"
                "  python manage.py load_bbps_operators   # reads Mobikwik/Operators.xlsx\n"
                "To match Mobikwik fully, get latest Operators.xlsx from Mobikwik and run the command again."
            )
