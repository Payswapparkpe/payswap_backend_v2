"""
OTP Service for Gift Voucher operations
Handles OTP generation, storage, and verification for voucher redemption and PIN changes
"""
import secrets
import bcrypt
from typing import Optional, Dict, Any, Tuple
from django.utils import timezone
from datetime import timedelta
from portal.models import GiftVoucher, GiftVoucherOTP
from portal.utils.voucher_utils import mask_mobile_number
from portal.utils.phone_utils import normalize_phone_number
from portal.services.notification_service_v2 import NotificationServiceV2
from portal.tasks.notification_tasks import send_otp_sms_task
from portal.utils.logging_helper import get_logger

logger = get_logger('portal.services.voucher_otp')

OTP_LENGTH = 6
OTP_VALIDITY_MINUTES = 5
OTP_MAX_ATTEMPTS = 3
OTP_RESEND_COOLDOWN_SECONDS = 30


class VoucherOTPService:
    """OTP service for voucher operations"""
    
    def __init__(self):
        self.notification_service = NotificationServiceV2()
    
    def generate_otp(self) -> str:
        """
        Generate random 6-digit OTP
        
        Returns:
            6-digit OTP string
        """
        return ''.join([str(secrets.randbelow(10)) for _ in range(OTP_LENGTH)])
    
    def hash_otp(self, otp: str) -> str:
        """
        Hash OTP using bcrypt
        
        Args:
            otp: Plain text OTP
        
        Returns:
            Hashed OTP string
        """
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(otp.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_otp(self, otp: str, otp_hash: str) -> bool:
        """
        Verify OTP against hash
        
        Args:
            otp: Plain text OTP
            otp_hash: Hashed OTP
        
        Returns:
            True if OTP matches, False otherwise
        """
        try:
            return bcrypt.checkpw(otp.encode('utf-8'), otp_hash.encode('utf-8'))
        except Exception:
            return False
    
    def generate_and_store_otp(
        self,
        voucher: GiftVoucher,
        mobile_number: str,
        otp_purpose: str,
        ip_address: Optional[str] = None
    ) -> Tuple[str, GiftVoucherOTP]:
        """
        Generate OTP, hash it, store in database, and send via SMS
        
        Args:
            voucher: Voucher instance
            mobile_number: Mobile number to send OTP to
            otp_purpose: Purpose of OTP (REDEMPTION or PIN_CHANGE)
            ip_address: Optional IP address
        
        Returns:
            Tuple of (plain_otp, otp_record)
        """
        # Normalize mobile number
        try:
            normalized_mobile = normalize_phone_number(mobile_number)
        except ValueError as e:
            logger.error(f'Invalid mobile number for OTP: {str(e)}')
            raise ValueError(f"Invalid mobile number: {str(e)}")
        
        # Check for recent OTP (cooldown check)
        recent_otp = GiftVoucherOTP.objects.filter(
            voucher=voucher,
            mobile_number=normalized_mobile,
            otp_purpose=otp_purpose,
            is_verified=False,
            expires_at__gt=timezone.now()
        ).order_by('-generated_at').first()
        
        if recent_otp:
            time_since_generation = (timezone.now() - recent_otp.generated_at).total_seconds()
            if time_since_generation < OTP_RESEND_COOLDOWN_SECONDS:
                remaining_seconds = int(OTP_RESEND_COOLDOWN_SECONDS - time_since_generation)
                raise ValueError(f"Please wait {remaining_seconds} seconds before requesting a new OTP")
        
        # Generate OTP
        plain_otp = self.generate_otp()
        otp_hash = self.hash_otp(plain_otp)
        
        # Calculate expiry
        expires_at = timezone.now() + timedelta(minutes=OTP_VALIDITY_MINUTES)
        
        # Create OTP record
        otp_record = GiftVoucherOTP.objects.create(
            voucher=voucher,
            mobile_number=normalized_mobile,
            otp_hash=otp_hash,
            otp_purpose=otp_purpose,
            expires_at=expires_at,
            ip_address=ip_address
        )
        
        # Send OTP via SMS
        try:
            # Use existing notification service
            send_otp_sms_task.delay(
                phone_number=normalized_mobile,
                otp_code=plain_otp,
                user_id=None,
                context={'voucher_code': voucher.voucher_code, 'purpose': otp_purpose}
            )
            logger.info(
                f'OTP sent for voucher {voucher.voucher_code} - Purpose: {otp_purpose}',
                extra_data={
                    'voucher_id': voucher.id,
                    'mobile_masked': mask_mobile_number(normalized_mobile),
                    'otp_purpose': otp_purpose
                }
            )
        except Exception as e:
            logger.error(
                f'Failed to send OTP for voucher {voucher.voucher_code}: {str(e)}',
                extra_data={'voucher_id': voucher.id, 'error': str(e)},
                traceback=str(e)
            )
            # Don't fail the operation if SMS fails, OTP is still stored
        
        return plain_otp, otp_record
    
    def verify_otp_for_voucher(
        self,
        voucher: GiftVoucher,
        otp: str,
        otp_purpose: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[GiftVoucherOTP], Optional[str]]:
        """
        Verify OTP for voucher
        
        Args:
            voucher: Voucher instance
            otp: Plain text OTP to verify
            otp_purpose: Purpose of OTP (REDEMPTION or PIN_CHANGE)
            ip_address: Optional IP address
        
        Returns:
            Tuple of (is_valid, otp_record, error_message)
        """
        # Find active OTP record
        otp_record = GiftVoucherOTP.objects.filter(
            voucher=voucher,
            otp_purpose=otp_purpose,
            is_verified=False,
            expires_at__gt=timezone.now()
        ).order_by('-generated_at').first()
        
        if not otp_record:
            return False, None, "No active OTP found or OTP has expired"
        
        # Check attempt count
        if otp_record.attempt_count >= OTP_MAX_ATTEMPTS:
            return False, otp_record, "Maximum OTP verification attempts exceeded"
        
        # Increment attempt count
        otp_record.attempt_count += 1
        otp_record.save()
        
        # Verify OTP
        is_valid = self.verify_otp(otp, otp_record.otp_hash)
        
        if is_valid:
            # Mark as verified
            otp_record.is_verified = True
            otp_record.verified_at = timezone.now()
            otp_record.save()
            
            logger.info(
                f'OTP verified for voucher {voucher.voucher_code} - Purpose: {otp_purpose}',
                extra_data={
                    'voucher_id': voucher.id,
                    'otp_purpose': otp_purpose
                }
            )
            
            return True, otp_record, None
        else:
            attempts_left = OTP_MAX_ATTEMPTS - otp_record.attempt_count
            error_msg = f"Invalid OTP. {attempts_left} attempt(s) remaining."
            
            logger.warning(
                f'Invalid OTP attempt for voucher {voucher.voucher_code} - Purpose: {otp_purpose}',
                extra_data={
                    'voucher_id': voucher.id,
                    'otp_purpose': otp_purpose,
                    'attempts_left': attempts_left
                }
            )
            
            return False, otp_record, error_msg
    
    def cleanup_expired_otps(self) -> int:
        """
        Clean up expired OTP records (background task)
        
        Returns:
            Number of OTPs cleaned up
        """
        from django.utils import timezone
        expired_count = GiftVoucherOTP.objects.filter(
            expires_at__lt=timezone.now(),
            is_verified=False
        ).delete()[0]
        
        if expired_count > 0:
            logger.info(f'Cleaned up {expired_count} expired OTP records')
        
        return expired_count
