"""
API v2 tests: public and partner endpoints (health, public, API key auth).
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestV2PublicEndpoints:
    """V2 public endpoints (AllowAny)."""

    def test_health_returns_200(self, api_client):
        """V2 health is public and returns 200."""
        response = api_client.get('/api/v2/health/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get('data', {}).get('version') == 'v2'
        assert data.get('data', {}).get('access_type') == 'external'

    def test_public_endpoint_returns_200(self, api_client):
        """V2 public endpoint returns 200."""
        response = api_client.get('/api/v2/public/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'v2' in str(data.get('data', {}))


@pytest.mark.django_db
class TestV2PartnerEndpoints:
    """V2 partner endpoint (HasAPIKey)."""

    def test_partner_without_api_key_returns_401(self, api_client):
        """Partner endpoint without X-API-Key returns 401 or 403."""
        response = api_client.get('/api/v2/partner/')
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_partner_with_api_key_returns_200(self, api_client, partner_with_api_key):
        """Partner endpoint with valid X-API-Key returns 200."""
        partner, plain_key = partner_with_api_key
        api_client.credentials(HTTP_X_API_KEY=plain_key)
        response = api_client.get('/api/v2/partner/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get('data', {}).get('authenticated') is True

    def test_partner_with_bearer_api_key_returns_200(self, api_client, partner_with_api_key):
        """Partner endpoint with Authorization: Bearer <api_key> returns 200."""
        partner, plain_key = partner_with_api_key
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {plain_key}')
        response = api_client.get('/api/v2/partner/')
        assert response.status_code == status.HTTP_200_OK
