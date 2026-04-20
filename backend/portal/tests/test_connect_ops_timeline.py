from django.test import TestCase

from portal.services.connect_ops_timeline import fetch_connect_timeline


class ConnectOpsTimelineTests(TestCase):
    def test_requires_exactly_one_filter(self):
        self.assertEqual(fetch_connect_timeline(qr_code=None, user_id=None), [])
        self.assertEqual(fetch_connect_timeline(qr_code="any", user_id=1), [])

    def test_user_filter_returns_empty_when_no_data(self):
        out = fetch_connect_timeline(qr_code=None, user_id=999999, hours=24, limit=50)
        self.assertEqual(out, [])

    def test_qr_filter_returns_empty_when_no_data(self):
        out = fetch_connect_timeline(qr_code="nonexistent-qr-code-xyz", user_id=None, hours=24, limit=50)
        self.assertEqual(out, [])
