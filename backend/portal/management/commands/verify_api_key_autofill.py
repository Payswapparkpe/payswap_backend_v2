"""
Verify that API key autofill works: view context + test commands read from env.
Run: python manage.py verify_api_key_autofill
"""
from django.core.management.base import BaseCommand
from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Verify API key autofill: view passes key to template, commands read from env"

    def handle(self, *args, **options):
        self.stdout.write("=== API Key autofill verification ===\n")

        # 1) Config: is EXPLORER_DEFAULT_API_KEY loaded?
        try:
            from core.config import payswap_config
            raw = getattr(payswap_config, "EXPLORER_DEFAULT_API_KEY", None)
            if raw is not None and hasattr(raw, "get_secret_value"):
                key_from_config = raw.get_secret_value()
            else:
                key_from_config = (raw or "").strip() or None
        except Exception as e:
            key_from_config = None
            self.stdout.write(self.style.WARNING(f"Config check failed: {e}"))

        if key_from_config:
            self.stdout.write(self.style.SUCCESS(f"1. EXPLORER_DEFAULT_API_KEY in config: YES (length {len(key_from_config)})"))
        else:
            self.stdout.write(self.style.WARNING("1. EXPLORER_DEFAULT_API_KEY in config: NOT SET (set in .env to test autofill)"))

        # 2) test_all_api_responses: get_api_key_from_env()
        try:
            from portal.management.commands.test_all_api_responses import get_api_key_from_env
            cmd_key = get_api_key_from_env()
            if cmd_key:
                self.stdout.write(self.style.SUCCESS(f"2. test_all_api_responses get_api_key_from_env(): YES (length {len(cmd_key)})"))
            else:
                self.stdout.write(self.style.WARNING("2. test_all_api_responses get_api_key_from_env(): EMPTY (no key in env)"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"2. test_all_api_responses: {e}"))

        # 3) test_api_and_check_logs: _get_api_key_from_env()
        try:
            from portal.management.commands.test_api_and_check_logs import _get_api_key_from_env
            log_key = _get_api_key_from_env()
            if log_key:
                self.stdout.write(self.style.SUCCESS(f"3. test_api_and_check_logs _get_api_key_from_env(): YES (length {len(log_key)})"))
            else:
                self.stdout.write(self.style.WARNING("3. test_api_and_check_logs _get_api_key_from_env(): EMPTY"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"3. test_api_and_check_logs: {e}"))

        # 4) API Explorer view removed; autofill was for /api-explorer/ (no longer available)
        self.stdout.write(self.style.WARNING("4. API Explorer: removed (page no longer available)"))

        self.stdout.write("")
        if not key_from_config:
            self.stdout.write(self.style.WARNING("To see autofill: add EXPLORER_DEFAULT_API_KEY=your_psk_live_... to .env and restart."))
        self.stdout.write("")
