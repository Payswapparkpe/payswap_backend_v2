"""
Create Super Admin role (all permissions), create sandeepsuda user, demote other admin users.
Run: python manage.py setup_super_admin

Note: The Super Admin portal UI (/dashboard/super-admin/, /super-admin/) has been removed;
these URLs now redirect to /dashboard/. This command only seeds the super_admin role and
permissions (used for access checks e.g. /internal/run-job/).
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import models
from portal.models import Role, Profile

User = get_user_model()

SUPER_ADMIN_EMAIL = "sandeep@payswap.in"
SUPER_ADMIN_USERNAME = "sandeepsuda"
SUPER_ADMIN_PASSWORD = "Admin@123"
SUPER_ADMIN_PHONE = "9461001200"  # 10-digit Indian mobile


class Command(BaseCommand):
    help = "Create Super Admin role with all permissions, create sandeepsuda user, demote other admin users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be done, do not change DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be saved."))

        # 1. Create or update Role super_admin with ALL permissions
        role, created = Role.objects.get_or_create(
            code="super_admin",
            defaults={
                "name": "Super Admin",
                "category": "b2b",
                "hierarchy_level": 999,
                "mfa_required": True,
            },
        )
        if not created:
            role.name = "Super Admin"
            role.category = "b2b"
            role.hierarchy_level = 999
            role.mfa_required = True
            if not dry_run:
                role.save()
        all_perms = list(Permission.objects.all())
        if not dry_run:
            role.default_permissions.set(all_perms)
        self.stdout.write(
            self.style.SUCCESS(f"Role super_admin: {'created' if created else 'updated'} with {len(all_perms)} permissions.")
        )

        # 2. Create or update user sandeepsuda
        try:
            user = User.objects.get(username=SUPER_ADMIN_USERNAME)
            user.email = SUPER_ADMIN_EMAIL
            user.set_password(SUPER_ADMIN_PASSWORD)
            user.role_code = "super_admin"
            user.role = role
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.email_verified = True
            if not dry_run:
                user.save()
            self.stdout.write(self.style.SUCCESS(f"User {SUPER_ADMIN_USERNAME} updated."))
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=SUPER_ADMIN_USERNAME,
                email=SUPER_ADMIN_EMAIL,
                password=SUPER_ADMIN_PASSWORD,
                role_code="super_admin",
            )
            if not dry_run:
                user.is_staff = True
                user.is_superuser = True
                user.email_verified = True
                user.save()
            self.stdout.write(self.style.SUCCESS(f"User {SUPER_ADMIN_USERNAME} created."))

        # Ensure Profile exists and has correct email/phone
        if not dry_run:
            import random
            placeholder_phone = f"91{random.randint(9000000000, 9999999999)}"
            while Profile.objects.filter(phone=placeholder_phone).exists():
                placeholder_phone = f"91{random.randint(9000000000, 9999999999)}"
            prof, prof_created = Profile.objects.get_or_create(
                user=user,
                defaults={
                    "first_name": "Sandeep",
                    "email": SUPER_ADMIN_EMAIL,
                    "phone": placeholder_phone,
                    "type": "individual",
                    "email_verified": True,
                    "phone_verified": False,
                },
            )
            if prof_created:
                self.stdout.write(self.style.SUCCESS("Profile created."))
            prof.email = SUPER_ADMIN_EMAIL
            prof.first_name = prof.first_name or "Sandeep"
            if not Profile.objects.filter(phone=SUPER_ADMIN_PHONE).exclude(user=user).exists():
                prof.phone = SUPER_ADMIN_PHONE
            else:
                self.stdout.write(self.style.WARNING(f"Phone {SUPER_ADMIN_PHONE} already in use; keeping placeholder. Update from profile page."))
            prof.save()
            self.stdout.write(self.style.SUCCESS(f"Profile: email={prof.email}, phone={prof.phone}"))
        else:
            self.stdout.write(self.style.SUCCESS("Profile would be created/updated."))

        # 3. Demote all other admin-type users (remove is_staff, is_superuser, set role to employee)
        employee_role = Role.objects.filter(code="employee").first()
        if not employee_role:
            self.stdout.write(self.style.WARNING("Employee role not found. Run python manage.py setup_roles first."))
        else:
            others = User.objects.filter(is_active=True).exclude(username=SUPER_ADMIN_USERNAME).filter(
                models.Q(is_staff=True) | models.Q(is_superuser=True) | models.Q(role_code="admin")
            )
            count = others.count()
            if not dry_run and count > 0:
                others.update(is_staff=False, is_superuser=False, role_code="employee", role=employee_role)
            self.stdout.write(
                self.style.SUCCESS(f"Demoted {count} other admin-type user(s) to employee (is_staff=False, is_superuser=False, role=employee).")
            )

        self.stdout.write(self.style.SUCCESS("Done. Login: username=%s password=%s" % (SUPER_ADMIN_USERNAME, SUPER_ADMIN_PASSWORD)))