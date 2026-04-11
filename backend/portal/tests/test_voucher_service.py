"""
Unit tests for VoucherService: validation (issued_by, issuer_type, brand), issuance structure.
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

from portal.models import (
    Role, User, Profile, GiftVoucherBrand, VoucherClient,
)
from portal.services.voucher_service import VoucherService

User = get_user_model()


def _make_issuer_user(username_suffix=''):
    """Username must be max 15 chars (User.username max_length)."""
    n = abs(hash(str(username_suffix))) % 10000
    role, _ = Role.objects.get_or_create(
        code='admin',
        defaults={'name': 'Admin', 'category': 'b2b', 'hierarchy_level': 10}
    )
    username = f'vi{n:05d}'[:15]
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        role_code='admin',
        role=role,
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={
            'first_name': 'Issuer',
            'email': f'voucher_issuer_{n}@example.com',
            'phone': f'919876543{n % 100:02d}',
        }
    )
    return user


def _make_brand(active=True, onboarded=True, suffix=''):
    return GiftVoucherBrand.objects.create(
        brand_code=f'BRD{suffix}',
        brand_name=f'Test Brand {suffix}',
        status='ACTIVE' if active else 'INACTIVE',
        onboarding_status='APPROVED' if onboarded else 'PENDING',
    )


@pytest.mark.django_db
class TestVoucherServiceValidation:
    """Validation: issued_by, issuer_type, brand not found, brand not active."""

    def test_issue_requires_issued_by(self):
        """issue_single_voucher raises ValueError when issued_by is missing."""
        brand = _make_brand(suffix='_req')
        service = VoucherService()
        with pytest.raises(ValueError, match='issued_by is required'):
            service.issue_single_voucher(
                brand_id=brand.id,
                amount=Decimal('100.00'),
                issued_by=None,
                issuer_type='ADMIN',
            )

    def test_issue_requires_issuer_type(self):
        """issue_single_voucher raises ValueError when issuer_type is missing."""
        user = _make_issuer_user('_type')
        brand = _make_brand(suffix='_type')
        service = VoucherService()
        with pytest.raises(ValueError, match='issuer_type'):
            service.issue_single_voucher(
                brand_id=brand.id,
                amount=Decimal('100.00'),
                issued_by=user,
                issuer_type=None,
            )

    def test_issue_invalid_issuer_type(self):
        """issue_single_voucher raises ValueError for invalid issuer_type."""
        user = _make_issuer_user('_inv')
        brand = _make_brand(suffix='_inv')
        service = VoucherService()
        with pytest.raises(ValueError, match='Invalid issuer_type'):
            service.issue_single_voucher(
                brand_id=brand.id,
                amount=Decimal('100.00'),
                issued_by=user,
                issuer_type='INVALID',
            )

    def test_issue_brand_not_found(self):
        """issue_single_voucher raises ValueError when brand_id does not exist."""
        user = _make_issuer_user('_nf')
        service = VoucherService()
        with pytest.raises(ValueError, match='Brand not found'):
            service.issue_single_voucher(
                brand_id=999999,
                amount=Decimal('100.00'),
                issued_by=user,
                issuer_type='ADMIN',
            )

    def test_issue_brand_not_active(self):
        """issue_single_voucher raises ValueError when brand is not active."""
        user = _make_issuer_user('_ina')
        brand = _make_brand(active=False, onboarded=True, suffix='_ina')
        service = VoucherService()
        with pytest.raises(ValueError, match='not active'):
            service.issue_single_voucher(
                brand_id=brand.id,
                amount=Decimal('100.00'),
                issued_by=user,
                issuer_type='ADMIN',
            )

    def test_issue_brand_onboarding_not_complete(self):
        """issue_single_voucher raises ValueError when brand onboarding is not complete."""
        user = _make_issuer_user('_ob')
        brand = _make_brand(active=True, onboarded=False, suffix='_ob')
        service = VoucherService()
        with pytest.raises(ValueError, match='onboarding'):
            service.issue_single_voucher(
                brand_id=brand.id,
                amount=Decimal('100.00'),
                issued_by=user,
                issuer_type='ADMIN',
            )


@pytest.mark.django_db
class TestVoucherServiceIssuance:
    """Single voucher issuance returns expected structure."""

    def test_issue_single_voucher_returns_voucher_code_and_pin(self):
        """Successful issue_single_voucher returns dict with voucher_code and PIN."""
        user = _make_issuer_user('_iss')
        brand = _make_brand(suffix='_iss')
        service = VoucherService()
        result = service.issue_single_voucher(
            brand_id=brand.id,
            amount=Decimal('500.00'),
            issued_by=user,
            issuer_type='ADMIN',
        )
        assert isinstance(result, dict)
        assert 'voucher_code' in result
        assert 'pin' in result
        assert result.get('voucher_code')
        assert result.get('pin')
        assert result.get('original_amount') == Decimal('500.00')
        assert result.get('status') == 'ACTIVE'
