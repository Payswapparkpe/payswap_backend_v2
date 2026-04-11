"""
Service Management Service  
Handles service configuration and management operations
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from django.db import transaction

from portal.models import Service, ServiceCost, User
from portal.mixins.service_base import ServiceBase


class ServiceManagementService(ServiceBase):
    """Service for managing platform services"""
    
    def create_service(
        self,
        name: str,
        code: str,
        description: str,
        category: str,
        requires_kyc: bool = False,
        min_balance: Optional[Decimal] = None,
        created_by: Optional[User] = None
    ) -> Service:
        """Create a new service"""
        try:
            # Check if service code already exists
            if Service.objects.filter(code=code).exists():
                raise ValueError(f"Service with code {code} already exists")
            
            service = Service.objects.create(
                name=name,
                code=code,
                description=description,
                category=category,
                is_active=True,
                requires_kyc=requires_kyc,
                min_balance=min_balance or Decimal('0.00')
            )
            
            self.log_info(
                operation='service_created',
                message=f'Service {name} created with code {code}',
                user_id=created_by.id if created_by else None,
                extra_data={
                    'service_id': service.id,
                    'service_code': code,
                    'category': category
                }
            )
            
            return service
            
        except Exception as e:
            self.log_error(
                'service_creation',
                e,
                user_id=created_by.id if created_by else None
            )
            raise
    
    def update_service(
        self,
        service: Service,
        name: Optional[str] = None,
        description: Optional[str] = None,
        requires_kyc: Optional[bool] = None,
        min_balance: Optional[Decimal] = None,
        updated_by: Optional[User] = None
    ) -> Service:
        """Update service configuration"""
        try:
            if name:
                service.name = name
            
            if description:
                service.description = description
            
            if requires_kyc is not None:
                service.requires_kyc = requires_kyc
            
            if min_balance is not None:
                service.min_balance = min_balance
            
            service.save()
            
            self.log_info(
                operation='service_updated',
                message=f'Service {service.code} updated',
                user_id=updated_by.id if updated_by else None,
                extra_data={'service_id': service.id}
            )
            
            return service
            
        except Exception as e:
            self.log_error(
                'service_update',
                e,
                user_id=updated_by.id if updated_by else None
            )
            raise
    
    def activate_service(self, service: Service, activated_by: User) -> Service:
        """Activate a service"""
        service.is_active = True
        service.save()
        
        self.log_info(
            operation='service_activated',
            message=f'Service {service.code} activated',
            user_id=activated_by.id,
            extra_data={'service_id': service.id}
        )
        
        return service
    
    def deactivate_service(self, service: Service, deactivated_by: User) -> Service:
        """Deactivate a service"""
        service.is_active = False
        service.save()
        
        self.log_warning(
            operation='service_deactivated',
            message=f'Service {service.code} deactivated',
            user_id=deactivated_by.id,
            extra_data={'service_id': service.id}
        )
        
        return service
    
    def set_service_cost(
        self,
        service: Service,
        role_code: str,
        cost: Decimal,
        commission: Optional[Decimal] = None,
        updated_by: Optional[User] = None
    ) -> ServiceCost:
        """Set or update service cost for a role"""
        try:
            service_cost, created = ServiceCost.objects.update_or_create(
                service=service,
                role_code=role_code,
                defaults={
                    'cost': cost,
                    'commission': commission or Decimal('0.00')
                }
            )
            
            action = 'created' if created else 'updated'
            self.log_info(
                operation=f'service_cost_{action}',
                message=f'Service cost {action} for {service.code} - {role_code}',
                user_id=updated_by.id if updated_by else None,
                extra_data={
                    'service_id': service.id,
                    'role_code': role_code,
                    'cost': str(cost)
                }
            )
            
            return service_cost
            
        except Exception as e:
            self.log_error(
                'service_cost_update',
                e,
                user_id=updated_by.id if updated_by else None
            )
            raise
    
    def get_service_cost(self, service: Service, role_code: str) -> Optional[Decimal]:
        """Get service cost for a specific role"""
        try:
            service_cost = ServiceCost.objects.get(
                service=service,
                role_code=role_code
            )
            return service_cost.cost
        except ServiceCost.DoesNotExist:
            return None
    
    def get_active_services(self, category: Optional[str] = None) -> List[Service]:
        """Get all active services, optionally filtered by category"""
        queryset = Service.objects.filter(is_active=True)
        
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset.order_by('name')
