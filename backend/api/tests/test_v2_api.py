"""
API v2 smoke tests: health and protected vendor endpoints.
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestV2PublicEndpoints:
    """V2 public endpoint coverage (AllowAny)."""

    def test_health_returns_200(self, api_client):
        """V2 health is public and returns 200."""
        response = api_client.get('/api/v2/health/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get('data', {}).get('version') == 'v2'
        assert data.get('data', {}).get('access_type') == 'external'

@pytest.mark.django_db
class TestV2ProtectedEndpoints:
    """V2 protected endpoint auth behavior."""

    def test_vendors_without_api_key_returns_401(self, api_client):
        """Protected endpoint without X-API-Key returns 401 or 403."""
        response = api_client.get('/api/v2/vendors/')
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_vendors_with_api_key_returns_200(self, api_client, partner_with_api_key):
        """Protected endpoint with valid X-API-Key returns 200."""
        partner, plain_key = partner_with_api_key
        api_client.credentials(HTTP_X_API_KEY=plain_key)
        response = api_client.get('/api/v2/vendors/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data.get('vendors', []), list)

    def test_vendors_with_bearer_api_key_returns_200(self, api_client, partner_with_api_key):
        """Protected endpoint with Authorization: Bearer <api_key> returns 200."""
        partner, plain_key = partner_with_api_key
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {plain_key}')
        response = api_client.get('/api/v2/vendors/')
        assert response.status_code == status.HTTP_200_OK
