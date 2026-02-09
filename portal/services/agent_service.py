"""
Agent Service
Handles agent management operations
"""
from typing import Optional, List, Dict, Any
from django.db import transaction

from portal.models import Agent, Department, User
from portal.mixins.service_base import ServiceBase


class AgentService(ServiceBase):
    """Service for managing agents"""
    
    def create_agent(
        self,
        user: User,
        department: Department,
        created_by: Optional[User] = None
    ) -> Agent:
        """Create a new agent"""
        try:
            # Check if user is already an agent
            if Agent.objects.filter(user=user).exists():
                raise ValueError(f"User {user.username} is already an agent")
            
            agent = Agent.objects.create(
                user=user,
                department=department,
                is_active=True
            )
            
            self.log_info(
                operation='agent_created',
                message=f'Agent created for user {user.username} in {department.name}',
                user_id=created_by.id if created_by else None,
                extra_data={
                    'agent_id': agent.id,
                    'user_id': user.id,
                    'department_id': department.id
                }
            )
            
            return agent
            
        except Exception as e:
            self.log_error(
                'agent_creation',
                e,
                user_id=created_by.id if created_by else None
            )
            raise
    
    def update_agent_department(
        self,
        agent: Agent,
        new_department: Department,
        updated_by: User
    ) -> Agent:
        """Update agent's department"""
        try:
            old_department = agent.department
            agent.department = new_department
            agent.save()
            
            self.log_info(
                operation='agent_department_updated',
                message=f'Agent {agent.user.username} moved from {old_department.name} to {new_department.name}',
                user_id=updated_by.id,
                extra_data={
                    'agent_id': agent.id,
                    'old_department_id': old_department.id,
                    'new_department_id': new_department.id
                }
            )
            
            return agent
            
        except Exception as e:
            self.log_error('agent_department_update', e, user_id=updated_by.id)
            raise
    
    def activate_agent(self, agent: Agent, activated_by: User) -> Agent:
        """Activate an agent"""
        agent.is_active = True
        agent.save()
        
        self.log_info(
            operation='agent_activated',
            message=f'Agent {agent.user.username} activated',
            user_id=activated_by.id,
            extra_data={'agent_id': agent.id}
        )
        
        return agent
    
    def deactivate_agent(self, agent: Agent, deactivated_by: User) -> Agent:
        """Deactivate an agent"""
        agent.is_active = False
        agent.save()
        
        self.log_warning(
            operation='agent_deactivated',
            message=f'Agent {agent.user.username} deactivated',
            user_id=deactivated_by.id,
            extra_data={'agent_id': agent.id}
        )
        
        return agent
    
    def get_department_agents(self, department: Department, active_only: bool = True) -> List[Agent]:
        """Get all agents in a department"""
        queryset = Agent.objects.filter(department=department)
        
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        return queryset.select_related('user', 'department').order_by('user__username')
    
    def get_agent_stats(self, agent: Agent) -> Dict[str, Any]:
        """Get statistics for an agent"""
        from portal.models import Ticket
        
        assigned_tickets = Ticket.objects.filter(assigned_to=agent)
        
        total_tickets = assigned_tickets.count()
        open_tickets = assigned_tickets.filter(status__in=['OPEN', 'IN_PROGRESS']).count()
        resolved_tickets = assigned_tickets.filter(status='RESOLVED').count()
        
        return {
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'resolved_tickets': resolved_tickets,
            'resolution_rate': (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0,
            'is_active': agent.is_active,
            'department': agent.department.name
        }
