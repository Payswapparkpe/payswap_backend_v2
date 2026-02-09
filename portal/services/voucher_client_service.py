"""
Voucher Client Service - Manages clients under brands
"""
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.core.exceptions import ValidationError
from portal.models import VoucherClient, GiftVoucherBrand, User
from portal.utils.voucher_utils import generate_client_code
from portal.utils.logging_helper import get_logger
from portal.utils.voucher_logging import log_voucher_operation

logger = get_logger('portal.services.voucher_client')


class VoucherClientService:
    """Service for voucher client operations"""
    
    DEFAULT_CLIENT_NAME = "Payswap"
    
    def create_client(
        self,
        brand_id: int,
        client_data: Dict[str, Any],
        created_by: Optional[User] = None
    ) -> VoucherClient:
        """
        Create a new client under a brand
        
        Args:
            brand_id: Brand ID
            client_data: Dict with client_name, contact_person, contact_email, contact_phone, metadata
            created_by: User creating the client
        
        Returns:
            VoucherClient instance
        """
        try:
            # Get brand
            try:
                brand = GiftVoucherBrand.objects.get(id=brand_id)
            except GiftVoucherBrand.DoesNotExist:
                raise ValueError("Brand not found")
            
            # Validate brand can have clients (must be onboarded)
            if not brand.is_onboarded():
                raise ValueError("Brand onboarding must be complete before creating clients")
            
            # Extract client data
            client_name = client_data.get('client_name', '').strip()
            if not client_name:
                raise ValueError("Client name is required")
            
            # Check if default client already exists
            is_default = client_data.get('is_default', False)
            if is_default:
                existing_default = VoucherClient.objects.filter(
                    brand=brand,
                    is_default=True,
                    status='ACTIVE'
                ).first()
                if existing_default:
                    raise ValueError(f"Default client already exists for this brand: {existing_default.client_name}")
            
            # Generate client code
            client_code = generate_client_code(brand, client_name)
            
            # Create client
            with transaction.atomic():
                client = VoucherClient.objects.create(
                    brand=brand,
                    client_name=client_name,
                    client_code=client_code,
                    contact_person=client_data.get('contact_person', '').strip() or None,
                    contact_email=client_data.get('contact_email', '').strip() or None,
                    contact_phone=client_data.get('contact_phone', '').strip() or None,
                    is_default=is_default,
                    status=client_data.get('status', 'ACTIVE'),
                    created_by=created_by,
                    metadata=client_data.get('metadata', {})
                )
            
            user_id = created_by.id if created_by and hasattr(created_by, 'id') else None
            log_voucher_operation(
                operation='client_created',
                log_level='INFO',
                message=f'Client created - Name: {client_name}, Code: {client_code}, Brand: {brand.brand_name}',
                user_id=user_id,
                extra_data={
                    'client_id': client.id,
                    'client_name': client_name,
                    'client_code': client_code,
                    'brand_id': brand_id,
                    'brand_name': brand.brand_name,
                    'is_default': is_default
                }
            )
            
            return client
            
        except Exception as e:
            user_id = created_by.id if created_by and hasattr(created_by, 'id') else None
            log_voucher_operation(
                operation='client_creation_failed',
                log_level='ERROR',
                message=f'Failed to create client: {str(e)}',
                user_id=user_id,
                extra_data={'brand_id': brand_id, 'error': str(e)},
                exception=e
            )
            raise
    
    def get_or_create_default_client(self, brand_id: int) -> VoucherClient:
        """
        Get or create the default Payswap client for a brand
        
        Args:
            brand_id: Brand ID
        
        Returns:
            VoucherClient instance (default Payswap client)
        """
        try:
            # Get brand
            try:
                brand = GiftVoucherBrand.objects.get(id=brand_id)
            except GiftVoucherBrand.DoesNotExist:
                raise ValueError("Brand not found")
            
            # Try to get existing default client
            default_client = VoucherClient.objects.filter(
                brand=brand,
                is_default=True,
                status='ACTIVE'
            ).first()
            
            if default_client:
                return default_client
            
            # Create default client if it doesn't exist
            with transaction.atomic():
                client_code = generate_client_code(brand, self.DEFAULT_CLIENT_NAME)
                default_client = VoucherClient.objects.create(
                    brand=brand,
                    client_name=self.DEFAULT_CLIENT_NAME,
                    client_code=client_code,
                    is_default=True,
                    status='ACTIVE',
                    created_by=None,  # System-created
                    metadata={'auto_created': True, 'system_client': True}
                )
            
            log_voucher_operation(
                operation='default_client_created',
                log_level='INFO',
                message=f'Default Payswap client created - Brand: {brand.brand_name}, Code: {client_code}',
                extra_data={'client_id': default_client.id, 'brand_id': brand_id, 'brand_name': brand.brand_name}
            )
            
            return default_client
            
        except Exception as e:
            log_voucher_operation(
                operation='default_client_creation_failed',
                log_level='ERROR',
                message=f'Failed to get or create default client: {str(e)}',
                extra_data={'brand_id': brand_id, 'error': str(e)},
                exception=e
            )
            raise
    
    def get_brand_clients(
        self,
        brand_id: int,
        include_inactive: bool = False
    ) -> List[VoucherClient]:
        """
        Get all clients for a brand
        
        Args:
            brand_id: Brand ID
            include_inactive: Whether to include inactive clients
        
        Returns:
            List of VoucherClient instances
        """
        try:
            queryset = VoucherClient.objects.filter(brand_id=brand_id)
            
            if not include_inactive:
                queryset = queryset.filter(status='ACTIVE')
            
            return list(queryset.order_by('-is_default', 'client_name'))
            
        except Exception as e:
            logger.error(
                f'Failed to get brand clients: {str(e)}',
                extra_data={'brand_id': brand_id, 'error': str(e)}
            )
            raise
    
    def update_client(
        self,
        client_id: int,
        client_data: Dict[str, Any]
    ) -> VoucherClient:
        """
        Update client information
        
        Args:
            client_id: Client ID
            client_data: Dict with fields to update
        
        Returns:
            Updated VoucherClient instance
        """
        try:
            client = VoucherClient.objects.get(id=client_id)
            
            # Update fields
            if 'client_name' in client_data:
                client.client_name = client_data['client_name'].strip()
            if 'contact_person' in client_data:
                client.contact_person = client_data['contact_person'].strip() or None
            if 'contact_email' in client_data:
                client.contact_email = client_data['contact_email'].strip() or None
            if 'contact_phone' in client_data:
                client.contact_phone = client_data['contact_phone'].strip() or None
            if 'status' in client_data:
                client.status = client_data['status']
            if 'metadata' in client_data:
                client.metadata = client_data['metadata']
            
            # Handle is_default change
            if 'is_default' in client_data:
                is_default = client_data['is_default']
                if is_default and not client.is_default:
                    # Check if another default exists
                    existing_default = VoucherClient.objects.filter(
                        brand=client.brand,
                        is_default=True,
                        status='ACTIVE'
                    ).exclude(id=client_id).first()
                    if existing_default:
                        raise ValueError(f"Default client already exists: {existing_default.client_name}")
                client.is_default = is_default
            
            client.save()
            
            log_voucher_operation(
                operation='client_updated',
                log_level='INFO',
                message=f'Client updated - ID: {client_id}, Name: {client.client_name}',
                extra_data={
                    'client_id': client_id,
                    'client_name': client.client_name,
                    'brand_id': client.brand.id if client.brand else None,
                    'changes': {k: v for k, v in client_data.items() if k in ['client_name', 'contact_person', 'contact_email', 'contact_phone', 'status']}
                }
            )
            
            return client
            
        except VoucherClient.DoesNotExist:
            raise ValueError("Client not found")
        except Exception as e:
            log_voucher_operation(
                operation='client_update_failed',
                log_level='ERROR',
                message=f'Failed to update client: {str(e)}',
                extra_data={'client_id': client_id, 'error': str(e)},
                exception=e
            )
            raise
    
    def deactivate_client(self, client_id: int) -> VoucherClient:
        """
        Deactivate a client (soft delete)
        
        Args:
            client_id: Client ID
        
        Returns:
            Deactivated VoucherClient instance
        """
        try:
            client = VoucherClient.objects.get(id=client_id)
            
            # Don't allow deactivating default client
            if client.is_default:
                raise ValueError("Cannot deactivate default Payswap client")
            
            client.status = 'INACTIVE'
            client.save()
            
            log_voucher_operation(
                operation='client_deactivated',
                log_level='INFO',
                message=f'Client deactivated - ID: {client_id}, Name: {client.client_name}',
                extra_data={
                    'client_id': client_id,
                    'client_name': client.client_name,
                    'brand_id': client.brand.id if client.brand else None
                }
            )
            
            return client
            
        except VoucherClient.DoesNotExist:
            raise ValueError("Client not found")
        except Exception as e:
            log_voucher_operation(
                operation='client_deactivation_failed',
                log_level='ERROR',
                message=f'Failed to deactivate client: {str(e)}',
                extra_data={'client_id': client_id, 'error': str(e)},
                exception=e
            )
            raise
