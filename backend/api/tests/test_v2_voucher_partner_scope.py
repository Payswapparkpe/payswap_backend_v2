"""
VAPT-006: Voucher v2 partner scoping regression tests.
Partner A issues voucher; Partner B gets 404 for balance; Partner A gets 200.
"""
import pytest
from decimal import Decimal
from rest_framework import status

from django.contrib.auth import get_user_model
from portal.models import (
    Role, Profile, Wallet, ResellerPartner, GiftVoucherBrand,
    GiftVoucher, APIKey,
)
from portal.services.api_key_service import APIKeyService
from portal.services.voucher_service import VoucherService
from portal.utils.voucher_utils import unformat_voucher_code, format_voucher_code

User = get_user_model()


def _create_partner_with_key(partner_code: str, voucher_permissions: dict):
    """Create ResellerPartner with wallet and API key. Returns (partner, plain_key)."""
    role, _ = Role.objects.get_or_create(
        code='admin',
        defaults={'name': 'Admin', 'category': 'b2b', 'hierarchy_level': 10}
    )
    # Username max_length=15; ensure unique
    uid = abs(hash(partner_code)) % 100000
    user = User.objects.create_user(
        username=f'u{uid}'[:15],
        password='testpass123',
        role_code='admin',
        role=role,
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={
            'first_name': 'Partner',
            'email': f'{partner_code}@example.com',
            'phone': f'9198765{uid:04d}',  # unique per partner
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
        partner_code=partner_code,
        defaults={
            'company_name': f'Partner {partner_code}',
            'contact_person': 'Contact',
            'email': f'{partner_code}@example.com',
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
        key_name=f'Key {partner_code}',
        key_type='TEST',
        permissions=voucher_permissions,
        created_by=user,
    )
    return partner, plain_key


@pytest.mark.django_db
class TestV2VoucherPartnerScope:
    """Partner A can access only vouchers they issued; Partner B gets 404."""

    def test_partner_b_cannot_access_partner_a_voucher_balance(self, api_client):
        """Partner A issues voucher; Partner B gets 404 on balance; Partner A gets 200."""
        perms_issue_balance = {
            'voucher': {'issue': True, 'balance': True},
        }
        perms_balance_only = {
            'voucher': {'balance': True},
        }
        partner_a, key_a = _create_partner_with_key(
            'PARTNER_A_SCOPE', perms_issue_balance
        )
        partner_b, key_b = _create_partner_with_key(
            'PARTNER_B_SCOPE', perms_balance_only
        )

        brand = GiftVoucherBrand.objects.create(
            brand_code='SCOPEBRAND',
            brand_name='Scope Test Brand',
            status='ACTIVE',
            onboarding_status='APPROVED',
        )
        # Issue voucher via service with Partner A in metadata (avoids issue API / role setup)
        issuer_user = partner_a.wallet.user
        voucher_service = VoucherService()
        result = voucher_service.issue_single_voucher(
            brand_id=brand.id,
            amount=Decimal('100.00'),
            recipient_email='holder@example.com',
            metadata={
                'partner_id': partner_a.id,
                'partner_code': partner_a.partner_code,
            },
            created_by=issuer_user,
            issued_by=issuer_user,
            issuer_type='ADMIN',
        )
        voucher_code = result.get('voucher_code')
        assert voucher_code, 'issue_single_voucher must return voucher_code'

        raw_code = unformat_voucher_code(voucher_code)
        balance_url = f'/api/v2/vouchers/{raw_code}/balance/'

        # Partner B: must get 404 (voucher belongs to A)
        api_client.credentials(HTTP_X_API_KEY=key_b)
        balance_b = api_client.get(balance_url)
        assert balance_b.status_code == status.HTTP_404_NOT_FOUND, (
            f'Partner B must get 404 for Partner A voucher; got {balance_b.status_code}'
        )

        # Partner A: must get 200
        api_client.credentials(HTTP_X_API_KEY=key_a)
        balance_a = api_client.get(balance_url)
        assert balance_a.status_code == status.HTTP_200_OK, balance_a.json()
        balance_data = balance_a.json().get('data', {})
        assert balance_data.get('current_balance') == '100.00'
