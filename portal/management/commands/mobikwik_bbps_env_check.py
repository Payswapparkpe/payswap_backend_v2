"""
Check which MOBIKWIK_BBPS_* env vars are set and what is still needed.
Does NOT print any secret values – only "set" / "not set" and required vs optional.
Usage: python manage.py mobikwik_bbps_env_check
"""
from django.core.management.base import BaseCommand


def _is_set(val) -> bool:
    if val is None:
        return False
    if hasattr(val, "get_secret_value"):
        val = val.get_secret_value()
    s = str(val).strip()
    return len(s) > 0 and s.lower() not in ("false", "none", "null")


class Command(BaseCommand):
    help = "Check MOBIKWIK_BBPS env vars (set/not set only; no values printed)"

    def handle(self, *args, **options):
        from core.config import payswap_config
        import os

        cfg = payswap_config

        # All MOBIKWIK_BBPS vars we care about
        vars_info = [
            ("MOBIKWIK_BBPS_ENABLED", True, "Enable integration"),
            ("MOBIKWIK_BBPS_CLIENT_ID", True, "Token API – Mobikwik gives this"),
            ("MOBIKWIK_BBPS_CLIENT_SECRET", True, "Token API – Mobikwik gives this"),
            ("MOBIKWIK_BBPS_BASE_URL", True, "UAT: https://alpha3.mobikwik.com"),
            ("MOBIKWIK_BBPS_ENVIRONMENT", False, "UAT or PRODUCTION"),
            ("MOBIKWIK_BBPS_USE_ENCRYPTION", False, "True for View Bill / Validation"),
            ("MOBIKWIK_BBPS_PUBLIC_KEY_PATH", False, "Path to public_key.pem from zip"),
            ("MOBIKWIK_BBPS_PUBLIC_KEY", False, "Or PEM string (if path not set)"),
            ("MOBIKWIK_BBPS_KEY_VERSION", False, "From zip README, e.g. 1.0"),
            ("MOBIKWIK_BBPS_PLAIN_JSON_UAT", False, "True = force plain JSON in UAT"),
            ("MOBIKWIK_BBPS_MERCHANT_ID", False, "Optional"),
            ("MOBIKWIK_BBPS_MEMBER_ID", False, "Balance Check – onboarded email"),
            ("MOBIKWIK_BBPS_AGENT_ID", False, "Validation & Recharge – agentId (UAT Postman)"),
            ("MOBIKWIK_BBPS_API_KEY", False, "Optional / legacy"),
            ("MOBIKWIK_BBPS_SECRET_KEY", False, "Optional / checksum"),
        ]

        # Read from config (pydantic may load from env)
        available = []
        missing_required = []
        missing_optional = []

        for var_name, required, desc in vars_info:
            val = getattr(cfg, var_name, None)
            if val is None and var_name.startswith("MOBIKWIK_BBPS_"):
                # Try os.environ for keys that might not be in config
                env_val = os.environ.get(var_name)
                if env_val is not None:
                    val = env_val
            is_set = _is_set(val)
            if is_set:
                available.append((var_name, desc))
            else:
                if required:
                    missing_required.append((var_name, desc))
                else:
                    missing_optional.append((var_name, desc))

        # Public key: either path or PEM
        key_path_set = _is_set(getattr(cfg, "MOBIKWIK_BBPS_PUBLIC_KEY_PATH", None))
        key_pem_set = _is_set(getattr(cfg, "MOBIKWIK_BBPS_PUBLIC_KEY", None))
        encryption_ok = key_path_set or key_pem_set
        if getattr(cfg, "MOBIKWIK_BBPS_USE_ENCRYPTION", False) and not encryption_ok:
            if ("MOBIKWIK_BBPS_PUBLIC_KEY_PATH", "Path to public_key.pem from zip") not in missing_required:
                missing_required.append(("MOBIKWIK_BBPS_PUBLIC_KEY_PATH or MOBIKWIK_BBPS_PUBLIC_KEY", "Required when USE_ENCRYPTION=True"))

        self.stdout.write("MOBIKWIK BBPS – env check (values nahi dikhaye, sirf set/not set)")
        self.stdout.write("=" * 60)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Available (set):"))
        for name, desc in available:
            self.stdout.write(f"  {name}")
            self.stdout.write(f"    -> {desc}")
        self.stdout.write("")
        if missing_required:
            self.stdout.write(self.style.ERROR("Missing (required):"))
            for name, desc in missing_required:
                self.stdout.write(f"  {name}")
                self.stdout.write(f"    -> {desc}")
            self.stdout.write("")
        if missing_optional:
            self.stdout.write(self.style.WARNING("Not set (optional):"))
            for name, desc in missing_optional:
                self.stdout.write(f"  {name}")
                self.stdout.write(f"    -> {desc}")
        # Public key file existence (path is relative to BASE_DIR like mobikwik client)
        key_path_val = getattr(cfg, "MOBIKWIK_BBPS_PUBLIC_KEY_PATH", None)
        if key_path_val and isinstance(key_path_val, str) and key_path_val.strip():
            from django.conf import settings
            key_path_resolved = key_path_val.strip()
            if not os.path.isabs(key_path_resolved):
                base = getattr(settings, "BASE_DIR", None)
                if base:
                    key_path_resolved = os.path.join(base, key_path_resolved)
            key_file_exists = os.path.isfile(key_path_resolved)
            if not key_file_exists and base and not os.path.isabs(key_path_val.strip()):
                parts = key_path_val.strip().replace("\\", "/").split("/")
                if parts and parts[0]:
                    alt = parts[0].lower() if parts[0][:1].isupper() else (parts[0][:1].upper() + (parts[0][1:] if len(parts[0]) > 1 else ""))
                    if alt != parts[0]:
                        alt_resolved = os.path.join(base, alt, *parts[1:])
                        if os.path.isfile(alt_resolved):
                            key_file_exists = True
                            key_path_resolved = alt_resolved
            self.stdout.write("")
            self.stdout.write("MOBIKWIK_BBPS_PUBLIC_KEY_PATH file:")
            self.stdout.write(f"  Env value: {key_path_val.strip()}")
            self.stdout.write(f"  Resolved:  {key_path_resolved}")
            if key_file_exists:
                self.stdout.write(self.style.SUCCESS("  File exists: YES"))
            else:
                self.stdout.write(self.style.ERROR("  File exists: NO (ye path par file nahi mili – folder name Mobikwik vs mobikwik check karo)"))
        # Key version – README in zip says 1.0
        kv = getattr(cfg, "MOBIKWIK_BBPS_KEY_VERSION", "1.0")
        self.stdout.write("")
        self.stdout.write("MOBIKWIK_BBPS_KEY_VERSION:")
        self.stdout.write(f"  Current: {kv!r}  (README in zip: 1.0 – galat ho to .env me 1.0 set karo)")

        self.stdout.write("")
        self.stdout.write("Summary:")
        if not missing_required:
            self.stdout.write(self.style.SUCCESS("  All required keys are set."))
        else:
            self.stdout.write(self.style.ERROR(f"  Abhi ye chahiye (required): {', '.join(n for n, _ in missing_required)}"))
        if getattr(cfg, "MOBIKWIK_BBPS_USE_ENCRYPTION", False) and not encryption_ok:
            self.stdout.write(self.style.WARNING("  Encryption ON hai but public key nahi mila – MOBIKWIK_BBPS_PUBLIC_KEY_PATH ya MOBIKWIK_BBPS_PUBLIC_KEY set karo."))
