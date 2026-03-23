"""
Voucher Service - Core business logic for gift voucher operations
"""
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from portal.models import (
    GiftVoucherBrand, GiftVoucher, GiftVoucherTransaction,
    GiftVoucherOTP, GiftVoucherAuditLog, VoucherClient
)
from portal.services.voucher_client_service import VoucherClientService
from portal.utils.voucher_utils import (
    generate_unique_voucher_code, format_voucher_code, unformat_voucher_code,
    generate_pin, hash_pin, verify_pin, check_pin_history, validate_pin_format,
    generate_reference_number, mask_mobile_number, is_pin_blocked,
    calculate_pin_block_until, get_pin_block_duration_minutes
)
from portal.utils.voucher_encryption import encrypt_voucher_code, decrypt_voucher_code
from portal.utils.voucher_errors import (
    VOUCHER_NOT_FOUND, INVALID_PIN, PIN_LOCKED, INSUFFICIENT_BALANCE,
    VOUCHER_BLOCKED, VOUCHER_EXPIRED, INVALID_OTP, OTP_EXPIRED,
    OTP_MAX_ATTEMPTS, PIN_REUSED, INVALID_AMOUNT, MOBILE_NUMBER_REQUIRED,
    VOUCHER_ALREADY_REDEEMED, DUPLICATE_TRANSACTION, get_error_message, create_error_response
)
from portal.services.voucher_otp_service import VoucherOTPService
from portal.utils.phone_utils import normalize_phone_number
from portal.utils.logging_helper import get_logger
from portal.utils.voucher_logging import log_voucher_operation
from portal.utils.transaction_id import generate_transaction_id

logger = get_logger('portal.services.voucher')


