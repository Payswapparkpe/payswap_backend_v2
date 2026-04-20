from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from api.connect.risk_controls import check_call_abuse, check_chat_abuse


class ConnectRiskControlsTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.factory = RequestFactory()

    def _request(self):
        req = self.factory.post("/api/connect/call/initiate/", {})
        req.META["REMOTE_ADDR"] = "1.2.3.4"
        req.META["HTTP_USER_AGENT"] = "pytest-agent"
        return req

    @override_settings(
        CONNECT_CALL_MAX_PER_USER_HOUR=2,
        CONNECT_CALL_MAX_PER_PHONE_HOUR=10,
        CONNECT_CALL_MAX_PER_FINGERPRINT_HOUR=2,
    )
    def test_call_abuse_blocks_after_user_threshold(self):
        req = self._request()
        first = check_call_abuse(req, scanner_user_id=10, scanner_phone="919876543210", owner_id=77, qr_code="A")
        second = check_call_abuse(req, scanner_user_id=10, scanner_phone="919876543210", owner_id=77, qr_code="A")
        third = check_call_abuse(req, scanner_user_id=10, scanner_phone="919876543210", owner_id=77, qr_code="A")

        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertFalse(third.allowed)
        self.assertIn("user_hourly_limit", third.reasons)

    @override_settings(
        CONNECT_CHAT_MAX_PER_THREAD_HOUR=2,
        CONNECT_CHAT_MAX_BODY_LENGTH=50,
        CONNECT_CHAT_MAX_PER_FINGERPRINT_HOUR=2,
    )
    def test_chat_abuse_blocks_thread_flood(self):
        req = self._request()
        first = check_chat_abuse(req, sender_user_id=1, thread_id=9, recipient_user_id=2, body="hi")
        second = check_chat_abuse(req, sender_user_id=1, thread_id=9, recipient_user_id=2, body="hello")
        third = check_chat_abuse(req, sender_user_id=1, thread_id=9, recipient_user_id=2, body="spam")

        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertFalse(third.allowed)
        self.assertIn("chat_thread_flood", third.reasons)

    @override_settings(CONNECT_CHAT_MAX_BODY_LENGTH=5)
    def test_chat_abuse_blocks_oversized_body(self):
        req = self._request()
        result = check_chat_abuse(req, sender_user_id=1, thread_id=10, recipient_user_id=2, body="message-too-long")
        self.assertFalse(result.allowed)
        self.assertIn("message_too_long", result.reasons)
