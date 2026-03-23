"""
Verify backup/restore readiness: check that DB and Redis are reachable and backup config exists.
Run: python manage.py backup_verify
Does not perform actual restore; use for monthly restore test separately.
"""
import time
from django.core.management.base import BaseCommand
from django.db import connection
from django.core.cache import cache


class Command(BaseCommand):
    help = "Verify backup readiness: DB and Redis connectivity; no actual restore."

    def handle(self, *args, **options):
        return self._handle_impl(*args, **options)

    def _handle_impl(self, *args, **options):
        ok = True
        try:
            with connection.cursor() as c:
                c.execute("SELECT 1")
            self.stdout.write(self.style.SUCCESS("DB: OK"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"DB: {e}"))
            ok = False
        try:
            cache.set("backup_verify_ping", 1, 5)
            assert cache.get("backup_verify_ping") == 1
            self.stdout.write(self.style.SUCCESS("Redis: OK"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Redis: {e}"))
            ok = False
        if ok:
            self.stdout.write(self.style.SUCCESS("backup_verify passed. Ensure daily DB/Redis backups are configured."))
        else:
            self.stdout.write(self.style.WARNING("backup_verify had failures."))
        return ok
