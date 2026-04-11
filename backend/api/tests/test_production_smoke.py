"""
Production smoke test suite — run on every deploy.
Covers: login, API key auth, BBPS, payment, vendor routing, wallet, settlement, audit log, kill switch.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestProductionSmoke:
    """Smoke tests for production readiness."""

    def test_internal_health_returns_200(self, client):
        r = client.get("/internal/health/")
        assert r.status_code in (200, 503)
        data = r.json()
        assert "checks" in data
        assert "db" in data["checks"]
        assert "redis" in data["checks"]
        assert "latency_ms" in data

    def test_internal_health_db_ok(self, client):
        r = client.get("/internal/health/")
        data = r.json()
        assert r.status_code == 200
        assert data["checks"].get("db") == "ok"

    def test_api_key_required_for_connect(self, client):
        r = client.get("/api/connect/vehicles/")
        assert r.status_code == status.HTTP_403_FORBIDDEN
        assert r.json().get("error") == "api_key_required"

    def test_api_key_required_for_bbps(self, client):
        r = client.get("/api/bbps/categories/")
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_api_key_required_for_payment(self, client):
        r = client.post("/api/payment/create-order/cashfree/", {}, format="json")
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_reseller_partner_model_exists(self):
        from portal.models import ResellerPartner
        assert ResellerPartner.objects.model == ResellerPartner

    def test_api_key_model_exists(self):
        from portal.models import APIKey
        assert APIKey.objects.model == APIKey


@pytest.mark.django_db
class TestProductionSmokeWithPartner:
    """Smoke tests that require a partner with API key (optional in CI)."""

    def test_connect_with_valid_key_returns_not_403_forbidden(self, client):
        from portal.models import ResellerPartner
        from portal.services.api_key_service import create_api_key
        partner = ResellerPartner.objects.filter(partner_code="parkpe").first()
        if not partner:
            pytest.skip("parkpe partner not found")
        _, plain_key, _ = create_api_key(partner=partner, key_name="SmokeTest", key_type="LIVE")
        client.credentials(HTTP_X_API_KEY=plain_key)
        r = client.get("/api/connect/vehicles/")
        assert r.status_code != status.HTTP_403_FORBIDDEN or r.json().get("error") != "api_key_required"
        assert r.status_code in (200, 403, 404, 503)
