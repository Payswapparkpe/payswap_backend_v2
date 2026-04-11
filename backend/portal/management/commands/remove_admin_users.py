"""
Remove all users with role_code='admin' from the database.
Admin Role is NOT removed; only User accounts with type Admin are deleted.
Run: python manage.py remove_admin_users [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Remove all users with role_code='admin'. Admin role is kept in DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show how many users would be deleted, do not delete.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        qs = User.objects.filter(role_code="admin")
        count = qs.count()

        if count == 0:
            self.stdout.write(self.style.WARNING("No users with role_code='admin' found."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Dry run: would delete {count} user(s) with role_code='admin'.")
            )
            for u in qs[:10]:
                self.stdout.write(f"  - {u.username} (id={u.pk})")
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more.")
            return

        # Delete users (Profile and other CASCADE relations will be removed)
        deleted = 0
        for user in qs:
            username = user.username
            user.delete()
            deleted += 1
            self.stdout.write(f"Deleted user: {username}")

        self.stdout.write(self.style.SUCCESS(f"Removed {deleted} admin-type user(s). Admin role is unchanged in DB."))
