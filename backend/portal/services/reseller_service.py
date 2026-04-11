"""
Reseller Partner Management Service
Handles reseller onboarding, management, and operations
"""
from typing import Optional, Dict, Any
from django.utils import timezone
from portal.models import ResellerPartner, Wallet, User
from portal.utils.logging_helper import get_logger

logger = get_logger('portal.services.reseller')


class ResellerService:
    """Service for managing reseller partners"""
    
    @staticmethod
    def create_reseller_partner(
        company_name: str,
        contact_person: str,
        email: str,
        phone: str,
        business_type: str,
        address: str,
        gst_number: Optional[str] = None,
        created_by: Optional[User] = None
    ) -> ResellerPartner:
        """
        Create new reseller partner
        
        Args:
            company_name: Company name
            contact_person: Contact person name
            email: Business email
            phone: Contact phone
            business_type: Business type (LLP, PRIVATE_LTD, etc.)
            address: Business address
            gst_number: Optional GST number
            created_by: User creating the partner
        
        Returns:
            ResellerPartner instance
        """
        # Generate partner code first
        from portal.utils.user_utils import generate_username
        partner_code = 'PRT' + generate_username('P')[:8]
        
        # Create wallet for partner
        # Note: Wallet.user is required, so we'll use created_by or create a system user
        wallet_user = created_by
        if not wallet_user:
            # Create a system user for the wallet if no user provided
            from portal.models import User, Role
            try:
                role = Role.objects.get(code='api_partner')
            except Role.DoesNotExist:
                role = Role.objects.create(
                    code='api_partner',
                    name='API Partner',
                    category='b2b'
                )
            
            wallet_user, _ = User.objects.get_or_create(
                username=f'SYS{partner_code[:8]}',
                defaults={
                    'email': f'system_{partner_code}@payswap.local',
                    'role': role,
                    'role_code': 'api_partner',
                    'is_active': False  # System user, not for login
                }
            )
        
        # Use get_or_create to avoid duplicate wallet error
        # If user already has a wallet, use it; otherwise create a new one
        wallet, wallet_created = Wallet.objects.get_or_create(
            user=wallet_user,
            defaults={
                'balance': 0.00,
                'currency': 'INR',
                'status': 'active'
            }
        )
        
        # Create partner
        partner = ResellerPartner.objects.create(
            partner_code=partner_code,
            company_name=company_name,
            contact_person=contact_person,
            email=email,
            phone=phone,
            business_type=business_type,
            gst_number=gst_number,
            address=address,
            status='PENDING',
            onboarding_status='PENDING',
            wallet=wallet,
            created_by=created_by
        )
        
        logger.info(
            f'Reseller partner created: {company_name} ({partner_code})',
            user=created_by,
            extra_data={
                'partner_id': partner.id,
                'partner_code': partner_code,
                'company_name': company_name
            }
        )
        
        return partner
    
    @staticmethod
    def approve_onboarding(
        partner: ResellerPartner,
        approved_by: User,
        notes: Optional[str] = None
    ) -> ResellerPartner:
        """
        Approve reseller partner onboarding
        
        Args:
            partner: ResellerPartner instance
            approved_by: Admin user approving
            notes: Optional approval notes
        
        Returns:
            Updated ResellerPartner instance
        """
        partner.onboarding_status = 'APPROVED'
        partner.status = 'ACTIVE'
        partner.onboarding_completed_at = timezone.now()
        partner.onboarding_approved_by = approved_by
        if notes:
            partner.onboarding_notes = notes
        partner.save()
        
        logger.info(
            f'Reseller partner approved: {partner.company_name} ({partner.partner_code})',
            user=approved_by,
            extra_data={
                'partner_id': partner.id,
                'partner_code': partner.partner_code
            }
        )
        
        return partner
    
    @staticmethod
    def reject_onboarding(
        partner: ResellerPartner,
        rejected_by: User,
        reason: str
    ) -> ResellerPartner:
        """
        Reject reseller partner onboarding
        
        Args:
            partner: ResellerPartner instance
            rejected_by: Admin user rejecting
            reason: Rejection reason
        
        Returns:
            Updated ResellerPartner instance
        """
        partner.onboarding_status = 'REJECTED'
        partner.status = 'REJECTED'
        partner.onboarding_notes = reason
        partner.save()
        
        logger.info(
            f'Reseller partner rejected: {partner.company_name} ({partner.partner_code})',
            user=rejected_by,
            extra_data={
                'partner_id': partner.id,
                'partner_code': partner.partner_code,
                'reason': reason
            }
        )
        
        return partner
    
    @staticmethod
    def suspend_partner(
        partner: ResellerPartner,
        suspended_by: User,
        reason: str
    ) -> ResellerPartner:
        """
        Suspend reseller partner
        
        Args:
            partner: ResellerPartner instance
            suspended_by: Admin user suspending
            reason: Suspension reason
        
        Returns:
            Updated ResellerPartner instance
        """
        partner.status = 'SUSPENDED'
        partner.metadata = partner.metadata or {}
        partner.metadata['suspension_reason'] = reason
        partner.metadata['suspended_at'] = timezone.now().isoformat()
        partner.metadata['suspended_by'] = suspended_by.id
        partner.save()
        
        # Revoke all API keys
        from portal.models import APIKey
        APIKey.objects.filter(partner=partner, status='ACTIVE').update(
            status='REVOKED',
            revoked_at=timezone.now(),
            revoked_reason=f'Partner suspended: {reason}'
        )
        
        logger.info(
            f'Reseller partner suspended: {partner.company_name} ({partner.partner_code})',
            user=suspended_by,
            extra_data={
                'partner_id': partner.id,
                'partner_code': partner.partner_code,
                'reason': reason
            }
        )
        
        return partner
    
    @staticmethod
    def activate_partner(
        partner: ResellerPartner,
        activated_by: User
    ) -> ResellerPartner:
        """
        Activate suspended reseller partner
        
        Args:
            partner: ResellerPartner instance
            activated_by: Admin user activating
        
        Returns:
            Updated ResellerPartner instance
        """
        partner.status = 'ACTIVE'
        partner.metadata = partner.metadata or {}
        partner.metadata['activated_at'] = timezone.now().isoformat()
        partner.metadata['activated_by'] = activated_by.id
        partner.save()
        
        logger.info(
            f'Reseller partner activated: {partner.company_name} ({partner.partner_code})',
            user=activated_by,
            extra_data={
                'partner_id': partner.id,
                'partner_code': partner.partner_code
            }
        )
        
        return partner
