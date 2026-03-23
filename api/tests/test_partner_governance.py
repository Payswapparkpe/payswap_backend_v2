"""
Partner & API key enforcement: no key -> 403, subscription DENY/allow, no internal bypass.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestParkPeRequiresKey:
    """Paths under /api/connect, /api/bbps, /api/payment, /api/voucher require X-API-Key."""

    def test_connect_without_key_returns_403(self, api_client):
        r = api_client.get("/api/connect/vehicles/")
        assert r.status_code == status.HTTP_403_FORBIDDEN
        data = r.json()
        assert data.get("error") == "api_key_required" or "api key" in (data.get("message") or "").lower()

    def test_bbps_without_key_returns_403(self, api_client):
        r = api_client.get("/api/bbps/")
        assert r.status_code == status.HTTP_403_FORBIDDEN
        data = r.json()
        assert data.get("error") == "api_key_required" or "api key" in (data.get("message") or "").lower()

    def test_payment_without_key_returns_403(self, api_client):
        r = api_client.post("/api/payment/initiate/", {}, format="json")
        assert r.status_code == status.HTTP_403_FORBIDDEN
        data = r.json()
        assert data.get("error") == "api_key_required" or "api key" in (data.get("message") or "").lower()

    def test_voucher_without_key_returns_403(self, api_client):
        r = api_client.get("/api/voucher/")
        assert r.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
        if r.status_code == 403:
            data = r.json()
            assert data.get("error") == "api_key_required" or "api key" in (data.get("message") or "").lower()


@pytest.mark.django_db
class TestSubscriptionEnforcement:
    """Subscription enforcement removed (api_management). Internal apps use API key only."""

    def test_connect_with_key_returns_ok_or_expected(self, api_client):
        from portal.models import ResellerPartner
        from portal.services.api_key_service import create_api_key

        partner, _ = ResellerPartner.objects.get_or_create(
            partner_code="test_sub_key",
            defaults={
                "company_name": "Test",
                "contact_person": "Test",
                "email": "test@test.com",
                "phone": "0000000000",
                "status": "ACTIVE",
                "onboarding_status": "APPROVED",
            },
        )
        _, plain_key, _ = create_api_key(partner=partner, key_name="Test", key_type="LIVE")
        api_client.credentials(HTTP_X_API_KEY=plain_key)
        r = api_client.get("/api/connect/vehicles/")
        # 200 or 400/404 (no vendor, no vehicles) - not 403 api_key_required
        assert r.status_code != 403 or "api_key" not in (r.json().get("message") or "").lower()


@pytest.mark.django_db
class TestInternalBypassBlocked:
    """No auth bypass: only APIKey (X-API-Key) is used; InternalAPIKey is not in request path."""

    def test_no_key_no_access(self, api_client):
        r = api_client.get("/api/connect/vehicles/", HTTP_X_APP="parkpe")
        assert r.status_code == status.HTTP_403_FORBIDDEN
        assert api_client.credentials() == {} or "X-API-Key" not in (api_client._credentials or {})
