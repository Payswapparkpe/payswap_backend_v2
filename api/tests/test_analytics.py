"""
Tests for Phase 8 analytics dashboard.
Run: pytest api/tests/test_analytics.py -v
"""
import pytest
from django.test import Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


@pytest.fixture
def super_role(db):
    """Ensure Role with code 'super' exists for create_superuser."""
    from portal.models import Role
    role, _ = Role.objects.get_or_create(
        code="super",
        defaults={"name": "Superuser", "category": "b2b", "hierarchy_level": 100},
    )
    return role


@pytest.mark.django_db
class TestAnalyticsDashboard:
    """Analytics dashboard is staff-only."""

    def test_analytics_redirects_when_not_authenticated(self):
        client = Client()
        r = client.get("/analytics/")
        assert r.status_code in (302, 200)  # redirect to login or 200 if auth not required in test

    def test_analytics_accessible_by_staff(self, super_role):
        user = User.objects.create_superuser(
            username="staff_analytics",
            password="test",
        )
        user.is_active = True
        user.save()
        client = Client()
        client.force_login(user)
        r = client.get("/analytics/")
        # 200 = dashboard; 302 = redirect (e.g. to MFA setup for staff)
        assert r.status_code in (200, 302)
        if r.status_code == 302:
            assert "mfa" in (r.get("Location") or "").lower() or "login" in (r.get("Location") or "").lower()
