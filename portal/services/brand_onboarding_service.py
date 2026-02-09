"""
Brand Onboarding Service - Manages brand onboarding workflow
"""
from typing import Dict, Any, Optional, Tuple, List
from django.utils import timezone
from django.core.exceptions import ValidationError
from portal.models import GiftVoucherBrand
from portal.utils.logging_helper import get_logger
from portal.utils.voucher_logging import log_voucher_operation
import traceback

logger = get_logger('portal.services.brand_onboarding')


class BrandOnboardingService:
    """Service for managing brand onboarding process"""
    
    # Step definitions
    STEPS = {
        1: 'basic',
        2: 'business',
        3: 'banking',
        4: 'documents',
        5: 'agreement',
        6: 'review'
    }
    
    STEP_NAMES = {
        'basic': 'Basic Information',
        'business': 'Business Details',
        'banking': 'Banking Information',
        'documents': 'Document Upload',
        'agreement': 'Terms & Agreement',
        'review': 'Review & Submit'
    }
    
    def __init__(self):
        pass
    
    def validate_step(self, step: int, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate data for a specific onboarding step
        
        Args:
            step: Step number (1-6)
            data: Form data dictionary
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        step_name = self.STEPS.get(step)
        if not step_name:
            return False, f"Invalid step number: {step}"
        
        try:
            if step == 1:  # Basic Information
                return self._validate_basic_step(data)
            elif step == 2:  # Business Details
                return self._validate_business_step(data)
            elif step == 3:  # Banking Information
                return self._validate_banking_step(data)
            elif step == 4:  # Documents
                return self._validate_documents_step(data)
            elif step == 5:  # Agreement
                return self._validate_agreement_step(data)
            elif step == 6:  # Review
                return self._validate_review_step(data)
        except Exception as e:
            logger.error(f'Error validating step {step}: {str(e)}', traceback=traceback.format_exc())
            return False, f"Validation error: {str(e)}"
    
    def _validate_basic_step(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate basic information step"""
        required_fields = ['brand_name', 'contact_person', 'contact_email', 'contact_phone', 'address']
        
        for field in required_fields:
            if not data.get(field):
                return False, f"{field.replace('_', ' ').title()} is required"
        
        # Validate email format
        email = data.get('contact_email', '')
        if '@' not in email or '.' not in email.split('@')[1]:
            return False, "Invalid email format"
        
        # Validate phone (basic check)
        phone = data.get('contact_phone', '')
        if len(phone) < 10:
            return False, "Invalid phone number"
        
        return True, None
    
    def _validate_business_step(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate business details step"""
        required_fields = ['business_type', 'business_reg_no']
        
        for field in required_fields:
            if not data.get(field):
                return False, f"{field.replace('_', ' ').title()} is required"
        
        # Validate PAN if provided
        pan = data.get('pan_number', '')
        if pan and len(pan) != 10:
            return False, "PAN must be 10 characters"
        
        # Validate GST if provided
        gst = data.get('gst_number', '')
        if gst and len(gst) != 15:
            return False, "GST number must be 15 characters"
        
        return True, None
    
    def _validate_banking_step(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate banking information step"""
        required_fields = ['bank_account_number', 'bank_ifsc_code', 'bank_name', 'account_holder_name']
        
        for field in required_fields:
            if not data.get(field):
                return False, f"{field.replace('_', ' ').title()} is required"
        
        # Validate IFSC code format (11 characters)
        ifsc = data.get('bank_ifsc_code', '')
        if len(ifsc) != 11:
            return False, "IFSC code must be 11 characters"
        
        # Validate account number (at least 9 digits)
        account = data.get('bank_account_number', '')
        if len(account) < 9 or not account.isdigit():
            return False, "Invalid account number"
        
        return True, None
    
    def _validate_documents_step(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate documents step - all documents optional, upload one or more as needed"""
        return True, None
    
    def _validate_agreement_step(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate agreement step"""
        if not data.get('terms_accepted'):
            return False, "You must accept the terms and conditions"
        
        return True, None
    
    def _validate_review_step(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate review step - check all previous steps are complete"""
        # Review step doesn't need additional validation
        # It just confirms all previous steps are complete
        return True, None
    
    def save_step(self, step: int, data: Dict[str, Any], brand: GiftVoucherBrand) -> GiftVoucherBrand:
        """
        Save data for a specific onboarding step
        
        Args:
            step: Step number (1-6)
            data: Form data dictionary
            brand: Brand instance
            
        Returns:
            Updated brand instance
        """
        step_name = self.STEPS.get(step)
        if not step_name:
            raise ValueError(f"Invalid step number: {step}")
        
        # Update onboarding status if starting
        if brand.onboarding_status == 'PENDING':
            brand.onboarding_status = 'IN_PROGRESS'
        
        if step == 1:  # Basic Information
            brand.brand_name = data.get('brand_name', brand.brand_name)
            brand.contact_person = data.get('contact_person', brand.contact_person)
            brand.contact_email = data.get('contact_email', brand.contact_email)
            brand.contact_phone = data.get('contact_phone', brand.contact_phone)
            brand.address = data.get('address', brand.address)
            
        elif step == 2:  # Business Details
            brand.business_type = data.get('business_type', brand.business_type)
            brand.business_reg_no = data.get('business_reg_no', brand.business_reg_no)
            brand.pan_number = data.get('pan_number', brand.pan_number)
            brand.gst_number = data.get('gst_number', brand.gst_number)
            
        elif step == 3:  # Banking Information
            account_number = data.get('bank_account_number', '')
            if account_number:
                brand.set_encrypted_bank_account(account_number)
            brand.bank_ifsc_code = data.get('bank_ifsc_code', brand.bank_ifsc_code)
            brand.bank_name = data.get('bank_name', brand.bank_name)
            brand.account_holder_name = data.get('account_holder_name', brand.account_holder_name)
            
        elif step == 4:  # Documents
            brand.business_registration_doc = data.get('business_registration_doc', brand.business_registration_doc)
            brand.pan_document = data.get('pan_document', brand.pan_document)
            brand.gst_certificate = data.get('gst_certificate', brand.gst_certificate)
            brand.bank_statement = data.get('bank_statement', brand.bank_statement)
            brand.agreement_document = data.get('agreement_document', brand.agreement_document)
            if data.get('other_documents'):
                brand.other_documents = data.get('other_documents', brand.other_documents)
            
        elif step == 5:  # Agreement
            if data.get('terms_accepted'):
                brand.terms_accepted = True
                brand.terms_accepted_at = timezone.now()
            if data.get('agreement_signed'):
                brand.agreement_signed = True
                brand.agreement_signed_at = timezone.now()
        
        brand.save()
        
        log_voucher_operation(
            operation='onboarding_step_saved',
            log_level='INFO',
            message=f'Onboarding step {step} saved for brand {brand.brand_code}',
            extra_data={
                'brand_id': brand.id,
                'brand_code': brand.brand_code,
                'step_number': step,
                'step_name': self.STEPS.get(step),
                'onboarding_status': brand.onboarding_status
            }
        )
        
        return brand
    
    def get_next_step(self, brand: GiftVoucherBrand) -> Optional[int]:
        """
        Determine the next incomplete step
        
        Args:
            brand: Brand instance
            
        Returns:
            Next step number (1-6) or None if all steps complete
        """
        for step in range(1, 7):
            if not self.is_step_complete(step, brand):
                return step
        return None
    
    def is_step_complete(self, step: int, brand: GiftVoucherBrand) -> bool:
        """
        Check if a specific step is complete
        
        Args:
            step: Step number (1-6)
            brand: Brand instance
            
        Returns:
            True if step is complete, False otherwise
        """
        if step == 1:  # Basic Information
            return all([
                brand.brand_name,
                brand.contact_person,
                brand.contact_email,
                brand.contact_phone,
                brand.address
            ])
        
        elif step == 2:  # Business Details
            return all([
                brand.business_type,
                brand.business_reg_no
            ])
        
        elif step == 3:  # Banking Information
            return all([
                brand.bank_account_number,
                brand.bank_ifsc_code,
                brand.bank_name,
                brand.account_holder_name
            ])
        
        elif step == 4:  # Documents (all optional - step complete even with zero docs)
            return True
        
        elif step == 5:  # Agreement
            return brand.terms_accepted and brand.agreement_signed
        
        elif step == 6:  # Review
            # Review is complete if all previous steps are complete
            return all([self.is_step_complete(s, brand) for s in range(1, 6)])
        
        return False
    
    def can_submit(self, brand: GiftVoucherBrand) -> Tuple[bool, List[str]]:
        """
        Check if brand can submit for approval
        
        Args:
            brand: Brand instance
            
        Returns:
            Tuple of (can_submit, list_of_missing_steps)
        """
        missing_steps = []
        
        for step in range(1, 7):
            if not self.is_step_complete(step, brand):
                step_name = self.STEP_NAMES.get(self.STEPS[step], f"Step {step}")
                missing_steps.append(step_name)
        
        return len(missing_steps) == 0, missing_steps
    
    def submit_for_approval(self, brand: GiftVoucherBrand) -> GiftVoucherBrand:
        """
        Submit brand onboarding for admin approval
        
        Args:
            brand: Brand instance
            
        Returns:
            Updated brand instance
            
        Raises:
            ValidationError: If not all steps are complete
        """
        can_submit, missing_steps = self.can_submit(brand)
        
        if not can_submit:
            raise ValidationError(
                f"Cannot submit: Missing steps - {', '.join(missing_steps)}"
            )
        
        brand.submit_for_approval()
        
        log_voucher_operation(
            operation='onboarding_submitted',
            log_level='INFO',
            message=f'Brand {brand.brand_code} submitted for onboarding approval',
            extra_data={
                'brand_id': brand.id,
                'brand_code': brand.brand_code,
                'brand_name': brand.brand_name,
                'onboarding_status': brand.onboarding_status
            }
        )
        
        return brand
    
    def approve_onboarding(self, brand: GiftVoucherBrand, approved_by) -> GiftVoucherBrand:
        """
        Approve brand onboarding
        
        Args:
            brand: Brand instance
            approved_by: User approving the onboarding
            
        Returns:
            Updated brand instance
        """
        try:
            brand.approve_onboarding(approved_by)
            
            user_id = approved_by.id if approved_by and hasattr(approved_by, 'id') else None
            log_voucher_operation(
                operation='onboarding_approved',
                log_level='INFO',
                message=f'Brand {brand.brand_code} onboarding approved',
                user_id=user_id,
                extra_data={
                    'brand_id': brand.id,
                    'brand_code': brand.brand_code,
                    'brand_name': brand.brand_name,
                    'approved_by': approved_by.username if approved_by and hasattr(approved_by, 'username') else str(approved_by),
                    'onboarding_status': brand.onboarding_status
                }
            )
            
            return brand
            
        except Exception as e:
            user_id = approved_by.id if approved_by and hasattr(approved_by, 'id') else None
            log_voucher_operation(
                operation='onboarding_approval_failed',
                log_level='ERROR',
                message=f'Failed to approve brand {brand.brand_code} onboarding: {str(e)}',
                user_id=user_id,
                extra_data={'brand_id': brand.id, 'brand_code': brand.brand_code, 'error': str(e)},
                exception=e
            )
            raise
    
    def reject_onboarding(self, brand: GiftVoucherBrand, rejected_by, reason: str) -> GiftVoucherBrand:
        """
        Reject brand onboarding
        
        Args:
            brand: Brand instance
            rejected_by: User rejecting the onboarding
            reason: Reason for rejection
            
        Returns:
            Updated brand instance
        """
        try:
            brand.reject_onboarding(rejected_by, reason)
            
            user_id = rejected_by.id if rejected_by and hasattr(rejected_by, 'id') else None
            log_voucher_operation(
                operation='onboarding_rejected',
                log_level='WARNING',
                message=f'Brand {brand.brand_code} onboarding rejected',
                user_id=user_id,
                extra_data={
                    'brand_id': brand.id,
                    'brand_code': brand.brand_code,
                    'brand_name': brand.brand_name,
                    'rejected_by': rejected_by.username if rejected_by and hasattr(rejected_by, 'username') else str(rejected_by),
                    'reason': reason,
                    'onboarding_status': brand.onboarding_status
                }
            )
            
            return brand
            
        except Exception as e:
            user_id = rejected_by.id if rejected_by and hasattr(rejected_by, 'id') else None
            log_voucher_operation(
                operation='onboarding_rejection_failed',
                log_level='ERROR',
                message=f'Failed to reject brand {brand.brand_code} onboarding: {str(e)}',
                user_id=user_id,
                extra_data={'brand_id': brand.id, 'brand_code': brand.brand_code, 'error': str(e)},
                exception=e
            )
            raise
    
    def get_onboarding_progress(self, brand: GiftVoucherBrand) -> Dict[str, Any]:
        """
        Get onboarding progress information
        
        Args:
            brand: Brand instance
            
        Returns:
            Dictionary with progress information
        """
        total_steps = 6
        completed_steps = sum(1 for step in range(1, 7) if self.is_step_complete(step, brand))
        progress_percentage = (completed_steps / total_steps) * 100
        
        steps_status = {}
        for step in range(1, 7):
            step_name = self.STEPS[step]
            steps_status[step_name] = {
                'number': step,
                'name': self.STEP_NAMES[step_name],
                'complete': self.is_step_complete(step, brand)
            }
        
        next_step = self.get_next_step(brand)
        can_submit, missing_steps = self.can_submit(brand)
        
        return {
            'total_steps': total_steps,
            'completed_steps': completed_steps,
            'progress_percentage': progress_percentage,
            'steps_status': steps_status,
            'next_step': next_step,
            'can_submit': can_submit,
            'missing_steps': missing_steps,
            'onboarding_status': brand.onboarding_status
        }
