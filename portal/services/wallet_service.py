"""
Wallet Service
Handles wallet operations and transactions
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from portal.models import Wallet, WalletTransaction, User
from portal.mixins.service_base import ServiceBase


class WalletService(ServiceBase):
    """Service for managing wallet operations"""
    
    def get_or_create_wallet(self, user: User) -> Wallet:
        """
        Get existing wallet or create new one for user
        
        Args:
            user: User instance
            
        Returns:
            Wallet instance
        """
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={
                'balance': Decimal('0.00'),
                'currency': 'INR',
                'status': 'active'
            }
        )
        
        if created:
            self.log_info(
                operation='wallet_created',
                message=f'Wallet created for user {user.username}',
                user_id=user.id,
                extra_data={'wallet_id': wallet.id}
            )
        
        return wallet
    
    def get_balance(self, user: User) -> Decimal:
        """
        Get wallet balance for user
        
        Args:
            user: User instance
            
        Returns:
            Current balance as Decimal
        """
        wallet = self.get_or_create_wallet(user)
        return wallet.balance
    
    def add_funds(
        self,
        user: User,
        amount: Decimal,
        description: str,
        reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        performed_by: Optional[User] = None
    ) -> WalletTransaction:
        """
        Add funds to wallet
        
        Args:
            user: User whose wallet to credit
            amount: Amount to add
            description: Transaction description
            reference_id: Optional reference ID
            metadata: Optional transaction metadata
            performed_by: User performing the transaction
            
        Returns:
            Created WalletTransaction instance
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        try:
            # Atomicity: balance update + transaction record + audit history succeed or fail together.
            with transaction.atomic():
                wallet = self.get_or_create_wallet(user)
                # Isolation: lock row so concurrent requests serialize.
                wallet = Wallet.objects.select_for_update().get(id=wallet.id)
                balance_before = wallet.balance
                wallet.balance += amount
                wallet.save()
                # Create transaction record (same transaction)
                wallet_txn = WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='credit',
                    amount=amount,
                    balance_before=balance_before,
                    balance_after=wallet.balance,
                    reference=description or f"Credit {amount}",
                    description=description,
                    reference_id=reference_id,
                    metadata=metadata or {},
                    status='completed',
                    performed_by=performed_by or user
                )
                
                self.log_info(
                    operation='wallet_credit',
                    message=f'Added {amount} to wallet for {user.username}',
                    user_id=performed_by.id if performed_by else user.id,
                    extra_data={
                        'wallet_id': wallet.id,
                        'transaction_id': wallet_txn.id,
                        'amount': str(amount),
                        'balance_after': str(wallet.balance)
                    }
                )
                
                return wallet_txn
                
        except Exception as e:
            self.log_error(
                'wallet_credit',
                e,
                user_id=performed_by.id if performed_by else user.id
            )
            raise
    
    def deduct_funds(
        self,
        user: User,
        amount: Decimal,
        description: str,
        reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        performed_by: Optional[User] = None
    ) -> WalletTransaction:
        """
        Deduct funds from wallet
        
        Args:
            user: User whose wallet to debit
            amount: Amount to deduct
            description: Transaction description
            reference_id: Optional reference ID
            metadata: Optional transaction metadata
            performed_by: User performing the transaction
            
        Returns:
            Created WalletTransaction instance
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        try:
            # Atomicity: balance update + transaction record + audit history succeed or fail together.
            with transaction.atomic():
                wallet = self.get_or_create_wallet(user)
                # Isolation: lock row so concurrent requests serialize; validate after lock.
                wallet = Wallet.objects.select_for_update().get(id=wallet.id)
                # Consistency: balance must never go negative.
                if wallet.balance < amount:
                    raise ValueError(f"Insufficient balance. Available: {wallet.balance}, Required: {amount}")
                
                balance_before = wallet.balance
                wallet.balance -= amount
                wallet.save()
                
                # Create transaction record
                wallet_txn = WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type='debit',
                    amount=amount,
                    balance_before=balance_before,
                    balance_after=wallet.balance,
                    reference=description or f"Debit {amount}",
                    description=description,
                    reference_id=reference_id,
                    metadata=metadata or {},
                    status='completed',
                    performed_by=performed_by or user
                )
                
                self.log_info(
                    operation='wallet_debit',
                    message=f'Deducted {amount} from wallet for {user.username}',
                    user_id=performed_by.id if performed_by else user.id,
                    extra_data={
                        'wallet_id': wallet.id,
                        'transaction_id': wallet_txn.id,
                        'amount': str(amount),
                        'balance_after': str(wallet.balance)
                    }
                )
                
                return wallet_txn
                
        except Exception as e:
            self.log_error(
                'wallet_debit',
                e,
                user_id=performed_by.id if performed_by else user.id
            )
            raise
    
    def get_transaction_history(
        self,
        user: User,
        limit: int = 50,
        transaction_type: Optional[str] = None
    ) -> List[WalletTransaction]:
        """
        Get wallet transaction history
        
        Args:
            user: User instance
            limit: Maximum number of transactions to return
            transaction_type: Filter by type (CREDIT/DEBIT)
            
        Returns:
            List of WalletTransaction instances
        """
        wallet = self.get_or_create_wallet(user)
        
        queryset = WalletTransaction.objects.filter(wallet=wallet)
        
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        return queryset.order_by('-created_at')[:limit]
    
    def calculate_statistics(self, user: User) -> Dict[str, Any]:
        """
        Calculate wallet statistics
        
        Args:
            user: User instance
            
        Returns:
            Dictionary with wallet statistics
        """
        wallet = self.get_or_create_wallet(user)
        transactions = WalletTransaction.objects.filter(wallet=wallet)
        
        total_credits = sum(
            txn.amount for txn in transactions.filter(transaction_type='CREDIT')
        )
        total_debits = sum(
            txn.amount for txn in transactions.filter(transaction_type='DEBIT')
        )
        
        return {
            'current_balance': wallet.balance,
            'total_credits': total_credits,
            'total_debits': total_debits,
            'transaction_count': transactions.count(),
            'wallet_status': 'ACTIVE' if wallet.status == 'active' else 'INACTIVE'
        }
    
    def freeze_wallet(self, user: User, reason: str, performed_by: User) -> Wallet:
        """Freeze a wallet (prevent transactions). State change under lock in same transaction."""
        try:
            with transaction.atomic():
                wallet = self.get_or_create_wallet(user)
                wallet = Wallet.objects.select_for_update().get(id=wallet.id)
                wallet.status = 'frozen'
                wallet.save(update_fields=['status', 'updated_at'])
                self.log_warning(
                    operation='wallet_frozen',
                    message=f'Wallet frozen for {user.username}: {reason}',
                    user_id=performed_by.id,
                    extra_data={'wallet_id': wallet.id, 'reason': reason},
                )
                return wallet
        except Exception as e:
            self.log_error('wallet_freeze', e, user_id=performed_by.id)
            raise

    def unfreeze_wallet(self, user: User, performed_by: User) -> Wallet:
        """Unfreeze a wallet. State change under lock in same transaction."""
        try:
            with transaction.atomic():
                wallet = self.get_or_create_wallet(user)
                wallet = Wallet.objects.select_for_update().get(id=wallet.id)
                wallet.status = 'active'
                wallet.save(update_fields=['status', 'updated_at'])
                self.log_info(
                    operation='wallet_unfrozen',
                    message=f'Wallet unfrozen for {user.username}',
                    user_id=performed_by.id,
                    extra_data={'wallet_id': wallet.id},
                )
                return wallet
        except Exception as e:
            self.log_error('wallet_unfreeze', e, user_id=performed_by.id)
            raise
