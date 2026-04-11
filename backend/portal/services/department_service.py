"""
Department Service
Handles department management operations
"""
from typing import Optional, List, Dict, Any
from django.db import transaction

from portal.models import Department, User
from portal.mixins.service_base import ServiceBase


class DepartmentService(ServiceBase):
    """Service for managing departments"""
    
    def create_department(
        self,
        name: str,
        description: Optional[str] = None,
        created_by: Optional[User] = None
    ) -> Department:
        """Create a new department"""
        try:
            # Check if department name already exists
            if Department.objects.filter(name=name).exists():
                raise ValueError(f"Department with name '{name}' already exists")
            
            department = Department.objects.create(
                name=name,
                description=description or '',
                is_active=True
            )
            
            self.log_info(
                operation='department_created',
                message=f'Department {name} created',
                user_id=created_by.id if created_by else None,
                extra_data={'department_id': department.id}
            )
            
            return department
            
        except Exception as e:
            self.log_error(
                'department_creation',
                e,
                user_id=created_by.id if created_by else None
            )
            raise
    
    def update_department(
        self,
        department: Department,
        name: Optional[str] = None,
        description: Optional[str] = None,
        updated_by: Optional[User] = None
    ) -> Department:
        """Update department details"""
        try:
            if name and name != department.name:
                # Check if new name already exists
                if Department.objects.filter(name=name).exclude(id=department.id).exists():
                    raise ValueError(f"Department with name '{name}' already exists")
                department.name = name
            
            if description is not None:
                department.description = description
            
            department.save()
            
            self.log_info(
                operation='department_updated',
                message=f'Department {department.name} updated',
                user_id=updated_by.id if updated_by else None,
                extra_data={'department_id': department.id}
            )
            
            return department
            
        except Exception as e:
            self.log_error(
                'department_update',
                e,
                user_id=updated_by.id if updated_by else None
            )
            raise
    
    def activate_department(self, department: Department, activated_by: User) -> Department:
        """Activate a department"""
        department.is_active = True
        department.save()
        
        self.log_info(
            operation='department_activated',
            message=f'Department {department.name} activated',
            user_id=activated_by.id,
            extra_data={'department_id': department.id}
        )
        
        return department
    
    def deactivate_department(self, department: Department, deactivated_by: User) -> Department:
        """Deactivate a department"""
        department.is_active = False
        department.save()
        
        self.log_warning(
            operation='department_deactivated',
            message=f'Department {department.name} deactivated',
            user_id=deactivated_by.id,
            extra_data={'department_id': department.id}
        )
        
        return department
    
    def get_active_departments(self) -> List[Department]:
        """Get all active departments"""
        return Department.objects.filter(is_active=True).order_by('name')
    
    def get_department_stats(self, department: Department) -> Dict[str, Any]:
        """Get statistics for a department"""
        from portal.models import Agent, Ticket
        
        agent_count = Agent.objects.filter(
            department=department,
            is_active=True
        ).count()
        
        ticket_count = Ticket.objects.filter(department=department).count()
        
        open_tickets = Ticket.objects.filter(
            department=department,
            status__in=['OPEN', 'IN_PROGRESS']
        ).count()
        
        resolved_tickets = Ticket.objects.filter(
            department=department,
            status='RESOLVED'
        ).count()
        
        return {
            'agent_count': agent_count,
            'total_tickets': ticket_count,
            'open_tickets': open_tickets,
            'resolved_tickets': resolved_tickets,
            'is_active': department.is_active
        }