class VoucherService:
    """Service for voucher operations"""
    
    def __init__(self):
        self.otp_service = VoucherOTPService()
        self.max_pin_retries = 3
        self.client_service = VoucherClientService()
    
    def issue_single_voucher(
        self,
        brand_id: int,
        amount: Decimal,
        mobile_number: Optional[str] = None,
        recipient_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[Any] = None,
        client_id: Optional[int] = None,
        issued_by: Optional[Any] = None,
        issuer_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Issue a single voucher.

        Args:
            brand_id: Brand ID
            amount: Voucher amount
            mobile_number: Optional mobile number for OTP-based redemption
            recipient_email: Optional recipient email (required when issuing via API; optional for admin)
            metadata: Optional metadata
            created_by: User who created the voucher
            client_id: Optional client ID (defaults to Payswap default client)
            issued_by: User who issued the voucher (required)
            issuer_type: Type of issuer - ADMIN/API_PARTNER/BRAND_OWNER (required)

        Returns:
            Dict with voucher details including voucher_code and PIN
        """
        try:
            # Validate issuer information
            if not issued_by:
                raise ValueError("issued_by is required")
            if not issuer_type:
                raise ValueError("issuer_type is required (ADMIN/API_PARTNER/BRAND_OWNER)")
            if issuer_type not in ['ADMIN', 'API_PARTNER', 'BRAND_OWNER']:
                raise ValueError("Invalid issuer_type. Must be ADMIN, API_PARTNER, or BRAND_OWNER")
            
            # Get brand
            try:
                brand = GiftVoucherBrand.objects.get(id=brand_id)
            except GiftVoucherBrand.DoesNotExist:
                raise ValueError("Brand not found")
            
            # Validate brand can issue vouchers (must be onboarded and active)
            if not brand.can_issue_vouchers():
                if not brand.is_onboarded():
                    raise ValueError("Brand onboarding is not complete. Please complete the onboarding process before issuing vouchers.")
                else:
                    raise ValueError("Brand is not active. Cannot issue vouchers.")
            
            # Get or create default client if client_id not provided
            if client_id:
                try:
                    client = VoucherClient.objects.get(id=client_id, brand=brand, status='ACTIVE')
                except VoucherClient.DoesNotExist:
                    raise ValueError("Client not found or inactive")
            else:
                # Get or create default Payswap client
                client = self.client_service.get_or_create_default_client(brand_id)
            
            # Normalize mobile number if provided
            normalized_mobile = None
            if mobile_number:
                try:
                    normalized_mobile = normalize_phone_number(mobile_number)
                except ValueError as e:
                    raise ValueError(f"Invalid mobile number: {str(e)}")
            
            # Generate issuer name
            issuer_name = None
            if hasattr(issued_by, 'username'):
                issuer_name = issued_by.username
            elif hasattr(issued_by, 'get_full_name'):
                issuer_name = issued_by.get_full_name()
            else:
                issuer_name = str(issued_by)
            
            # Generate voucher code and PIN
            voucher_code = generate_unique_voucher_code()
            pin = generate_pin()
            
            # Encrypt and hash
            voucher_code_hash = encrypt_voucher_code(voucher_code)
            pin_hash = hash_pin(pin)
            
            # Generate reference number
            reference_number = generate_reference_number()
            
            # Prepare metadata (store PIN encrypted for export purposes)
            from portal.utils.encryption import encrypt_data
            voucher_metadata = metadata.copy() if metadata else {}
            voucher_metadata['encrypted_pin'] = encrypt_data(pin)  # Store PIN encrypted for export
            if recipient_email:
                voucher_metadata['recipient_email'] = recipient_email
            
            # Create voucher
            with transaction.atomic():
                voucher = GiftVoucher.objects.create(
                    brand=brand,
                    client=client,
                    reference_number=reference_number,
                    voucher_code=voucher_code,
                    voucher_code_hash=voucher_code_hash,
                    pin_hash=pin_hash,
                    original_amount=amount,
                    current_balance=amount,
                    currency='INR',
                    status='ACTIVE',
                    mobile_number=normalized_mobile,
                    created_by=created_by,
                    issued_by=issued_by,
                    issuer_type=issuer_type,
                    issuer_name=issuer_name,
                    metadata=voucher_metadata
                )
                
                # Create issuance transaction
                GiftVoucherTransaction.objects.create(
                    voucher=voucher,
                    transaction_type='ISSUANCE',
                    transaction_amount=None,
                    balance_before=Decimal('0.00'),
                    balance_after=amount,
                    transaction_status='SUCCESS',
                    metadata={'reference_number': reference_number}
                )
            
            # Log operation
            user_id = issued_by.id if hasattr(issued_by, 'id') else None
            log_voucher_operation(
                operation='voucher_issued',
                log_level='INFO',
                message=f'Voucher issued successfully - Code: {format_voucher_code(voucher_code)}, Brand: {brand.brand_name}, Amount: {amount}',
                user_id=user_id,
                extra_data={
                    'voucher_id': voucher.id,
                    'brand_id': brand_id,
                    'brand_name': brand.brand_name,
                    'client_id': client.id,
                    'client_name': client.client_name,
                    'amount': str(amount),
                    'reference_number': reference_number,
                    'issued_by': issuer_name,
                    'issuer_type': issuer_type
                }
            )
            
            return {
                'voucher_id': voucher.id,
                'reference_number': reference_number,
                'voucher_code': format_voucher_code(voucher_code),
                'pin': pin,  # Only shown once during issuance
                'amount': str(amount),
                'currency': 'INR',
                'status': 'ACTIVE',
                'issued_at': voucher.issued_at.isoformat(),
                'mobile_number': mask_mobile_number(normalized_mobile) if normalized_mobile else None,
                'client_name': client.client_name,
                'client_code': client.client_code,
                'issued_by': issuer_name,
                'issuer_type': issuer_type
            }
            
        except Exception as e:
            user_id = issued_by.id if hasattr(issued_by, 'id') else None
            log_voucher_operation(
                operation='voucher_issuance_failed',
                log_level='ERROR',
                message=f'Failed to issue voucher: {str(e)}',
                user_id=user_id,
                extra_data={
                    'brand_id': brand_id,
                    'amount': str(amount),
                    'error': str(e)
                },
                exception=e
            )
            raise
    
    def validate_voucher_code(
        self, voucher_code: str, expected_partner_id: Optional[int] = None
    ) -> Optional[GiftVoucher]:
        """
        Validate voucher code format and existence.
        VAPT-006: When expected_partner_id is set, voucher must have metadata.partner_id matching it.
        Legacy vouchers without metadata.partner_id are not accessible to partners (return None).
        """
        code = unformat_voucher_code(voucher_code)
        if len(code) != 16:
            log_voucher_operation(
                operation='voucher_validation_failed',
                log_level='WARNING',
                message=f'Invalid voucher code format: {voucher_code}',
                extra_data={'voucher_code': voucher_code, 'reason': 'invalid_length'}
            )
            return None
        try:
            voucher = GiftVoucher.objects.get(voucher_code=code)
        except GiftVoucher.DoesNotExist:
            log_voucher_operation(
                operation='voucher_validation_failed',
                log_level='WARNING',
                message=f'Voucher code not found: {voucher_code}',
                extra_data={'voucher_code': voucher_code, 'reason': 'not_found'}
            )
            return None
        if expected_partner_id is not None:
            stored_id = (voucher.metadata or {}).get('partner_id')
            if stored_id is None:
                return None  # Legacy/admin voucher: no partner access via v2
            if stored_id != expected_partner_id:
                return None  # Different partner
        return voucher
    
    def verify_pin(
        self,
        voucher: GiftVoucher,
        pin: str,
        increment_retry: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify PIN with retry logic and blocking
        
        Args:
            voucher: Voucher instance
            pin: Plain text PIN
            increment_retry: Whether to increment retry count on failure
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Guard legacy/null values to avoid type errors during retry bookkeeping.
        retry_count = int(voucher.pin_retry_count or 0)

        # Check if PIN is blocked
        if is_pin_blocked(voucher.pin_blocked_until):
            remaining_minutes = int((voucher.pin_blocked_until - timezone.now()).total_seconds() / 60)
            return False, f"PIN is temporarily blocked. Please try again after {remaining_minutes} minutes."
        
        # Validate PIN format
        if not validate_pin_format(pin):
            return False, "Invalid PIN format"
        
        # Verify PIN
        is_valid = verify_pin(pin, voucher.pin_hash)
        
        if not is_valid and increment_retry:
            # Increment retry count
            retry_count += 1
            voucher.pin_retry_count = retry_count
            
            # Block if max retries reached
            if retry_count >= self.max_pin_retries:
                voucher.pin_blocked_until = calculate_pin_block_until()
                voucher.pin_retry_count = 0  # Reset for next block period
                error_msg = f"Too many failed attempts. PIN is temporarily blocked for {get_pin_block_duration_minutes()} minutes."
            else:
                attempts_left = self.max_pin_retries - retry_count
                error_msg = f"Invalid PIN. {attempts_left} attempt(s) remaining."
            
            voucher.save()
            
            log_voucher_operation(
                operation='pin_verification_failed',
                log_level='WARNING',
                message=f'Invalid PIN attempt for voucher {voucher.voucher_code} - Attempts: {voucher.pin_retry_count}',
                extra_data={'voucher_id': voucher.id, 'voucher_code': voucher.voucher_code}
            )
            
            return False, error_msg
        
        if is_valid and retry_count > 0:
            # Reset retry count on successful verification
            voucher.pin_retry_count = 0
            voucher.pin_blocked_until = None
            voucher.save()
        
        return is_valid, None
    
    def redeem_voucher_pin(
        self,
        voucher_code: str,
        pin: str,
        amount: Decimal,
        transaction_ref: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Redeem voucher using PIN method
        
        Args:
            voucher_code: Voucher code
            pin: PIN
            amount: Redemption amount
            transaction_ref: Optional external transaction reference
            ip_address: Optional IP address
            user_agent: Optional user agent
        
        Returns:
            Transaction result dict
        """
        # Validate voucher
        voucher = self.validate_voucher_code(voucher_code)
        if not voucher:
            raise ValueError(get_error_message(VOUCHER_NOT_FOUND))
        
        # Check voucher status
        if voucher.status == 'BLOCKED':
            raise ValueError(get_error_message(VOUCHER_BLOCKED))
        if voucher.status == 'EXPIRED':
            raise ValueError(get_error_message(VOUCHER_EXPIRED))
        if voucher.status == 'FULLY_REDEEMED':
            raise ValueError(get_error_message(VOUCHER_ALREADY_REDEEMED))
        
        # Verify PIN
        is_valid, error_msg = self.verify_pin(voucher, pin, increment_retry=True)
        if not is_valid:
            raise ValueError(error_msg or get_error_message(INVALID_PIN))
        
        # Validate amount
        if amount <= 0:
            raise ValueError(get_error_message(INVALID_AMOUNT))
        if amount > voucher.current_balance:
            raise ValueError(get_error_message(INSUFFICIENT_BALANCE))
        
        if not transaction_ref:
            transaction_ref = generate_transaction_id()

        # Check for duplicate transaction reference
        if transaction_ref:
            if GiftVoucherTransaction.objects.filter(transaction_ref=transaction_ref).exists():
                raise ValueError(get_error_message(DUPLICATE_TRANSACTION))
        
        # Perform redemption inside atomic block with row lock to prevent double-spend.
        # Re-fetch voucher with select_for_update() so concurrent requests serialize on this row.
        with transaction.atomic():
            voucher_locked = GiftVoucher.objects.select_for_update().get(id=voucher.id)
            if voucher_locked.status == 'BLOCKED':
                raise ValueError(get_error_message(VOUCHER_BLOCKED))
            if voucher_locked.status == 'EXPIRED':
                raise ValueError(get_error_message(VOUCHER_EXPIRED))
            if voucher_locked.status == 'FULLY_REDEEMED':
                raise ValueError(get_error_message(VOUCHER_ALREADY_REDEEMED))
            if amount > voucher_locked.current_balance:
                raise ValueError(get_error_message(INSUFFICIENT_BALANCE))
            
            balance_before = voucher_locked.current_balance
            balance_after = balance_before - amount
            
            voucher_locked.current_balance = balance_after
            voucher_locked.last_transaction_at = timezone.now()
            if balance_after == 0:
                voucher_locked.status = 'FULLY_REDEEMED'
            elif balance_after < voucher_locked.original_amount:
                voucher_locked.status = 'PARTIALLY_REDEEMED'
            voucher_locked.save()
            
            txn = GiftVoucherTransaction.objects.create(
                voucher=voucher_locked,
                transaction_type='REDEMPTION',
                transaction_amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                redemption_method='PIN',
                transaction_status='SUCCESS',
                transaction_ref=transaction_ref,
                ip_address=ip_address,
                user_agent=user_agent
            )
            voucher = voucher_locked
        
        log_voucher_operation(
            operation='voucher_redeemed_pin',
            log_level='INFO',
            message=f'Voucher redeemed via PIN - Code: {voucher.voucher_code}, Amount: {amount}',
            extra_data={
                'voucher_id': voucher.id,
                'voucher_code': voucher.voucher_code,
                'transaction_id': txn.id,
                'amount': str(amount),
                'balance_before': str(balance_before),
                'balance_after': str(balance_after)
            }
        )
        
        return {
            'transaction_id': txn.id,
            'reference_number': voucher.reference_number,
            'redeemed_amount': str(amount),
            'balance_before': str(balance_before),
            'balance_after': str(balance_after),
            'status': 'SUCCESS',
            'timestamp': txn.created_at.isoformat()
        }
    
    def redeem_voucher_otp(
        self,
        voucher_code: str,
        otp: str,
        amount: Decimal,
        transaction_ref: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Redeem voucher using OTP method
        
        Args:
            voucher_code: Voucher code
            otp: OTP
            amount: Redemption amount
            transaction_ref: Optional external transaction reference
            ip_address: Optional IP address
            user_agent: Optional user agent
        
        Returns:
            Transaction result dict
        """
        # Validate voucher
        voucher = self.validate_voucher_code(voucher_code)
        if not voucher:
            raise ValueError(get_error_message(VOUCHER_NOT_FOUND))
        
        # Check mobile number
        if not voucher.mobile_number:
            raise ValueError(get_error_message(MOBILE_NUMBER_REQUIRED))
        
        # Check voucher status
        if voucher.status == 'BLOCKED':
            raise ValueError(get_error_message(VOUCHER_BLOCKED))
        if voucher.status == 'EXPIRED':
            raise ValueError(get_error_message(VOUCHER_EXPIRED))
        if voucher.status == 'FULLY_REDEEMED':
            raise ValueError(get_error_message(VOUCHER_ALREADY_REDEEMED))
        
        # Verify OTP
        is_valid, otp_record, error_msg = self.otp_service.verify_otp_for_voucher(
            voucher, otp, 'REDEMPTION', ip_address
        )
        
        if not is_valid:
            raise ValueError(error_msg or get_error_message(INVALID_OTP))
        
        # Validate amount
        if amount <= 0:
            raise ValueError(get_error_message(INVALID_AMOUNT))
        if amount > voucher.current_balance:
            raise ValueError(get_error_message(INSUFFICIENT_BALANCE))
        
        if not transaction_ref:
            transaction_ref = generate_transaction_id()

        # Check for duplicate transaction reference
        if transaction_ref:
            if GiftVoucherTransaction.objects.filter(transaction_ref=transaction_ref).exists():
                raise ValueError(get_error_message(DUPLICATE_TRANSACTION))
        
        # Perform redemption inside atomic block with row lock to prevent double-spend.
        # Re-fetch voucher with select_for_update() so concurrent requests serialize on this row.
        with transaction.atomic():
            voucher_locked = GiftVoucher.objects.select_for_update().get(id=voucher.id)
            if voucher_locked.status == 'BLOCKED':
                raise ValueError(get_error_message(VOUCHER_BLOCKED))
            if voucher_locked.status == 'EXPIRED':
                raise ValueError(get_error_message(VOUCHER_EXPIRED))
            if voucher_locked.status == 'FULLY_REDEEMED':
                raise ValueError(get_error_message(VOUCHER_ALREADY_REDEEMED))
            if amount > voucher_locked.current_balance:
                raise ValueError(get_error_message(INSUFFICIENT_BALANCE))
            
            balance_before = voucher_locked.current_balance
            balance_after = balance_before - amount
            
            voucher_locked.current_balance = balance_after
            voucher_locked.last_transaction_at = timezone.now()
            if balance_after == 0:
                voucher_locked.status = 'FULLY_REDEEMED'
            elif balance_after < voucher_locked.original_amount:
                voucher_locked.status = 'PARTIALLY_REDEEMED'
            voucher_locked.save()
            
            txn = GiftVoucherTransaction.objects.create(
                voucher=voucher_locked,
                transaction_type='REDEMPTION',
                transaction_amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                redemption_method='OTP',
                transaction_status='SUCCESS',
                transaction_ref=transaction_ref,
                ip_address=ip_address,
                user_agent=user_agent
            )
            voucher = voucher_locked
        
        log_voucher_operation(
            operation='voucher_redeemed_otp',
            log_level='INFO',
            message=f'Voucher redeemed via OTP - Code: {voucher.voucher_code}, Amount: {amount}',
            extra_data={
                'voucher_id': voucher.id,
                'voucher_code': voucher.voucher_code,
                'transaction_id': txn.id,
                'amount': str(amount),
                'balance_before': str(balance_before),
                'balance_after': str(balance_after)
            }
        )
        
        return {
            'transaction_id': txn.id,
            'reference_number': voucher.reference_number,
            'redeemed_amount': str(amount),
            'balance_before': str(balance_before),
            'balance_after': str(balance_after),
            'status': 'SUCCESS',
            'timestamp': txn.created_at.isoformat()
        }
    
    def change_pin(
        self,
        voucher_code: str,
        otp: str,
        new_pin: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Change PIN with OTP verification
        
        Args:
            voucher_code: Voucher code
            otp: OTP for verification
            new_pin: New 4-digit PIN
            ip_address: Optional IP address
            user_agent: Optional user agent
        
        Returns:
            Success message dict
        """
        # Validate voucher
        voucher = self.validate_voucher_code(voucher_code)
        if not voucher:
            raise ValueError(get_error_message(VOUCHER_NOT_FOUND))
        
        # Check mobile number
        if not voucher.mobile_number:
            raise ValueError(get_error_message(MOBILE_NUMBER_REQUIRED))
        
        # Verify OTP
        is_valid, otp_record, error_msg = self.otp_service.verify_otp_for_voucher(
            voucher, otp, 'PIN_CHANGE', ip_address
        )
        
        if not is_valid:
            raise ValueError(error_msg or get_error_message(INVALID_OTP))
        
        # Validate new PIN format
        if not validate_pin_format(new_pin):
            raise ValueError("Invalid PIN format. PIN must be 4 digits (1000-9999)")
        
        # Check PIN history
        if check_pin_history(new_pin, voucher.pin_history):
            raise ValueError(get_error_message(PIN_REUSED))
        
        # Update PIN
        with transaction.atomic():
            # Hash new PIN
            new_pin_hash = hash_pin(new_pin)
            
            # Update PIN history (keep last 3)
            pin_history = voucher.pin_history or []
            pin_history.insert(0, voucher.pin_hash)
            pin_history = pin_history[:3]  # Keep only last 3
            
            # Update voucher
            voucher.pin_hash = new_pin_hash
            voucher.pin_history = pin_history
            voucher.last_pin_change = timezone.now()
            voucher.pin_retry_count = 0  # Reset retry count
            voucher.pin_blocked_until = None  # Clear any block
            voucher.save()
            
            # Create transaction record
            GiftVoucherTransaction.objects.create(
                voucher=voucher,
                transaction_type='PIN_CHANGE',
                transaction_amount=None,
                balance_before=voucher.current_balance,
                balance_after=voucher.current_balance,
                transaction_status='SUCCESS',
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        log_voucher_operation(
            operation='pin_changed',
            log_level='INFO',
            message=f'PIN changed for voucher {voucher.voucher_code}',
            extra_data={'voucher_id': voucher.id, 'voucher_code': voucher.voucher_code}
        )
        
        return {
            'message': 'PIN changed successfully',
            'timestamp': timezone.now().isoformat()
        }
    
    def check_balance(
        self,
        voucher_code: str,
        pin: str,
        include_transactions: bool = False
    ) -> Dict[str, Any]:
        """
        Check voucher balance
        
        Args:
            voucher_code: Voucher code
            pin: PIN
            include_transactions: Whether to include recent transactions
        
        Returns:
            Balance information dict
        """
        # Validate voucher
        voucher = self.validate_voucher_code(voucher_code)
        if not voucher:
            raise ValueError(get_error_message(VOUCHER_NOT_FOUND))
        
        # Verify PIN (don't increment retry for balance inquiry)
        is_valid, error_msg = self.verify_pin(voucher, pin, increment_retry=False)
        if not is_valid:
            raise ValueError(error_msg or get_error_message(INVALID_PIN))
        
        # Balance inquiry is not stored in transaction table; use application logs for audit
        result = {
            'reference_number': voucher.reference_number,
            'current_balance': str(voucher.current_balance),
            'original_amount': str(voucher.original_amount),
            'status': voucher.status,
            'issued_at': voucher.issued_at.isoformat(),
            'last_transaction_at': voucher.last_transaction_at.isoformat() if voucher.last_transaction_at else None
        }
        
        # Include recent transactions if requested
        if include_transactions:
            recent_txns = voucher.transactions.filter(
                transaction_type='REDEMPTION'
            ).order_by('-created_at')[:5]
            
            result['recent_transactions'] = [
                {
                    'transaction_id': txn.id,
                    'type': txn.transaction_type,
                    'amount': str(txn.transaction_amount) if txn.transaction_amount else None,
                    'timestamp': txn.created_at.isoformat()
                }
                for txn in recent_txns
            ]
        
        return result
    
    def check_balance_without_pin(
        self,
        voucher_code: str,
        include_transactions: bool = False
    ) -> Dict[str, Any]:
        """
        Check voucher balance without PIN verification (admin only).
        
        Args:
            voucher_code: Voucher code
            include_transactions: Whether to include recent transactions
        
        Returns:
            Balance information dict
        """
        voucher = self.validate_voucher_code(voucher_code)
        if not voucher:
            raise ValueError(get_error_message(VOUCHER_NOT_FOUND))
        
        # Balance inquiry is not stored in transaction table; use application logs for audit
        result = {
            'reference_number': voucher.reference_number,
            'current_balance': str(voucher.current_balance),
            'original_amount': str(voucher.original_amount),
            'status': voucher.status,
            'issued_at': voucher.issued_at.isoformat(),
            'last_transaction_at': voucher.last_transaction_at.isoformat() if voucher.last_transaction_at else None
        }
        if include_transactions:
            recent_txns = voucher.transactions.filter(
                transaction_type='REDEMPTION'
            ).order_by('-created_at')[:5]
            result['recent_transactions'] = [
                {
                    'transaction_id': txn.id,
                    'type': txn.transaction_type,
                    'amount': str(txn.transaction_amount) if txn.transaction_amount else None,
                    'timestamp': txn.created_at.isoformat()
                }
                for txn in recent_txns
            ]
        return result
    
    def generate_otp_for_voucher(
        self,
        voucher_code: str,
        otp_purpose: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate and send OTP for voucher
        
        Args:
            voucher_code: Voucher code
            otp_purpose: Purpose (REDEMPTION or PIN_CHANGE)
            ip_address: Optional IP address
        
        Returns:
            OTP response dict
        """
        # Validate voucher
        voucher = self.validate_voucher_code(voucher_code)
        if not voucher:
            raise ValueError(get_error_message(VOUCHER_NOT_FOUND))
        
        # Check mobile number
        if not voucher.mobile_number:
            raise ValueError(get_error_message(MOBILE_NUMBER_REQUIRED))
        
        # Generate and send OTP
        plain_otp, otp_record = self.otp_service.generate_and_store_otp(
            voucher, voucher.mobile_number, otp_purpose, ip_address
        )
        
        log_voucher_operation(
            operation='otp_generated',
            log_level='INFO',
            message=f'OTP generated for voucher {voucher.voucher_code} - Purpose: {otp_purpose}',
            extra_data={
                'voucher_id': voucher.id,
                'voucher_code': voucher.voucher_code,
                'otp_purpose': otp_purpose,
                'mobile_number_masked': mask_mobile_number(voucher.mobile_number)
            }
        )
        
        return {
            'message': 'OTP sent to registered mobile number',
            'mobile_masked': mask_mobile_number(voucher.mobile_number),
            'expires_in_seconds': 300  # 5 minutes
        }
