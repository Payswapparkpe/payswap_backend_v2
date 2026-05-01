from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from portal.models import Role


User = get_user_model()


class UserDeleteViewTests(TestCase):
    def setUp(self):
        Role.objects.create(
            name="Super Admin",
            code="super_admin",
            category="b2b",
            hierarchy_level=9,
            mfa_required=True,
        )
        Role.objects.create(
            name="Customer",
            code="customer",
            category="b2c",
            hierarchy_level=1,
            mfa_required=False,
        )
        self.admin = User.objects.create_user(
            username="superadmin",
            password="TestPass123!",
            role_code="super_admin",
            is_superuser=True,
            mfa_configured=True,
        )
        self.target = User.objects.create_user(
            username="referenced-user",
            password="TestPass123!",
            role_code="customer",
        )
        self.client.force_login(self.admin)

    def test_permanent_delete_integrity_error_redirects_with_message(self):
        with patch.object(User, "delete", side_effect=IntegrityError("referenced")):
            response = self.client.post(
                reverse("user_delete", kwargs={"user_id": self.target.pk}),
                {"action": "permanent"},
            )

        self.assertRedirects(
            response,
            reverse("user_detail", kwargs={"user_id": self.target.pk}),
            fetch_redirect_response=False,
        )
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("Permanent delete blocked" in message for message in messages)
        )
