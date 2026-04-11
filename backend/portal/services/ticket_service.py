"""
Ticket Service
Handles ticket lifecycle management operations
"""
from typing import Optional, Dict, List, Any
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from portal.models import Ticket, TicketNote, TicketAttachment, TicketAssignmentHistory, Department, Agent, User
from portal.mixins.service_base import ServiceBase


class TicketService(ServiceBase):
    """Service for managing tickets"""
    
    def create_ticket(
        self,
        subject: str,
        description: str,
        category: str,
        priority: str,
        created_by: User,
        department: Optional[Department] = None,
        assigned_to: Optional[Agent] = None
    ) -> Ticket:
        """
        Create a new ticket
        
        Args:
            subject: Ticket subject
            description: Ticket description
            category: Ticket category
            priority: Ticket priority
            created_by: User creating the ticket
            department: Optional department assignment
            assigned_to: Optional agent assignment
            
        Returns:
            Created Ticket instance
        """
        # Log operation start
        self.log_service_operation(
            operation='create_ticket',
            status='started',
            user=created_by,
            extra_data={
                'subject': subject,
                'category': category,
                'priority': priority
            }
        )
        
        try:
            with transaction.atomic():
                # Generate ticket number
                ticket_number = self._generate_ticket_number()
                
                # Create ticket
                ticket = Ticket.objects.create(
                    ticket_number=ticket_number,
                    subject=subject,
                    description=description,
                    category=category,
                    priority=priority,
                    status='OPEN',
                    created_by=created_by,
                    department=department,
                    assigned_to=assigned_to
                )
                
                # Log assignment if agent is assigned
                if assigned_to:
                    TicketAssignmentHistory.objects.create(
                        ticket=ticket,
                        assigned_to=assigned_to,
                        assigned_by=created_by,
                        notes=f'Initial assignment to {assigned_to.user.username}'
                    )
                
                # Log using legacy method (keep for backward compatibility)
                self.log_info(
                    operation='ticket_created',
                    message=f'Ticket {ticket_number} created',
                    user_id=created_by.id,
                    extra_data={
                        'ticket_id': ticket.id,
                        'ticket_number': ticket_number,
                        'category': category,
                        'priority': priority
                    }
                )
                
                # Log operation success with unified logger
                self.log_service_operation(
                    operation='create_ticket',
                    status='success',
                    user=created_by,
                    extra_data={
                        'ticket_id': ticket.id,
                        'ticket_number': ticket_number
                    }
                )
                
                return ticket
                
        except Exception as e:
            # Log using legacy method
            self.log_error('ticket_creation', e, user_id=created_by.id if created_by else None)
            
            # Log operation error with unified logger
            self.log_operation_error(
                operation='create_ticket',
                exception=e,
                user=created_by,
                context={
                    'subject': subject,
                    'category': category,
                    'priority': priority
                }
            )
            raise
    
    def update_ticket_status(
        self,
        ticket: Ticket,
        new_status: str,
        updated_by: User,
        notes: Optional[str] = None
    ) -> Ticket:
        """
        Update ticket status
        
        Args:
            ticket: Ticket instance
            new_status: New status
            updated_by: User performing update
            notes: Optional notes
            
        Returns:
            Updated Ticket instance
        """
        try:
            old_status = ticket.status
            ticket.status = new_status
            ticket.updated_at = timezone.now()
            
            if new_status == 'RESOLVED':
                ticket.resolved_at = timezone.now()
                ticket.resolved_by = updated_by
            
            ticket.save()
            
            # Add note about status change
            if notes:
                self.add_note(ticket, notes, updated_by, is_internal=True)
            
            self.log_info(
                operation='ticket_status_updated',
                message=f'Ticket {ticket.ticket_number} status changed from {old_status} to {new_status}',
                user_id=updated_by.id,
                extra_data={
                    'ticket_id': ticket.id,
                    'old_status': old_status,
                    'new_status': new_status
                }
            )
            
            return ticket
            
        except Exception as e:
            self.log_error('ticket_status_update', e, user_id=updated_by.id if updated_by else None)
            raise
    
    def assign_ticket(
        self,
        ticket: Ticket,
        agent: Agent,
        assigned_by: User,
        notes: Optional[str] = None
    ) -> Ticket:
        """
        Assign ticket to an agent
        
        Args:
            ticket: Ticket instance
            agent: Agent to assign to
            assigned_by: User performing assignment
            notes: Optional assignment notes
            
        Returns:
            Updated Ticket instance
        """
        try:
            with transaction.atomic():
                old_agent = ticket.assigned_to
                ticket.assigned_to = agent
                ticket.save()
                
                # Log assignment history
                TicketAssignmentHistory.objects.create(
                    ticket=ticket,
                    assigned_to=agent,
                    assigned_by=assigned_by,
                    notes=notes or f'Assigned from {old_agent.user.username if old_agent else "Unassigned"}'
                )
                
                self.log_info(
                    operation='ticket_assigned',
                    message=f'Ticket {ticket.ticket_number} assigned to {agent.user.username}',
                    user_id=assigned_by.id,
                    extra_data={
                        'ticket_id': ticket.id,
                        'agent_id': agent.id,
                        'agent_name': agent.user.username
                    }
                )
                
                return ticket
                
        except Exception as e:
            self.log_error('ticket_assignment', e, user_id=assigned_by.id if assigned_by else None)
            raise
    
    def add_note(
        self,
        ticket: Ticket,
        note: str,
        created_by: User,
        is_internal: bool = False
    ) -> TicketNote:
        """
        Add a note to a ticket
        
        Args:
            ticket: Ticket instance
            note: Note content
            created_by: User creating the note
            is_internal: Whether note is internal only
            
        Returns:
            Created TicketNote instance
        """
        try:
            ticket_note = TicketNote.objects.create(
                ticket=ticket,
                note=note,
                created_by=created_by,
                is_internal=is_internal
            )
            
            # Update ticket's updated_at timestamp
            ticket.updated_at = timezone.now()
            ticket.save(update_fields=['updated_at'])
            
            return ticket_note
            
        except Exception as e:
            self.log_error('ticket_note_creation', e, user_id=created_by.id if created_by else None)
            raise
    
    def search_tickets(
        self,
        search_term: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        department: Optional[Department] = None,
        assigned_to: Optional[Agent] = None,
        created_by: Optional[User] = None
    ) -> List[Ticket]:
        """
        Search tickets with filters
        
        Args:
            search_term: Search in subject/description
            status: Filter by status
            category: Filter by category
            priority: Filter by priority
            department: Filter by department
            assigned_to: Filter by assigned agent
            created_by: Filter by creator
            
        Returns:
            List of matching Ticket instances
        """
        queryset = Ticket.objects.all()
        
        if search_term:
            queryset = queryset.filter(
                Q(ticket_number__icontains=search_term) |
                Q(subject__icontains=search_term) |
                Q(description__icontains=search_term)
            )
        
        if status:
            queryset = queryset.filter(status=status)
        
        if category:
            queryset = queryset.filter(category=category)
        
        if priority:
            queryset = queryset.filter(priority=priority)
        
        if department:
            queryset = queryset.filter(department=department)
        
        if assigned_to:
            queryset = queryset.filter(assigned_to=assigned_to)
        
        if created_by:
            queryset = queryset.filter(created_by=created_by)
        
        return queryset.order_by('-created_at')
    
    def get_ticket_history(self, ticket: Ticket) -> List[TicketAssignmentHistory]:
        """
        Get assignment history for a ticket
        
        Args:
            ticket: Ticket instance
            
        Returns:
            List of TicketAssignmentHistory instances
        """
        return TicketAssignmentHistory.objects.filter(
            ticket=ticket
        ).order_by('-assigned_at')
    
    def _generate_ticket_number(self) -> str:
        """Generate unique ticket number"""
        from django.db.models import Max
        
        # Get last ticket number
        last_ticket = Ticket.objects.aggregate(Max('id'))
        last_id = last_ticket['id__max'] or 0
        
        # Generate new ticket number
        new_number = f"TKT{(last_id + 1):08d}"
        
        return new_number
