"""
VAPT-004: Per-phone OTP verify lockout tests.
After N failed attempts, verify_otp returns (False, "locked"); success resets counter.
"""
from django.test import TestCase
from django.core.cache import cache
from portal.services.otp_service import OTPService
from portal.utils.mfa_utils import store_otp_in_cache
from portal.utils.phone_utils import normalize_phone_number


class OTPLockoutTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_lockout_after_max_failures(self):
        """After OTP_VERIFY_FAIL_MAX failed attempts, verify_otp returns (False, 'locked')."""
        otp_service = OTPService()
        phone = "9876543210"
        normalized = normalize_phone_number(phone)
        # Store correct OTP so we can test success resets later
        store_otp_in_cache(normalized, "123456", 300)
        # Fail N times with wrong OTP
        for _ in range(otp_service.OTP_VERIFY_FAIL_MAX):
            ok, reason = otp_service.verify_otp(phone, "000000")
            self.assertFalse(ok)
            self.assertIsNone(reason)
        # Next attempt should be locked
        ok, reason = otp_service.verify_otp(phone, "123456")
        self.assertFalse(ok)
        self.assertEqual(reason, "locked")

    def test_success_resets_lockout_counter(self):
        """Successful verification resets the failure counter."""
        otp_service = OTPService()
        phone = "9876543210"
        normalized = normalize_phone_number(phone)
        store_otp_in_cache(normalized, "123456", 300)
        # Few failures
        for _ in range(3):
            otp_service.verify_otp(phone, "000000")
        # Success
        ok, reason = otp_service.verify_otp(phone, "123456")
        self.assertTrue(ok)
        self.assertIsNone(reason)
        # Counter reset: next wrong attempt is not locked (only 1 fail)
        ok, reason = otp_service.verify_otp(phone, "000000")
        self.assertFalse(ok)
        self.assertIsNone(reason)
