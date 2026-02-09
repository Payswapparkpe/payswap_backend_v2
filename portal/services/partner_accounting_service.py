"""
Partner Accounting Service
Handles financial transactions, commission calculation, and settlements
"""
from typing import Optional, Dict, Any, List
from decimal import Decimal
from django.utils import timezone
from django.db import transaction, IntegrityError
from portal.models import (
    ResellerPartner, ResellerPartnerTransaction, ResellerPartnerPricing,
    ResellerPartnerSettlement, Service, ServiceCost, APIKey, Wallet, WalletTransaction
)
from portal.utils.logging_helper import get_logger

# Finance logger: writes to logs/finance.log (file-system; never affects DB transactions)
logger = get_logger('portal.finance')


class PartnerAccountingService:
    """Service for partner accounting and finance management"""

    @staticmethod
    def charge_partner_for_service(
        partner: ResellerPartner,
        service: Service,
        amount: Decimal,
        api_key: Optional[APIKey] = None,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """
        Charge partner wallet for using a service.
        When reference_id is set: DB unique (partner, reference_id) for REVENUE ensures
        at most one charge per reference_id; create REVENUE PENDING first (reserve), then
        debit wallet, then COMPLETED. On IntegrityError return existing without debiting.
        Wallet debit, WalletTransaction, and ResellerPartnerTransaction are in one atomic block.
        """
        if not partner.wallet:
            logger.error(
                f'Partner {partner.company_name} has no wallet',
                extra_data={'partner_id': partner.id}
            )
            raise ValueError(f"Partner {partner.company_name} has no wallet")

        try:
            pricing = ResellerPartnerPricing.objects.get(
                partner=partner,
                service=service,
                is_active=True
            )
        except ResellerPartnerPricing.DoesNotExist:
            logger.error(
                f'No pricing found for partner {partner.company_name} and service {service.name}',
                extra_data={'partner_id': partner.id, 'service_id': service.id}
            )
            raise ValueError(f"No pricing configuration found for service {service.name}")

        # When reference_id is set: Option A - create REVENUE first to reserve reference_id (DB unique).
        # Only one request can create; others get IntegrityError and return existing without debiting.
        if reference_id and reference_id.strip():
            return PartnerAccountingService._charge_with_reference_id(
                partner=partner,
                service=service,
                amount=amount,
                api_key=api_key,
                reference_id=reference_id.strip(),
                description=description or f'Service usage: {service.name}',
                metadata=metadata or {},
            )

        # No reference_id: single atomic block; create REVENUE ourselves to avoid record_transaction double-debit
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(id=partner.wallet_id)
            if wallet.balance < amount:
                logger.warning(
                    f'Insufficient balance for partner {partner.company_name}: {wallet.balance} < {amount}',
                    extra_data={
                        'partner_id': partner.id,
                        'wallet_balance': str(wallet.balance),
                        'required_amount': str(amount)
                    }
                )
                return None, False

            balance_before = wallet.balance
            wallet.balance -= amount
            wallet.save(update_fields=['balance'])
            balance_after = wallet.balance

            ref_text = f"Service Usage: {service.name} - N/A"
            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type='debit',
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference=ref_text,
                reference_id=reference_id,
                status='completed'
            )

            partner_transaction = ResellerPartnerTransaction.objects.create(
                partner=partner,
                service=service,
                api_key=api_key,
                transaction_type='REVENUE',
                amount=amount,
                currency='INR',
                reference_id=reference_id,
                status='COMPLETED',
                description=description or f'Service usage: {service.name}',
                metadata=metadata or {},
            )

        PartnerAccountingService._ensure_commission_for_revenue(
            partner=partner,
            service=service,
            amount=amount,
            reference_id=reference_id or str(partner_transaction.id),
            api_key=api_key,
            metadata=metadata or {},
        )

        logger.info(
            f'Partner charged for service: {partner.company_name} - {service.name} - {amount}',
            extra_data={
                'partner_id': partner.id,
                'service_id': service.id,
                'amount': str(amount),
                'transaction_id': partner_transaction.id
            }
        )
        return partner_transaction, True

    @staticmethod
    def _charge_with_reference_id(
        partner: ResellerPartner,
        service: Service,
        amount: Decimal,
        api_key: Optional[APIKey],
        reference_id: str,
        description: str,
        metadata: Dict[str, Any],
    ) -> tuple:
        """
        Charge with reference_id: create REVENUE PENDING first (reserves reference_id via DB unique).
        If IntegrityError, another request already reserved -> return existing without debiting.
        One atomic block: reserve or return existing; lock wallet; check balance; debit; WalletTransaction; COMPLETED.
        """
        with transaction.atomic():
            # Reserve reference_id by creating REVENUE PENDING; DB unique prevents double-create
            try:
                partner_txn = ResellerPartnerTransaction.objects.create(
                    partner=partner,
                    service=service,
                    api_key=api_key,
                    transaction_type='REVENUE',
                    amount=amount,
                    currency='INR',
                    reference_id=reference_id,
                    status='PENDING',
                    description=description,
                    metadata=metadata,
                )
            except IntegrityError:
                # Another request already created REVENUE for this (partner, reference_id); return it
                existing = ResellerPartnerTransaction.objects.get(
                    partner=partner,
                    reference_id=reference_id,
                    transaction_type='REVENUE',
                )
                logger.info(
                    f'Idempotent charge: returning existing transaction for reference_id={reference_id}',
                    extra_data={'partner_id': partner.id, 'transaction_id': existing.id}
                )
                return existing, True

            # This request reserved; now debit wallet (lock prevents race on balance)
            wallet = Wallet.objects.select_for_update().get(id=partner.wallet_id)
            if wallet.balance < amount:
                partner_txn.status = 'FAILED'
                partner_txn.save(update_fields=['status'])
                logger.warning(
                    f'Insufficient balance for partner {partner.company_name}: {wallet.balance} < {amount}',
                    extra_data={
                        'partner_id': partner.id,
                        'wallet_balance': str(wallet.balance),
                        'required_amount': str(amount)
                    }
                )
                return None, False

            balance_before = wallet.balance
            wallet.balance -= amount
            wallet.save(update_fields=['balance'])
            balance_after = wallet.balance

            ref_text = f"Service Usage: {service.name} - {reference_id}"
            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type='debit',
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference=ref_text,
                reference_id=reference_id,
                status='completed'
            )

            partner_txn.status = 'COMPLETED'
            partner_txn.save(update_fields=['status'])

        # Commission (outside atomic so wallet lock is released; commission is separate credit)
        PartnerAccountingService._ensure_commission_for_revenue(
            partner=partner,
            service=service,
            amount=amount,
            reference_id=reference_id,
            api_key=api_key,
            metadata=metadata,
        )

        logger.info(
            f'Partner charged for service: {partner.company_name} - {service.name} - {amount}',
            extra_data={
                'partner_id': partner.id,
                'service_id': service.id,
                'amount': str(amount),
                'transaction_id': partner_txn.id
            }
        )
        return partner_txn, True

    @staticmethod
    def _ensure_commission_for_revenue(
        partner: ResellerPartner,
        service: Service,
        amount: Decimal,
        reference_id: str,
        api_key: Optional[APIKey] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create COMMISSION transaction and credit partner wallet when pricing has commission."""
        try:
            pricing = ResellerPartnerPricing.objects.get(
                partner=partner,
                service=service,
                is_active=True
            )
        except ResellerPartnerPricing.DoesNotExist:
            return
        commission_amount = pricing.calculate_commission(amount)
        if commission_amount <= 0:
            return
        commission_rate = pricing.commission_percentage if pricing.commission_type == 'REVENUE_SHARE' else None
        ResellerPartnerTransaction.objects.create(
            partner=partner,
            service=service,
            api_key=api_key,
            transaction_type='COMMISSION',
            amount=commission_amount,
            currency='INR',
            commission_amount=commission_amount,
            commission_rate=commission_rate,
            status='COMPLETED',
            reference_id=f"{reference_id}_COMM",
            description=f'Commission for transaction: {reference_id}',
            metadata=metadata or {}
        )
        commission_txn = ResellerPartnerTransaction.objects.filter(
            partner=partner,
            reference_id=f"{reference_id}_COMM"
        ).order_by('-created_at').first()
        if commission_txn and partner.wallet:
            PartnerAccountingService._update_partner_wallet(
                partner, commission_amount, 'credit', commission_txn
            )
    
    @staticmethod
    def record_transaction(
        partner: ResellerPartner,
        service: Optional[Service],
        transaction_type: str,
        amount: Decimal,
        base_amount: Optional[Decimal] = None,
        api_key: Optional[APIKey] = None,
        reference_id: Optional[str] = None,
        external_reference: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ResellerPartnerTransaction:
        """
        Record a financial transaction for a partner
        
        Args:
            partner: ResellerPartner instance
            service: Service instance (optional)
            transaction_type: Type of transaction (REVENUE, COMMISSION, etc.)
            amount: Transaction amount
            base_amount: Base amount before markup (optional)
            api_key: API key used (optional)
            reference_id: Reference ID (optional)
            external_reference: External reference (optional)
            description: Transaction description (optional)
            metadata: Additional metadata (optional)
        
        Returns:
            ResellerPartnerTransaction instance
        """
        # Get pricing configuration if service provided
        pricing = None
        commission_amount = Decimal('0.00')
        markup_amount = Decimal('0.00')
        commission_rate = None
        
        if service:
            try:
                pricing = ResellerPartnerPricing.objects.get(
                    partner=partner,
                    service=service,
                    is_active=True
                )
                
                # Calculate commission for REVENUE transactions
                if transaction_type == 'REVENUE':
                    commission_amount = pricing.calculate_commission(amount)
                    commission_rate = pricing.commission_percentage if pricing.commission_type == 'REVENUE_SHARE' else None
                    
                    # Calculate markup if base_amount provided
                    if base_amount:
                        markup_amount = amount - base_amount
                    else:
                        # Try to calculate from pricing
                        if pricing.pricing_type == 'PERCENTAGE':
                            markup_amount = amount * pricing.markup_percentage / 100
                        elif pricing.pricing_type == 'FIXED':
                            markup_amount = pricing.fixed_markup
                    
                    # Also create a COMMISSION transaction (separate from REVENUE)
                    if commission_amount > 0 and transaction_type == 'REVENUE':
                        ResellerPartnerTransaction.objects.create(
                            partner=partner,
                            service=service,
                            api_key=api_key,
                            transaction_type='COMMISSION',
                            amount=commission_amount,
                            currency='INR',
                            commission_amount=commission_amount,
                            commission_rate=commission_rate,
                            status='COMPLETED',
                            reference_id=f"{reference_id}_COMM",
                            description=f'Commission for transaction: {reference_id}',
                            metadata=metadata or {}
                        )
                        
                        # Get the commission transaction we just created
                        commission_txn = ResellerPartnerTransaction.objects.filter(
                            partner=partner,
                            reference_id=f"{reference_id}_COMM"
                        ).order_by('-created_at').first()
                        
                        if commission_txn:
                            # Update partner wallet with commission
                            PartnerAccountingService._update_partner_wallet(
                                partner, commission_amount, 'credit', commission_txn
                            )
            except ResellerPartnerPricing.DoesNotExist:
                pass
        
        # Create transaction
        partner_transaction = ResellerPartnerTransaction.objects.create(
            partner=partner,
            service=service,
            api_key=api_key,
            transaction_type=transaction_type,
            amount=amount,
            currency='INR',
            commission_amount=commission_amount,
            commission_rate=commission_rate,
            base_amount=base_amount,
            markup_amount=markup_amount,
            status='COMPLETED',
            reference_id=reference_id,
            external_reference=external_reference,
            description=description,
            metadata=metadata or {}
        )
        
        # Note: Commission wallet update is handled separately when creating COMMISSION transaction
        # Only update wallet for direct COMMISSION transactions (not auto-created ones from REVENUE)
        if transaction_type == 'COMMISSION' and commission_amount > 0:
            if not reference_id or (reference_id and not reference_id.endswith('_COMM')):
                PartnerAccountingService._update_partner_wallet(partner, commission_amount, 'credit', partner_transaction)
        
        # For REVENUE transactions, debit wallet (if not already debited by charge_partner_for_service)
        # This is a safety check - charge_partner_for_service should be called first
        if transaction_type == 'REVENUE' and service:
            # Check if wallet was already debited (by checking if there's a recent wallet transaction)
            if partner.wallet:
                recent_wallet_txn = WalletTransaction.objects.filter(
                    wallet=partner.wallet,
                    reference__icontains=reference_id or str(partner_transaction.id),
                    transaction_type='debit'
                ).first()
                
                # Only debit if not already debited
                if not recent_wallet_txn:
                    PartnerAccountingService._update_partner_wallet(partner, amount, 'debit', partner_transaction)
        
        logger.info(
            f'Partner transaction recorded: {partner.company_name} - {transaction_type} - {amount}',
            extra_data={
                'partner_id': partner.id,
                'transaction_id': partner_transaction.id,
                'transaction_type': transaction_type,
                'amount': str(amount),
                'commission_amount': str(commission_amount)
            }
        )
        
        return partner_transaction
    
    @staticmethod
    def _update_partner_wallet(
        partner: ResellerPartner,
        amount: Decimal,
        transaction_type: str,
        reference_transaction: ResellerPartnerTransaction,
    ) -> None:
        """
        Update partner wallet balance. Must run inside or as single atomic block.
        Uses select_for_update so balance update + WalletTransaction succeed or fail together.
        """
        if not partner.wallet:
            return
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(id=partner.wallet_id)
            balance_before = wallet.balance
            if transaction_type == 'credit':
                wallet.balance += amount
                balance_after = wallet.balance
            else:  # debit
                if wallet.balance < amount:
                    raise ValueError(
                        f"Insufficient partner wallet balance: {wallet.balance} < {amount}"
                    )
                wallet.balance -= amount
                balance_after = wallet.balance
            wallet.save(update_fields=['balance'])
            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type=transaction_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference=f"Partner Transaction #{reference_transaction.id}",
                status='completed',
            )

    # -------------------------------------------------------------------------
    # Manual partner wallet credit/debit (4-eye: call only from approval execution)
    # Protects against one-click irreversible money movement; requires approval flow.
    # -------------------------------------------------------------------------

    @staticmethod
    def manual_partner_wallet_credit(
        partner: ResellerPartner,
        amount: Decimal,
        reference_id: str,
        description: str,
        performed_by: Optional[Any] = None,
    ) -> ResellerPartnerTransaction:
        """
        Credit partner wallet (manual adjustment). Call ONLY after approval.
        Atomic: lock wallet, create ADJUSTMENT txn, update balance, create WalletTransaction.
        """
        if not partner.wallet:
            raise ValueError(f"Partner {partner.company_name} has no wallet")
        if amount <= 0:
            raise ValueError("Amount must be positive")

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(id=partner.wallet_id)
            balance_before = wallet.balance
            wallet.balance += amount
            wallet.save(update_fields=['balance'])
            balance_after = wallet.balance

            ref_text = f"Manual credit: {description} - {reference_id}"
            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type='credit',
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference=ref_text,
                reference_id=reference_id,
                status='completed',
            )

            partner_txn = ResellerPartnerTransaction.objects.create(
                partner=partner,
                service=None,
                api_key=None,
                transaction_type='ADJUSTMENT',
                amount=amount,
                currency='INR',
                reference_id=reference_id,
                status='COMPLETED',
                description=description,
                metadata={'manual_credit': True, 'performed_by_id': getattr(performed_by, 'id', None)},
            )

        logger.info(
            f'Manual partner wallet credit: {partner.company_name} - {amount} - ref={reference_id}',
            extra_data={'partner_id': partner.id, 'transaction_id': partner_txn.id},
        )
        return partner_txn

    @staticmethod
    def manual_partner_wallet_debit(
        partner: ResellerPartner,
        amount: Decimal,
        reference_id: str,
        description: str,
        performed_by: Optional[Any] = None,
    ) -> ResellerPartnerTransaction:
        """
        Debit partner wallet (manual adjustment). Call ONLY after approval.
        Atomic: lock wallet, check balance, create ADJUSTMENT txn, update balance, create WalletTransaction.
        """
        if not partner.wallet:
            raise ValueError(f"Partner {partner.company_name} has no wallet")
        if amount <= 0:
            raise ValueError("Amount must be positive")

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(id=partner.wallet_id)
            if wallet.balance < amount:
                raise ValueError(
                    f"Insufficient balance. Available: {wallet.balance}, Required: {amount}"
                )
            balance_before = wallet.balance
            wallet.balance -= amount
            wallet.save(update_fields=['balance'])
            balance_after = wallet.balance

            ref_text = f"Manual debit: {description} - {reference_id}"
            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type='debit',
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference=ref_text,
                reference_id=reference_id,
                status='completed',
            )

            partner_txn = ResellerPartnerTransaction.objects.create(
                partner=partner,
                service=None,
                api_key=None,
                transaction_type='ADJUSTMENT',
                amount=amount,
                currency='INR',
                reference_id=reference_id,
                status='COMPLETED',
                description=description,
                metadata={'manual_debit': True, 'performed_by_id': getattr(performed_by, 'id', None)},
            )

        logger.info(
            f'Manual partner wallet debit: {partner.company_name} - {amount} - ref={reference_id}',
            extra_data={'partner_id': partner.id, 'transaction_id': partner_txn.id},
        )
        return partner_txn

    @staticmethod
    def create_settlement(
        partner: ResellerPartner,
        period_start: timezone.datetime,
        period_end: timezone.datetime,
        created_by: Optional[Any] = None
    ) -> ResellerPartnerSettlement:
        """
        Create a settlement for a partner for a given period
        
        Args:
            partner: ResellerPartner instance
            period_start: Start of settlement period
            period_end: End of settlement period
            created_by: User creating the settlement
        
        Returns:
            ResellerPartnerSettlement instance
        """
        # Calculate totals from transactions
        transactions = ResellerPartnerTransaction.objects.filter(
            partner=partner,
            transaction_type='COMMISSION',
            status='COMPLETED',
            transaction_date__gte=period_start,
            transaction_date__lte=period_end
        )
        
        total_commission = sum(t.commission_amount for t in transactions)
        total_transactions = transactions.count()
        
        # Calculate total revenue
        revenue_transactions = ResellerPartnerTransaction.objects.filter(
            partner=partner,
            transaction_type='REVENUE',
            status='COMPLETED',
            transaction_date__gte=period_start,
            transaction_date__lte=period_end
        )
        total_revenue = sum(t.amount for t in revenue_transactions)
        
        # Generate settlement reference
        from portal.utils.user_utils import generate_username
        settlement_ref = f"STL{partner.partner_code}{timezone.now().strftime('%Y%m%d')}{generate_username('S')[:6]}"
        
        # Create settlement
        settlement = ResellerPartnerSettlement.objects.create(
            partner=partner,
            settlement_period_start=period_start,
            settlement_period_end=period_end,
            total_revenue=total_revenue,
            total_commission=total_commission,
            total_transactions=total_transactions,
            settlement_amount=total_commission,  # Settle commission
            currency='INR',
            status='PENDING',
            settlement_reference=settlement_ref,
            created_by=created_by
        )
        
        logger.info(
            f'Settlement created: {partner.company_name} - {settlement_ref}',
            user=created_by,
            extra_data={
                'partner_id': partner.id,
                'settlement_id': settlement.id,
                'settlement_reference': settlement_ref,
                'total_commission': str(total_commission)
            }
        )
        
        return settlement
    
    @staticmethod
    def process_settlement(
        settlement: ResellerPartnerSettlement,
        payment_method: str,
        payment_reference: str,
        processed_by: Any,
    ) -> ResellerPartnerSettlement:
        """
        Process a settlement (mark as completed). Call only after approval (4-eye).
        Atomic: lock settlement row, validate status PENDING, then update to PROCESSING then COMPLETED.
        """
        with transaction.atomic():
            settlement_locked = ResellerPartnerSettlement.objects.select_for_update().get(
                id=settlement.id
            )
            if settlement_locked.status != 'PENDING':
                raise ValueError(
                    f"Settlement {settlement.id} is not PENDING (current: {settlement_locked.status})"
                )
            settlement_locked.status = 'PROCESSING'
            settlement_locked.payment_method = payment_method
            settlement_locked.payment_reference = payment_reference
            settlement_locked.processed_by = processed_by
            settlement_locked.processed_at = timezone.now()
            settlement_locked.save(
                update_fields=[
                    'status', 'payment_method', 'payment_reference',
                    'processed_by', 'processed_at', 'updated_at',
                ]
            )
            settlement_locked.status = 'COMPLETED'
            settlement_locked.completed_at = timezone.now()
            settlement_locked.save(update_fields=['status', 'completed_at', 'updated_at'])
            settlement = settlement_locked
        logger.info(
            f'Settlement processed: {settlement.settlement_reference}',
            extra_data={
                'settlement_id': settlement.id,
                'settlement_reference': settlement.settlement_reference,
                'amount': str(settlement.settlement_amount),
                'processed_by_id': getattr(processed_by, 'id', None),
            },
        )
        return settlement
    
    @staticmethod
    def get_partner_summary(
        partner: ResellerPartner,
        start_date: Optional[timezone.datetime] = None,
        end_date: Optional[timezone.datetime] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive summary for a partner
        
        Args:
            partner: ResellerPartner instance
            start_date: Start date for summary (optional)
            end_date: End date for summary (optional)
        
        Returns:
            Dictionary with partner summary data
        """
        from django.db.models import Sum, Count, Avg, Q
        from datetime import timedelta
        
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        # Transaction summary
        transactions = ResellerPartnerTransaction.objects.filter(
            partner=partner,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )
        
        total_revenue = transactions.filter(transaction_type='REVENUE').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        total_commission = transactions.filter(transaction_type='COMMISSION').aggregate(
            total=Sum('commission_amount')
        )['total'] or Decimal('0.00')
        
        total_transactions = transactions.count()
        
        # Service-wise breakdown
        service_breakdown = transactions.values('service__name').annotate(
            revenue=Sum('amount', filter=Q(transaction_type='REVENUE')),
            commission=Sum('commission_amount', filter=Q(transaction_type='COMMISSION')),
            count=Count('id')
        )
        
        # API usage
        from portal.models import APIKeyUsageLog
        api_usage = APIKeyUsageLog.objects.filter(
            partner=partner,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        total_api_requests = api_usage.count()
        successful_requests = api_usage.filter(status_code__lt=400).count()
        success_rate = (successful_requests / total_api_requests * 100) if total_api_requests > 0 else 0
        
        # Wallet balance
        wallet_balance = partner.wallet.balance if partner.wallet else Decimal('0.00')
        
        # Pending settlements
        pending_settlements = ResellerPartnerSettlement.objects.filter(
            partner=partner,
            status='PENDING'
        ).aggregate(total=Sum('settlement_amount'))['total'] or Decimal('0.00')
        
        return {
            'partner': partner,
            'period': {
                'start': start_date,
                'end': end_date
            },
            'financial': {
                'total_revenue': total_revenue,
                'total_commission': total_commission,
                'wallet_balance': wallet_balance,
                'pending_settlements': pending_settlements,
                'net_earnings': total_commission - pending_settlements
            },
            'transactions': {
                'total': total_transactions,
                'revenue_count': transactions.filter(transaction_type='REVENUE').count(),
                'commission_count': transactions.filter(transaction_type='COMMISSION').count()
            },
            'services': list(service_breakdown),
            'api_usage': {
                'total_requests': total_api_requests,
                'successful_requests': successful_requests,
                'success_rate': round(success_rate, 2)
            }
        }
