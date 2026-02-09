"""
KYC Service
Handles KYC (Know Your Customer) workflow operations
"""
from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone

from portal.models import KYC, User
from portal.mixins.service_base import ServiceBase


class KYCService(ServiceBase):
    """Service for managing KYC operations"""
    
    def submit_kyc(
        self,
        user: User,
        kyc_type: str,
        kyc_number: str,
        document_front: Optional[Any] = None,
        document_back: Optional[Any] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> KYC:
        """
        Submit KYC documents for verification
        
        Args:
            user: User submitting KYC
            kyc_type: Type of KYC (AADHAAR, PAN, PASSPORT, etc.)
            kyc_number: KYC document number
            document_front: Front side of document
            document_back: Back side of document
            additional_data: Additional KYC data
            
        Returns:
            Created KYC instance
        """
        try:
            # Check if user already has KYC of this type
            existing_kyc = KYC.objects.filter(
                user=user,
                kyc_type=kyc_type
            ).first()
            
            if existing_kyc and existing_kyc.status in ['APPROVED', 'PENDING']:
                raise ValueError(f"KYC of type {kyc_type} already exists with status {existing_kyc.status}")
            
            # Create new KYC record
            kyc = KYC.objects.create(
                user=user,
                kyc_type=kyc_type,
                kyc_number=kyc_number,
                document_front=document_front,
                document_back=document_back,
                status='PENDING',
                submitted_at=timezone.now(),
                additional_data=additional_data or {}
            )
            
            self.log_info(
                operation='kyc_submitted',
                message=f'KYC submitted for user {user.username}',
                user_id=user.id,
                extra_data={
                    'kyc_id': kyc.id,
                    'kyc_type': kyc_type
                }
            )
            
            return kyc
            
        except Exception as e:
            self.log_error('kyc_submission', e, user_id=user.id)
            raise
    
    def verify_kyc(
        self,
        kyc: KYC,
        verified_by: User,
        status: str,
        remarks: Optional[str] = None
    ) -> KYC:
        """
        Verify or reject KYC documents
        
        Args:
            kyc: KYC instance
            verified_by: User performing verification
            status: New status (APPROVED or REJECTED)
            remarks: Optional verification remarks
            
        Returns:
            Updated KYC instance
        """
        if status not in ['APPROVED', 'REJECTED']:
            raise ValueError("Status must be APPROVED or REJECTED")
        
        try:
            kyc.status = status
            kyc.verified_by = verified_by
            kyc.verified_at = timezone.now()
            kyc.verification_remarks = remarks
            kyc.save()
            
            self.log_info(
                operation='kyc_verified',
                message=f'KYC {status.lower()} for user {kyc.user.username}',
                user_id=verified_by.id,
                extra_data={
                    'kyc_id': kyc.id,
                    'kyc_type': kyc.kyc_type,
                    'status': status,
                    'user_id': kyc.user.id
                }
            )
            
            return kyc
            
        except Exception as e:
            self.log_error('kyc_verification', e, user_id=verified_by.id)
            raise
    
    def update_kyc(
        self,
        kyc: KYC,
        kyc_number: Optional[str] = None,
        document_front: Optional[Any] = None,
        document_back: Optional[Any] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> KYC:
        """
        Update KYC details (only if status is PENDING or REJECTED)
        
        Args:
            kyc: KYC instance
            kyc_number: Updated KYC number
            document_front: Updated front document
            document_back: Updated back document
            additional_data: Updated additional data
            
        Returns:
            Updated KYC instance
        """
        if kyc.status == 'APPROVED':
            raise ValueError("Cannot update approved KYC")
        
        try:
            if kyc_number:
                kyc.kyc_number = kyc_number
            
            if document_front:
                kyc.document_front = document_front
            
            if document_back:
                kyc.document_back = document_back
            
            if additional_data:
                kyc.additional_data.update(additional_data)
            
            # Reset to PENDING if it was REJECTED
            if kyc.status == 'REJECTED':
                kyc.status = 'PENDING'
                kyc.verified_by = None
                kyc.verified_at = None
                kyc.verification_remarks = None
            
            kyc.save()
            
            self.log_info(
                operation='kyc_updated',
                message=f'KYC updated for user {kyc.user.username}',
                user_id=kyc.user.id,
                extra_data={
                    'kyc_id': kyc.id,
                    'kyc_type': kyc.kyc_type
                }
            )
            
            return kyc
            
        except Exception as e:
            self.log_error('kyc_update', e, user_id=kyc.user.id)
            raise
    
    def get_user_kyc(self, user: User, kyc_type: Optional[str] = None) -> Optional[KYC]:
        """
        Get KYC for a user
        
        Args:
            user: User instance
            kyc_type: Optional KYC type filter
            
        Returns:
            KYC instance or None
        """
        query = KYC.objects.filter(user=user)
        
        if kyc_type:
            query = query.filter(kyc_type=kyc_type)
        
        return query.order_by('-submitted_at').first()
    
    def is_user_kyc_approved(self, user: User) -> bool:
        """
        Check if user has any approved KYC
        
        Args:
            user: User instance
            
        Returns:
            True if user has approved KYC, False otherwise
        """
        return KYC.objects.filter(
            user=user,
            status='APPROVED'
        ).exists()
