from django.contrib.auth import get_user_model
from django.test import TestCase

from portal.models import DevicePushToken, NotificationDeliveryLog, Role
from portal.services.connect_chat_notifications import _maybe_queue_connect_push

User = get_user_model()


class ConnectChatPushIntentTests(TestCase):
    def setUp(self):
        Role.objects.get_or_create(
            code="customer",
            defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 1},
        )
        self.user = User.objects.create_user(username="push_u", password="pass12345", role_code="customer")

    def test_maybe_queue_writes_delivery_log_when_push_enabled(self):
        DevicePushToken.objects.create(
            user=self.user,
            token="unit_tok_connect_push",
            device_platform=DevicePushToken.PLATFORM_WEB,
        )
        with self.settings(NOTIFICATIONS_PUSH_ENABLED=True):
            _maybe_queue_connect_push(
                user=self.user,
                title="Connect · DL1",
                body="hello",
                meta={"thread_id": 9, "message_id": 10, "deep_link": "/connect/chats/9"},
            )
        log = NotificationDeliveryLog.objects.filter(user=self.user, channel="push", provider="connect_chat").first()
        self.assertIsNotNone(log)
        data = log.request_payload.get("data") or {}
        self.assertEqual(data.get("type"), "connect_chat")
        self.assertEqual(data.get("thread_id"), "9")
        self.assertEqual(data.get("message_id"), "10")
        self.assertIn("notification", log.request_payload)
