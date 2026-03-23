"""
Reset MFA for a user identified by phone number (e.g. when OTP is not received and admin cannot login).
Run: python manage.py reset_mfa_for_phone 9461001200
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from portal.models import Profile

User = get_user_model()


class Command(BaseCommand):
    help = "Find user by phone (Profile) and reset MFA so they can login without MFA / set up again."

    def add_arguments(self, parser):
        parser.add_argument(
            "phone",
            type=str,
            help="Phone number (e.g. 9461001200 or 919461001200)",
        )

    def handle(self, *args, **options):
        raw = (options["phone"] or "").strip()
        if not raw:
            self.stdout.write(self.style.ERROR("Provide phone number: python manage.py reset_mfa_for_phone 9461001200"))
            return

        digits = "".join(c for c in raw if c.isdigit())
        search_phones = set()
        if digits.startswith("91") and len(digits) == 12:
            search_phones = {digits, digits[2:], f"+{digits}"}
        elif len(digits) == 10:
            search_phones = {digits, "91" + digits, f"+91{digits}"}
        else:
            search_phones = {raw, digits} if digits else {raw}
        search_phones = list(search_phones)

        profile = Profile.objects.filter(phone__in=search_phones).select_related("user").first()
        if not profile:
            self.stdout.write(
                self.style.ERROR(f"No Profile found with phone matching: {raw} (tried {search_phones})")
            )
            return

        user = profile.user
        self.stdout.write(f"Found user: {user.username} (id={user.id}), phone={profile.phone}")

        if not user.mfa_configured and not user.mfa_enabled:
            self.stdout.write(self.style.WARNING("MFA was already off. No change."))
            return

        user.mfa_enabled = False
        user.mfa_configured = False
        user.mfa_method = None
        user.totp_secret = None
        user.save(update_fields=["mfa_enabled", "mfa_configured", "mfa_method", "totp_secret"])
        self.stdout.write(self.style.SUCCESS(f"MFA reset for {user.username}. They can now sign in without OTP (or set up MFA again)."))
