"""
Pytest fixtures for API tests (v1 internal, v2 external/API key).
"""
import pytest
from decimal import Decimal
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model
from portal.models import Role, Profile, Wallet, ResellerPartner, Service
from portal.services.api_key_service import APIKeyService

User = get_user_model()


@pytest.fixture
def api_client():
    """DRF API client for request tests."""
    return APIClient()


@pytest.fixture
def internal_user(db):
    """Staff user for v1 internal API (IsInternalUser). Username max 15 chars."""
    role, _ = Role.objects.get_or_create(
        code='admin',
        defaults={'name': 'Admin', 'category': 'b2b', 'hierarchy_level': 10}
    )
    user = User.objects.create_user(
        username='api_int_user',
        password='testpass123',
        role_code='admin',
        role=role,
        is_staff=True,
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={
            'first_name': 'Internal',
            'email': 'internal@example.com',
            'phone': '919876543210',
        }
    )
    return user


@pytest.fixture
def partner_with_api_key(db):
    """
    ResellerPartner with wallet and an active API key.
    Returns (partner, plain_api_key).
    """
    role, _ = Role.objects.get_or_create(
        code='admin',
        defaults={'name': 'Admin', 'category': 'b2b', 'hierarchy_level': 10}
    )
    user = User.objects.create_user(
        username='api_part_usr',
        password='testpass123',
        role_code='admin',
        role=role,
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={
            'first_name': 'Partner',
            'email': 'partner_api@example.com',
            'phone': '919876543211',
        }
    )
    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        defaults={
            'balance': Decimal('1000.00'),
            'currency': 'INR',
            'status': 'active',
        }
    )
    partner, _ = ResellerPartner.objects.get_or_create(
        partner_code='API_TEST_PARTNER',
        defaults={
            'company_name': 'API Test Partner',
            'contact_person': 'Contact',
            'email': 'apipartner@example.com',
            'phone': '91999999999',
            'business_type': 'PRIVATE_LTD',
            'address': 'Address',
            'status': 'ACTIVE',
            'onboarding_status': 'APPROVED',
            'wallet': wallet,
        }
    )
    if not partner.wallet_id:
        partner.wallet = wallet
        partner.save()
    api_key_obj, plain_key, _ = APIKeyService.create_api_key(
        partner=partner,
        key_name='Test API Key',
        key_type='TEST',
        created_by=user,
    )
    return partner, plain_key
