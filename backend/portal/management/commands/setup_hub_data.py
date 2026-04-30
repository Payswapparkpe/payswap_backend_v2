"""
Seed default Hub RBAC data: Departments, Projects, and standard HubRoles.
Safe to run multiple times — uses get_or_create throughout.

Usage:
    python manage.py setup_hub_data
    python manage.py setup_hub_data --skip-roles   # skip role seeding
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission


class Command(BaseCommand):
    help = "Seed default Hub RBAC Departments, Projects, and standard Hub Roles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-roles",
            action="store_true",
            help="Seed only Departments and Projects; skip HubRole seeding",
        )

    def handle(self, *args, **options):
        from rbac.models import Department, Project, HubRole

        skip_roles = options.get("skip_roles", False)

        departments = [
            {"code": "finance", "name": "Finance", "description": "Financial operations, settlements, reconciliation"},
            {"code": "operations", "name": "Operations", "description": "Day-to-day platform operations and support"},
            {"code": "compliance", "name": "Compliance & Risk", "description": "KYC review, risk management, regulatory"},
            {"code": "tech", "name": "Technology", "description": "Engineering, DevOps, infrastructure"},
            {"code": "business", "name": "Business", "description": "Sales, partnerships, onboarding"},
            {"code": "support", "name": "Customer Support", "description": "Partner and user support tickets"},
        ]

        projects = [
            {"code": "parkpe", "name": "ParkPe", "description": "ParkPe consumer app and platform"},
            {"code": "payswap", "name": "Payswap", "description": "Payswap hub and partner platform"},
            {"code": "voucher", "name": "VoucherX", "description": "Gift voucher platform"},
            {"code": "bbps", "name": "BBPS", "description": "Bharat Bill Payment System integration"},
            {"code": "connect", "name": "Connect", "description": "Vehicle connectivity and QR scanning"},
        ]

        dept_objs = {}
        self.stdout.write(self.style.SUCCESS("Creating Departments..."))
        for d in departments:
            obj, created = Department.objects.get_or_create(
                code=d["code"],
                defaults={"name": d["name"], "description": d["description"], "is_active": True},
            )
            dept_objs[d["code"]] = obj
            status = "created" if created else "exists"
            self.stdout.write(f"  [{status}] {obj.code} — {obj.name}")

        proj_objs = {}
        self.stdout.write(self.style.SUCCESS("Creating Projects..."))
        for p in projects:
            obj, created = Project.objects.get_or_create(
                code=p["code"],
                defaults={"name": p["name"], "description": p["description"], "is_active": True},
            )
            proj_objs[p["code"]] = obj
            status = "created" if created else "exists"
            self.stdout.write(f"  [{status}] {obj.code} — {obj.name}")

        if skip_roles:
            self.stdout.write(self.style.WARNING("Skipping HubRole seeding (--skip-roles)."))
            self.stdout.write(self.style.SUCCESS("Done."))
            return

        # Standard role definitions: list of (dept_code, project_code, role_code, name, permission_codenames)
        # Permissions are portal app permissions — adjust if your Permission rows differ.
        VIEW_KYC = "portal.view_kyc"
        CHANGE_KYC = "portal.change_kyc"
        VIEW_WALLET = "portal.view_wallet"
        VIEW_USER = "portal.view_user"
        CHANGE_USER = "portal.change_user"
        VIEW_VOUCHER = "portal.view_giftvoucher"
        ADD_VOUCHER = "portal.add_giftvoucher"
        VIEW_PARTNER = "portal.view_resellerpartner"
        CHANGE_PARTNER = "portal.change_resellerpartner"
        VIEW_LOG = "portal.view_logentry"
        VIEW_DEPT = "rbac.view_department"
        VIEW_PROJ = "rbac.view_project"
        VIEW_HUBROLE = "rbac.view_hubrole"
        VIEW_ASSIGN = "rbac.view_userhubassignment"

        standard_roles = [
            # Finance > ParkPe
            ("finance", "parkpe", "finance_viewer", "Finance Viewer",
             [VIEW_WALLET, VIEW_USER, VIEW_LOG]),
            ("finance", "parkpe", "finance_manager", "Finance Manager",
             [VIEW_WALLET, VIEW_USER, CHANGE_USER, VIEW_LOG]),

            # Compliance > ParkPe
            ("compliance", "parkpe", "kyc_reviewer", "KYC Reviewer",
             [VIEW_KYC, CHANGE_KYC, VIEW_USER, VIEW_LOG]),
            ("compliance", "parkpe", "kyc_viewer", "KYC Viewer",
             [VIEW_KYC, VIEW_USER]),

            # Operations > ParkPe
            ("operations", "parkpe", "ops_viewer", "Operations Viewer",
             [VIEW_USER, VIEW_LOG]),
            ("operations", "parkpe", "ops_manager", "Operations Manager",
             [VIEW_USER, CHANGE_USER, VIEW_LOG, VIEW_KYC]),
            ("operations", "parkpe", "parking_owner", "Parking Owner",
             [VIEW_USER, CHANGE_USER, VIEW_LOG]),
            ("operations", "parkpe", "parking_manager", "Parking Manager",
             [VIEW_USER, VIEW_LOG]),
            ("operations", "parkpe", "parking_attendant", "Parking Attendant",
             [VIEW_USER]),

            # Business > ParkPe
            ("business", "parkpe", "partner_manager", "Partner Manager",
             [VIEW_PARTNER, CHANGE_PARTNER, VIEW_USER, VIEW_LOG]),
            ("business", "parkpe", "partner_viewer", "Partner Viewer",
             [VIEW_PARTNER, VIEW_USER]),

            # Tech > Payswap
            ("tech", "payswap", "platform_viewer", "Platform Viewer",
             [VIEW_USER, VIEW_LOG, VIEW_DEPT, VIEW_PROJ, VIEW_HUBROLE, VIEW_ASSIGN]),

            # Finance > Voucher
            ("finance", "voucher", "voucher_viewer", "Voucher Viewer",
             [VIEW_VOUCHER]),
            ("finance", "voucher", "voucher_issuer", "Voucher Issuer",
             [VIEW_VOUCHER, ADD_VOUCHER]),

            # Support > ParkPe
            ("support", "parkpe", "support_agent", "Support Agent",
             [VIEW_USER, VIEW_KYC, VIEW_LOG]),
        ]

        self.stdout.write(self.style.SUCCESS("Creating standard HubRoles..."))
        for dept_code, proj_code, role_code, role_name, perm_strings in standard_roles:
            dept = dept_objs.get(dept_code)
            proj = proj_objs.get(proj_code)
            if not dept or not proj:
                self.stdout.write(self.style.WARNING(f"  [skip] {role_code}: dept={dept_code} or proj={proj_code} not found"))
                continue

            role, created = HubRole.objects.get_or_create(
                department=dept,
                project=proj,
                code=role_code,
                defaults={"name": role_name, "is_active": True},
            )
            if not created:
                self.stdout.write(f"  [exists] {dept_code}/{proj_code}/{role_code}")
                continue

            # Attach permissions
            attached = 0
            for perm_str in perm_strings:
                app_label, codename = perm_str.split(".", 1)
                try:
                    perm = Permission.objects.get(content_type__app_label=app_label, codename=codename)
                    role.permissions.add(perm)
                    attached += 1
                except Permission.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"    [warn] Permission not found: {perm_str} (run migrations + setup_roles first)")
                    )

            self.stdout.write(f"  [created] {dept_code}/{proj_code}/{role_code} — {role_name} ({attached} perms)")

        self.stdout.write(self.style.SUCCESS("\n✓ setup_hub_data complete."))
        self.stdout.write("  Next step: Go to /dashboard/hub/assignments/ to assign users to these roles.")
