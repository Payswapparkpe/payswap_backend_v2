"""
Parkpe app integration smoke tests.
Hits main Parkpe-facing endpoints to confirm backend integration (runtime-config, auth login/profile).
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from portal.models import Role, Profile

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def parkpe_user(db):
    """User with profile for Parkpe login (email + password)."""
    role, _ = Role.objects.get_or_create(
        code="customer",
        defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 1},
    )
    user = User.objects.create_user(
        username="parkpe_tuser",
        password="parkpe_test_pass_123",
        role_code="customer",
        role=role,
        is_active=True,
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={
            "first_name": "Parkpe",
            "last_name": "Test",
            "email": "parkpe.test@example.com",
            "phone": "919876543210",
        },
    )
    return user


@pytest.mark.django_db
class TestParkpeRuntimeConfig:
    """Runtime config for Parkpe frontend (no auth)."""

    def test_runtime_config_returns_200(self, api_client):
        response = api_client.get("/api/v1/runtime-config/", {"app": "parkpe"})
        assert response.status_code == status.HTTP_200_OK

    def test_runtime_config_has_app_and_apis(self, api_client):
        response = api_client.get("/api/v1/runtime-config/", {"app": "parkpe"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"].get("app") == "parkpe"
        assert "apis" in data["data"]


@pytest.mark.django_db
class TestParkpeAuthLogin:
    """Parkpe auth login (email or phone + password)."""

    def test_login_requires_email_or_phone(self, api_client):
        response = api_client.post(
            "/api/auth/login",
            {"password": "any"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email or mobile" in (response.json().get("detail") or "")

    def test_login_with_valid_credentials_returns_200_and_tokens(self, api_client, parkpe_user):
        response = api_client.post(
            "/api/auth/login",
            {
                "email": "parkpe.test@example.com",
                "password": "parkpe_test_pass_123",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "token" in data
        assert data.get("user")

    def test_login_invalid_password_returns_401(self, api_client, parkpe_user):
        response = api_client.post(
            "/api/auth/login",
            {
                "email": "parkpe.test@example.com",
                "password": "wrong_password",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestParkpeAuthProfile:
    """Parkpe profile endpoint (requires JWT)."""

    def test_profile_requires_auth(self, api_client):
        response = api_client.get("/api/auth/profile")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_profile_returns_200_with_jwt(self, api_client, parkpe_user):
        # Obtain JWT via login
        login_resp = api_client.post(
            "/api/auth/login",
            {
                "email": "parkpe.test@example.com",
                "password": "parkpe_test_pass_123",
            },
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK
        data = login_resp.json()
        token = data.get("token")
        assert token
        # Call profile with Bearer token
        response = api_client.get(
            "/api/auth/profile",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert response.status_code == status.HTTP_200_OK
        profile_data = response.json()
        assert "email" in profile_data or "id" in profile_data
