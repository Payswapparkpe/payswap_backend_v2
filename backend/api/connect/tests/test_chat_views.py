from django.utils import timezone
from rest_framework.test import APIClient
from django.test import TestCase

from portal.models import User, Profile, Role, Vehicle, VehicleQRCode, ConnectThread, ConnectMessage, UserNotification


class ConnectChatViewsTests(TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        Role.objects.get_or_create(
            code="customer",
            defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 1},
        )
        self.owner = User.objects.create_user(
            username="owner_chat",
            password="pass12345",
            role_code="customer",
        )
        self.scanner = User.objects.create_user(
            username="scanner_chat",
            password="pass12345",
            role_code="customer",
        )
        Profile.objects.get_or_create(
            user=self.owner,
            defaults={"phone": "9999990001", "email": "owner_chat@example.com"},
        )
        Profile.objects.get_or_create(
            user=self.scanner,
            defaults={"phone": "9999990002", "email": "scanner_chat@example.com"},
        )
        self.vehicle = Vehicle.objects.create(
            user=self.owner,
            connect_scope=Vehicle.SCOPE_CONSUMER,
            vehicle_type="four_wheeler",
            registration_number="DL01AA1111",
            is_primary=True,
        )
        self.thread = ConnectThread.objects.create(vehicle=self.vehicle, scanner_user=self.scanner)

    def test_mark_read_updates_seen_state(self):
        msg = ConnectMessage.objects.create(
            thread=self.thread,
            sender=self.owner,
            message_type="text",
            body="hello",
        )
        self.client.force_authenticate(user=self.scanner)
        res = self.client.post(f"/api/connect/chat/threads/{self.thread.id}/mark-read/", {}, format="json")
        self.assertEqual(res.status_code, 200)
        self.thread.refresh_from_db()
        msg.refresh_from_db()
        self.assertGreaterEqual(self.thread.scanner_last_read_message_id, msg.id)
        self.assertEqual(msg.delivery_status, "seen")
        self.assertIsNotNone(msg.seen_at)

    def test_thread_settings_patch(self):
        self.client.force_authenticate(user=self.owner)
        res = self.client.patch(
            f"/api/connect/chat/threads/{self.thread.id}/settings/",
            {"pinned": True, "muted": True},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.thread.refresh_from_db()
        self.assertTrue(self.thread.owner_pinned)
        self.assertTrue(self.thread.owner_muted)

    def test_block_endpoint_sets_other_profile_blocked_until(self):
        self.client.force_authenticate(user=self.owner)
        res = self.client.post(
            f"/api/connect/chat/threads/{self.thread.id}/block/",
            {"action": "block", "reason": "spam"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        scanner_profile = Profile.objects.get(user=self.scanner)
        self.assertIsNotNone(scanner_profile.connect_blocked_until)
        self.assertGreater(scanner_profile.connect_blocked_until, timezone.now())

    def test_thread_peer_display_name_other_party_first_name(self):
        Profile.objects.filter(user=self.owner).update(first_name="Rajesh")
        Profile.objects.filter(user=self.scanner).update(first_name="Amit")
        self.client.force_authenticate(user=self.owner)
        res_list = self.client.get("/api/connect/chat/threads/")
        self.assertEqual(res_list.status_code, 200)
        row = next(r for r in res_list.json() if r["id"] == self.thread.id)
        self.assertEqual(row["peer_display_name"], "Amit")
        res_detail = self.client.get(f"/api/connect/chat/threads/{self.thread.id}/")
        self.assertEqual(res_detail.status_code, 200)
        self.assertEqual(res_detail.json()["peer_display_name"], "Amit")

        self.client.force_authenticate(user=self.scanner)
        res_peer = self.client.get(f"/api/connect/chat/threads/{self.thread.id}/")
        self.assertEqual(res_peer.status_code, 200)
        self.assertEqual(res_peer.json()["peer_display_name"], "Rajesh")

    def test_new_message_creates_in_app_notification_for_peer(self):
        self.client.force_authenticate(user=self.owner)
        res = self.client.post(
            f"/api/connect/chat/threads/{self.thread.id}/messages/",
            {"message_type": "text", "body": "hello peer"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        n = UserNotification.objects.filter(user=self.scanner).first()
        self.assertIsNotNone(n)
        self.assertEqual(n.metadata.get("thread_id"), self.thread.id)
        self.assertEqual(n.metadata.get("type"), "connect_chat")

    def test_muted_thread_skips_in_app_notification(self):
        self.thread.scanner_muted = True
        self.thread.save(update_fields=["scanner_muted"])
        self.client.force_authenticate(user=self.owner)
        self.client.post(
            f"/api/connect/chat/threads/{self.thread.id}/messages/",
            {"message_type": "text", "body": "should not notify"},
            format="json",
        )
        self.assertFalse(UserNotification.objects.filter(user=self.scanner).exists())

    def test_attachment_persisted_without_data_url_in_response(self):
        tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        self.client.force_authenticate(user=self.owner)
        res = self.client.post(
            f"/api/connect/chat/threads/{self.thread.id}/messages/",
            {
                "message_type": "attachment",
                "body": "img.png",
                "metadata": {
                    "data_url": f"data:image/png;base64,{tiny_png}",
                    "file_name": "img.png",
                },
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        meta = res.json().get("metadata") or {}
        self.assertNotIn("data_url", meta)
        self.assertIn("storage_path", meta)
        self.assertIn("media_url", meta)

    def test_create_thread_own_vehicle_qr_returns_400(self):
        VehicleQRCode.objects.create(vehicle=self.vehicle, code="ownvehqr_test")
        self.client.force_authenticate(user=self.owner)
        res = self.client.post(
            "/api/connect/chat/threads/",
            {"qr_code": "ownvehqr_test"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("own vehicle", (res.json().get("detail") or "").lower())

    def test_create_thread_scanner_other_vehicle_ok(self):
        vehicle2 = Vehicle.objects.create(
            user=self.owner,
            connect_scope=Vehicle.SCOPE_CONSUMER,
            vehicle_type="four_wheeler",
            registration_number="DL02BB2222",
            is_primary=False,
        )
        VehicleQRCode.objects.create(vehicle=vehicle2, code="scanok_qr_test")
        self.client.force_authenticate(user=self.scanner)
        res = self.client.post(
            "/api/connect/chat/threads/",
            {"qr_code": "scanok_qr_test"},
            format="json",
        )
        self.assertIn(res.status_code, (200, 201))
        self.assertEqual(res.json().get("vehicle_id"), vehicle2.id)
