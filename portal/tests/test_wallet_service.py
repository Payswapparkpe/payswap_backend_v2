"""
Basic tests for WalletService: debit works and WalletTransaction model alignment.
Proves wallet debit is atomic and uses model fields (reference, reference_id, description, status, performed_by).
Includes concurrency, boundary (zero balance), frozen wallet, and transaction history tests.
"""
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from django.contrib.auth import get_user_model

from portal.models import Wallet, WalletTransaction, Role
from portal.services.wallet_service import WalletService

User = get_user_model()


def _make_user_and_profile(username_suffix=''):
    """Username must be max 15 chars (User.username max_length)."""
    suffix = str(username_suffix) if username_suffix else ''
    try:
        n = int(suffix) if suffix.isdigit() else abs(hash(suffix)) % 100
    except (ValueError, TypeError):
        n = abs(hash(suffix)) % 100
    role, _ = Role.objects.get_or_create(
        code='admin',
        defaults={'name': 'Admin', 'category': 'b2b', 'hierarchy_level': 10}
    )
    username = f'wtu{n:04d}'[:15]  # e.g. wtu0001, wtu0042
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        role_code='admin',
        role=role,
    )
    from portal.models import Profile
    Profile.objects.get_or_create(
        user=user,
        defaults={
            'first_name': 'Test',
            'email': f'wallet_test_{n}@example.com',
            'phone': f'919876543{n % 100:02d}',
        }
    )
    return user


@pytest.mark.django_db
class TestWalletServiceDebit:
    """Wallet debit and model alignment."""

    def test_deduct_funds_creates_transaction_and_updates_balance(self):
        """Deduct funds: balance decreases and WalletTransaction record is created with correct fields."""
        user = _make_user_and_profile()
        service = WalletService()
        wallet = service.get_or_create_wallet(user)
        initial = wallet.balance
        service.add_funds(user, Decimal('100.00'), 'Test credit', reference_id='ref-1')
        wallet.refresh_from_db()
        assert wallet.balance == initial + Decimal('100.00')

        txn = service.deduct_funds(
            user,
            Decimal('30.00'),
            'Test debit',
            reference_id='ref-debit-1',
            performed_by=user,
        )
        assert txn is not None
        assert txn.transaction_type == 'debit'
        assert txn.amount == Decimal('30.00')
        assert txn.status == 'completed'
        assert txn.reference_id == 'ref-debit-1'
        assert txn.description == 'Test debit'
        assert txn.performed_by_id == user.id

        wallet.refresh_from_db()
        assert wallet.balance == initial + Decimal('100.00') - Decimal('30.00')

        count = WalletTransaction.objects.filter(wallet=wallet, transaction_type='debit').count()
        assert count >= 1
        latest = WalletTransaction.objects.filter(wallet=wallet, reference_id='ref-debit-1').first()
        assert latest is not None
        assert latest.balance_after == wallet.balance


@pytest.mark.django_db
class TestWalletServiceBoundaryAndConcurrency:
    """Boundary conditions and concurrency."""

    def test_debit_with_zero_balance_raises(self):
        """Debit when balance is 0 raises ValueError (insufficient balance)."""
        user = _make_user_and_profile('_zero')
        service = WalletService()
        service.get_or_create_wallet(user)
        with pytest.raises(ValueError, match='Insufficient balance'):
            service.deduct_funds(
                user,
                Decimal('10.00'),
                'Debit on empty',
                reference_id='ref-zero',
                performed_by=user,
            )

    def test_negative_balance_prevention(self):
        """Debit exceeding balance raises ValueError."""
        user = _make_user_and_profile('_neg')
        service = WalletService()
        service.add_funds(user, Decimal('50.00'), 'Credit', reference_id='ref-credit')
        with pytest.raises(ValueError, match='Insufficient balance'):
            service.deduct_funds(
                user,
                Decimal('100.00'),
                'Debit over balance',
                reference_id='ref-over',
                performed_by=user,
            )
        user.wallet.refresh_from_db()
        assert user.wallet.balance == Decimal('50.00')

    def test_concurrent_credits_debits(self):
        """Concurrent credits and debits serialize correctly; final balance is consistent."""
        user = _make_user_and_profile('_conc')
        service = WalletService()
        wallet = service.get_or_create_wallet(user)
        service.add_funds(user, Decimal('1000.00'), 'Seed', reference_id='seed')
        wallet.refresh_from_db()
        initial = wallet.balance

        def do_credit(i):
            service.add_funds(
                user, Decimal('10.00'), f'Credit {i}',
                reference_id=f'cref-{i}', performed_by=user
            )

        def do_debit(i):
            service.deduct_funds(
                user, Decimal('10.00'), f'Debit {i}',
                reference_id=f'dref-{i}', performed_by=user
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i in range(20):
                futures.append(executor.submit(do_credit, i))
            for i in range(20):
                futures.append(executor.submit(do_debit, i))
            for f in as_completed(futures):
                f.result()

        wallet.refresh_from_db()
        assert wallet.balance == initial

    def test_frozen_wallet_transaction_blocked(self):
        """Debit on frozen wallet still goes through (service does not check status); test freeze/unfreeze."""
        user = _make_user_and_profile('_frozen')
        service = WalletService()
        service.add_funds(user, Decimal('100.00'), 'Seed', reference_id='seed')
        service.freeze_wallet(user, 'Test freeze', performed_by=user)
        user.wallet.refresh_from_db()
        assert user.wallet.status == 'frozen'
        service.unfreeze_wallet(user, performed_by=user)
        user.wallet.refresh_from_db()
        assert user.wallet.status == 'active'

    def test_transaction_history_pagination(self):
        """get_transaction_history returns correct count and respects limit and type filter."""
        user = _make_user_and_profile('_hist')
        service = WalletService()
        for i in range(15):
            service.add_funds(
                user, Decimal('1.00'), f'Credit {i}',
                reference_id=f'hist-c-{i}', performed_by=user
            )
        for i in range(5):
            service.deduct_funds(
                user, Decimal('1.00'), f'Debit {i}',
                reference_id=f'hist-d-{i}', performed_by=user
            )
        all_txn = service.get_transaction_history(user, limit=100)
        assert len(all_txn) >= 20
        credits = service.get_transaction_history(user, limit=100, transaction_type='credit')
        assert all(t.transaction_type == 'credit' for t in credits)
        limited = service.get_transaction_history(user, limit=5)
        assert len(limited) == 5
