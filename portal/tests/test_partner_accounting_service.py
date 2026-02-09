"""
Unit tests for PartnerAccountingService: pricing, commission, charges, idempotency.
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction

from portal.models import (
    Role, User, Profile, Wallet, WalletTransaction,
    ResellerPartner, ResellerPartnerPricing, ResellerPartnerTransaction,
    Service,
)
from portal.services.partner_accounting_service import PartnerAccountingService

User = get_user_model()


def _make_user(username_suffix=''):
    """Username must be max 15 chars (User.username max_length)."""
    suffix = str(username_suffix) if username_suffix else ''
    try:
        n = int(suffix) if suffix.isdigit() else abs(hash(suffix)) % 10000
    except (ValueError, TypeError):
        n = abs(hash(suffix)) % 10000
    role, _ = Role.objects.get_or_create(
        code='admin',
        defaults={'name': 'Admin', 'category': 'b2b', 'hierarchy_level': 10}
    )
    username = f'pu{n:05d}'[:15]  # e.g. pu00001
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        role_code='admin',
        role=role,
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={
            'first_name': 'Test',
            'email': f'partner_test_{n}@example.com',
            'phone': f'919876543{n % 100:02d}',
        }
    )
    return user


def _make_wallet_for_user(user, balance=None):
    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        defaults={
            'balance': balance or Decimal('0.00'),
            'currency': 'INR',
            'status': 'active',
        }
    )
    if balance is not None and wallet.balance != balance:
        wallet.balance = balance
        wallet.save()
    return wallet


def _make_service(name_suffix=''):
    service, _ = Service.objects.get_or_create(
        code=f'SVC{name_suffix}',
        defaults={
            'name': f'Test Service {name_suffix}',
            'status': 'active',
            'is_enabled': True,
        }
    )
    return service


def _make_partner_with_wallet(user, balance=Decimal('1000.00'), partner_suffix=''):
    wallet = _make_wallet_for_user(user, balance=balance)
    partner, _ = ResellerPartner.objects.get_or_create(
        partner_code=f'PRT{partner_suffix}',
        defaults={
            'company_name': f'Partner {partner_suffix}',
            'contact_person': 'Contact',
            'email': f'partner{partner_suffix}@example.com',
            'phone': '91999999999',
            'business_type': 'PRIVATE_LTD',
            'address': 'Address',
            'status': 'ACTIVE',
            'onboarding_status': 'APPROVED',
            'wallet': wallet,
        }
    )
    if partner.wallet_id != wallet.id:
        partner.wallet = wallet
        partner.save()
    return partner


@pytest.mark.django_db
class TestResellerPartnerPricingCalculation:
    """Tiered pricing and commission calculation on ResellerPartnerPricing model."""

    def test_tiered_pricing_percentage(self):
        """Tiered pricing with percentage rate returns base + (base * rate/100)."""
        user = _make_user('_tier')
        partner = _make_partner_with_wallet(user, balance=Decimal('5000.00'), partner_suffix='_tier')
        service = _make_service('_tier')
        pricing = ResellerPartnerPricing.objects.create(
            partner=partner,
            service=service,
            pricing_type='TIERED',
            tiered_pricing=[
                {'min': 0, 'max': 1000, 'rate': 2.0, 'type': 'percentage'},
                {'min': 1000, 'max': 5000, 'rate': 1.5, 'type': 'percentage'},
            ],
            commission_type='REVENUE_SHARE',
            commission_percentage=Decimal('0'),
            is_active=True,
        )
        assert pricing.calculate_price(Decimal('500')) == Decimal('510.00')  # 500 + 2%
        assert pricing.calculate_price(Decimal('1500')) == Decimal('1522.50')  # 1500 + 1.5%

    def test_tiered_pricing_fixed_per_tier(self):
        """Tiered pricing with fixed rate adds rate to base."""
        user = _make_user('_tier2')
        partner = _make_partner_with_wallet(user, balance=Decimal('5000.00'), partner_suffix='_tier2')
        service = _make_service('_tier2')
        pricing = ResellerPartnerPricing.objects.create(
            partner=partner,
            service=service,
            pricing_type='TIERED',
            tiered_pricing=[
                {'min': 0, 'max': 1000, 'rate': 10, 'type': 'fixed'},
            ],
            commission_type='FIXED_COMMISSION',
            fixed_commission=Decimal('0'),
            is_active=True,
        )
        assert pricing.calculate_price(Decimal('500')) == Decimal('510.00')

    def test_commission_calculation_revenue_share(self):
        """REVENUE_SHARE: commission = transaction_amount * commission_percentage / 100."""
        user = _make_user('_rev')
        partner = _make_partner_with_wallet(user, balance=Decimal('1000.00'), partner_suffix='_rev')
        service = _make_service('_rev')
        pricing = ResellerPartnerPricing.objects.create(
            partner=partner,
            service=service,
            pricing_type='PERCENTAGE',
            markup_percentage=Decimal('1'),
            commission_type='REVENUE_SHARE',
            commission_percentage=Decimal('10.00'),
            is_active=True,
        )
        assert pricing.calculate_commission(Decimal('100.00')) == Decimal('10.00')

    def test_commission_calculation_fixed_commission(self):
        """FIXED_COMMISSION: commission = fixed_commission."""
        user = _make_user('_fix')
        partner = _make_partner_with_wallet(user, balance=Decimal('1000.00'), partner_suffix='_fix')
        service = _make_service('_fix')
        pricing = ResellerPartnerPricing.objects.create(
            partner=partner,
            service=service,
            pricing_type='FIXED',
            fixed_markup=Decimal('5'),
            commission_type='FIXED_COMMISSION',
            fixed_commission=Decimal('2.50'),
            is_active=True,
        )
        assert pricing.calculate_commission(Decimal('100.00')) == Decimal('2.50')

    def test_commission_zero_when_commission_amount_zero(self):
        """When commission_percentage is 0, calculate_commission returns 0."""
        user = _make_user('_zero')
        partner = _make_partner_with_wallet(user, balance=Decimal('1000.00'), partner_suffix='_zero')
        service = _make_service('_zero')
        pricing = ResellerPartnerPricing.objects.create(
            partner=partner,
            service=service,
            pricing_type='PERCENTAGE',
            markup_percentage=Decimal('1'),
            commission_type='REVENUE_SHARE',
            commission_percentage=Decimal('0'),
            is_active=True,
        )
        assert pricing.calculate_commission(Decimal('100.00')) == Decimal('0.00')


@pytest.mark.django_db
class TestPartnerAccountingCharge:
    """charge_partner_for_service and idempotency."""

    def test_charge_success_debits_wallet_and_creates_transaction(self):
        """Successful charge debits partner wallet and creates REVENUE transaction."""
        user = _make_user('_ch')
        partner = _make_partner_with_wallet(user, balance=Decimal('500.00'), partner_suffix='_ch')
        service = _make_service('_ch')
        ResellerPartnerPricing.objects.create(
            partner=partner,
            service=service,
            pricing_type='PERCENTAGE',
            markup_percentage=Decimal('0'),
            commission_type='REVENUE_SHARE',
            commission_percentage=Decimal('0'),
            is_active=True,
        )
        txn, success = PartnerAccountingService.charge_partner_for_service(
            partner=partner,
            service=service,
            amount=Decimal('100.00'),
            reference_id=None,
            description='Test charge',
        )
        assert success is True
        assert txn is not None
        assert txn.transaction_type == 'REVENUE'
        assert txn.amount == Decimal('100.00')
        partner.wallet.refresh_from_db()
        assert partner.wallet.balance == Decimal('400.00')

    def test_charge_insufficient_balance_returns_false(self):
        """Charge when balance < amount returns (None, False) and does not debit."""
        user = _make_user('_insuf')
        partner = _make_partner_with_wallet(user, balance=Decimal('50.00'), partner_suffix='_insuf')
        service = _make_service('_insuf')
        ResellerPartnerPricing.objects.create(
            partner=partner,
            service=service,
            pricing_type='PERCENTAGE',
            markup_percentage=Decimal('0'),
            commission_type='REVENUE_SHARE',
            commission_percentage=Decimal('0'),
            is_active=True,
        )
        txn, success = PartnerAccountingService.charge_partner_for_service(
            partner=partner,
            service=service,
            amount=Decimal('100.00'),
            reference_id=None,
        )
        assert success is False
        assert txn is None
        partner.wallet.refresh_from_db()
        assert partner.wallet.balance == Decimal('50.00')

    def test_charge_no_pricing_raises(self):
        """Charge when no pricing config raises ValueError."""
        user = _make_user('_noprice')
        partner = _make_partner_with_wallet(user, balance=Decimal('100.00'), partner_suffix='_noprice')
        service = _make_service('_noprice')
        with pytest.raises(ValueError, match='No pricing configuration'):
            PartnerAccountingService.charge_partner_for_service(
                partner=partner,
                service=service,
                amount=Decimal('10.00'),
                reference_id=None,
            )

    def test_charge_no_wallet_raises(self):
        """Partner with no wallet raises ValueError."""
        user = _make_user('_nowal')
        partner = _make_partner_with_wallet(user, balance=Decimal('100.00'), partner_suffix='_nowal')
        partner.wallet = None
        partner.save()
        service = _make_service('_nowal')
        ResellerPartnerPricing.objects.create(
            partner=partner,
            service=service,
            pricing_type='PERCENTAGE',
            markup_percentage=Decimal('0'),
            commission_type='REVENUE_SHARE',
            commission_percentage=Decimal('0'),
            is_active=True,
        )
        with pytest.raises(ValueError, match='has no wallet'):
            PartnerAccountingService.charge_partner_for_service(
                partner=partner,
                service=service,
                amount=Decimal('10.00'),
                reference_id=None,
            )

    def test_idempotent_charge_duplicate_reference_id(self):
        """Two charges with same reference_id: second returns existing transaction without double debit."""
        user = _make_user('_idem')
        partner = _make_partner_with_wallet(user, balance=Decimal('500.00'), partner_suffix='_idem')
        service = _make_service('_idem')
        ResellerPartnerPricing.objects.create(
            partner=partner,
            service=service,
            pricing_type='PERCENTAGE',
            markup_percentage=Decimal('0'),
            commission_type='REVENUE_SHARE',
            commission_percentage=Decimal('0'),
            is_active=True,
        )
        ref_id = 'idem-ref-001'
        txn1, success1 = PartnerAccountingService.charge_partner_for_service(
            partner=partner,
            service=service,
            amount=Decimal('50.00'),
            reference_id=ref_id,
            description='First',
        )
        assert success1 is True
        assert txn1 is not None
        balance_after_first = partner.wallet.balance
        partner.wallet.refresh_from_db()
        balance_after_first = partner.wallet.balance

        txn2, success2 = PartnerAccountingService.charge_partner_for_service(
            partner=partner,
            service=service,
            amount=Decimal('50.00'),
            reference_id=ref_id,
            description='Duplicate',
        )
        assert success2 is True
        assert txn2 is not None
        assert txn2.id == txn1.id
        partner.wallet.refresh_from_db()
        assert partner.wallet.balance == balance_after_first
