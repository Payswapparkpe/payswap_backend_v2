"""
API v1 tests: internal endpoints (health, authentication).
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestV1Health:
    """V1 health and auth-required behavior."""

    def test_health_unauthenticated_returns_403(self, api_client):
        """Without auth, v1 health returns 403 (IsInternalUser denies)."""
        response = api_client.get('/api/v1/health/')
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)

    def test_health_authenticated_returns_200(self, api_client, internal_user):
        """With authenticated staff user, v1 health returns 200 and version v1."""
        api_client.force_authenticate(user=internal_user)
        response = api_client.get('/api/v1/health/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get('data', {}).get('version') == 'v1'
        assert data.get('data', {}).get('access_type') == 'internal'
