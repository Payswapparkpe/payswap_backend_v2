"""
Ticket Management Views for API v1
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg, F
from django.utils import timezone
from datetime import timedelta

from api.mixins.response_mixin import StandardResponseMixin
from portal.models import (
    Department, Agent, Ticket, TicketNote, 
    TicketAssignmentHistory, TicketAttachment, User
)
from django.core.exceptions import ObjectDoesNotExist
from .ticket_serializers import (
    DepartmentSerializer, AgentSerializer, TicketListSerializer,
    TicketDetailSerializer, TicketCreateSerializer, TicketAttachmentSerializer,
    TicketNoteSerializer, TicketNoteCreateSerializer,
    TicketAssignmentSerializer, TicketReassignmentSerializer,
    TicketStatusUpdateSerializer, TicketPriorityUpdateSerializer
)
from portal.permissions import HasPermission, IsRole, IsRoleOrHigher


class DepartmentViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Department management ViewSet
    
    Endpoints:
    - GET /api/v1/departments/ - List all departments
    - POST /api/v1/departments/ - Create department (Admin only)
    - GET /api/v1/departments/{id}/ - Get department details
    - PUT /api/v1/departments/{id}/ - Update department (Admin only)
    - DELETE /api/v1/departments/{id}/ - Delete department (Admin only)
    - POST /api/v1/departments/{id}/assign-agent/ - Assign agent to department
    - DELETE /api/v1/departments/{id}/remove-agent/{agent_id}/ - Remove agent
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'can_view_all_tickets']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'destroy', 'assign_agent', 'remove_agent']:
            return [IsAuthenticated(), IsRoleOrHigher('admin')]
        return [IsAuthenticated()]
    
    def create(self, request, *args, **kwargs):
        """Create department"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return self.success_response(
            message="Department created successfully",
            data=serializer.data,
            status_code=status.HTTP_201_CREATED,
            request=request
        )
    
    @action(detail=True, methods=['post'])
    def assign_agent(self, request, pk=None):
        """Assign agent to department"""
        department = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return self.error_response(
                message="user_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        
        try:
            user = User.objects.get(id=user_id)
            agent, created = Agent.objects.get_or_create(
                user=user,
                department=department,
                defaults={'is_available': True}
            )
            
            if not created:
                return self.error_response(
                    message="Agent already assigned to this department",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    request=request
                )
            
            serializer = AgentSerializer(agent)
            return self.success_response(
                message="Agent assigned successfully",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED,
                request=request
            )
        except User.DoesNotExist:
            return self.error_response(
                message="User not found",
                status_code=status.HTTP_404_NOT_FOUND,
                request=request
            )
    
    @action(detail=True, methods=['delete'], url_path='remove-agent/(?P<agent_id>[^/.]+)')
    def remove_agent(self, request, pk=None, agent_id=None):
        """Remove agent from department"""
        department = self.get_object()
        
        try:
            agent = Agent.objects.get(id=agent_id, department=department)
            # Check if agent has active tickets
            active_tickets = Ticket.objects.filter(
                assigned_to=agent.user,
                status__in=['NEW', 'OPEN', 'IN_PROGRESS', 'PENDING']
            ).count()
            
            if active_tickets > 0:
                return self.error_response(
                    message=f"Cannot remove agent with {active_tickets} active tickets",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    request=request
                )
            
            agent.delete()
            return self.success_response(
                message="Agent removed successfully",
                request=request
            )
        except Agent.DoesNotExist:
            return self.error_response(
                message="Agent not found in this department",
                status_code=status.HTTP_404_NOT_FOUND,
                request=request
            )


class AgentViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Agent management ViewSet
    
    Endpoints:
    - GET /api/v1/agents/ - List all agents
    - POST /api/v1/agents/ - Create agent (Admin only)
    - GET /api/v1/agents/{id}/ - Get agent details
    - PUT /api/v1/agents/{id}/ - Update agent
    - DELETE /api/v1/agents/{id}/ - Delete agent
    - GET /api/v1/agents/{id}/performance/ - Get agent performance metrics
    """
    queryset = Agent.objects.select_related('user', 'department').all()
    serializer_class = AgentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['department', 'is_available']
    search_fields = ['user__username', 'user__profile__email', 'department__name']
    ordering_fields = ['current_tickets', 'created_at']
    ordering = ['-created_at']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'destroy']:
            return [IsAuthenticated(), IsRoleOrHigher('admin')]
        return [IsAuthenticated()]
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get agent performance metrics"""
        agent = self.get_object()
        
        # Calculate metrics
        total_tickets = Ticket.objects.filter(assigned_to=agent.user).count()
        resolved_tickets = Ticket.objects.filter(
            assigned_to=agent.user,
            status='RESOLVED'
        ).count()
        
        open_tickets = Ticket.objects.filter(
            assigned_to=agent.user,
            status__in=['NEW', 'OPEN', 'IN_PROGRESS', 'PENDING']
        ).count()
        
        # Average resolution time (in hours)
        resolved_tickets_with_time = Ticket.objects.filter(
            assigned_to=agent.user,
            status='RESOLVED',
            resolved_at__isnull=False
        ).exclude(created_at__isnull=True)
        
        avg_resolution_time = None
        if resolved_tickets_with_time.exists():
            resolution_times = []
            for ticket in resolved_tickets_with_time:
                if ticket.resolved_at and ticket.created_at:
                    delta = ticket.resolved_at - ticket.created_at
                    resolution_times.append(delta.total_seconds() / 3600)  # Convert to hours
            
            if resolution_times:
                avg_resolution_time = sum(resolution_times) / len(resolution_times)
        
        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_resolved = Ticket.objects.filter(
            assigned_to=agent.user,
            status='RESOLVED',
            resolved_at__gte=thirty_days_ago
        ).count()
        
        data = {
            'agent_id': agent.id,
            'agent_name': agent.user.profile.full_name if hasattr(agent.user, 'profile') else agent.user.username,
            'total_tickets': total_tickets,
            'resolved_tickets': resolved_tickets,
            'open_tickets': open_tickets,
            'avg_resolution_time_hours': round(avg_resolution_time, 2) if avg_resolution_time else None,
            'recent_resolved_30_days': recent_resolved,
            'current_tickets': agent.current_tickets,
            'max_tickets': agent.max_tickets,
            'is_available': agent.is_available
        }
        
        return self.success_response(
            message="Agent performance metrics retrieved successfully",
            data=data,
            request=request
        )


class TicketViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Ticket management ViewSet
    
    Endpoints:
    - GET /api/v1/tickets/ - List tickets (filtered by permissions)
    - POST /api/v1/tickets/ - Create ticket
    - GET /api/v1/tickets/{id}/ - Get ticket details
    - PUT /api/v1/tickets/{id}/ - Update ticket
    - DELETE /api/v1/tickets/{id}/ - Delete ticket (Admin only)
    - POST /api/v1/tickets/{id}/assign/ - Assign ticket to agent
    - POST /api/v1/tickets/{id}/reassign/ - Reassign ticket
    - POST /api/v1/tickets/{id}/pick/ - Agent picks ticket (self-assign)
    - POST /api/v1/tickets/{id}/notes/ - Add note to ticket
    - GET /api/v1/tickets/{id}/history/ - Get ticket history
    - POST /api/v1/tickets/{id}/attachments/ - Upload attachment
    - PUT /api/v1/tickets/{id}/status/ - Update ticket status
    - GET /api/v1/tickets/unassigned/ - Get unassigned tickets
    - GET /api/v1/tickets/my-tickets/ - Get user's tickets
    """
    queryset = Ticket.objects.select_related(
        'created_by', 'assigned_to', 'department'
    ).prefetch_related('notes', 'attachments').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'department', 'assigned_to', 'created_by']
    search_fields = ['ticket_id', 'subject', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'status']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return TicketCreateSerializer
        elif self.action == 'list':
            return TicketListSerializer
        return TicketDetailSerializer
    
    def get_queryset(self):
        """Filter queryset based on user role and permissions"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Super Admin and Admin can see all tickets
        if user.role_code in ['super', 'admin']:
            return queryset
        
        # Department Manager can see all tickets in their department
        if user.role_code == 'dept_manager':
            # Get user's department
            try:
                agent = user.agent_profile
                if agent and agent.department:
                    return queryset.filter(department=agent.department)
            except (Agent.DoesNotExist, AttributeError):
                pass
        
        # Support Agent can see tickets assigned to them or in their department
        if user.role_code == 'support_agent':
            try:
                agent = user.agent_profile
                if agent and agent.department:
                    # Tickets assigned to agent or in their department
                    return queryset.filter(
                        Q(assigned_to=user) | 
                        Q(department=agent.department)
                    )
                else:
                    # Only tickets assigned to them
                    return queryset.filter(assigned_to=user)
            except (Agent.DoesNotExist, AttributeError):
                return queryset.filter(assigned_to=user)
        
        # Business users (Customer, Retailer, etc.) can only see their own tickets
        return queryset.filter(created_by=user)
    
    def create(self, request, *args, **kwargs):
        """Create new ticket"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        
        # Auto-assign if department is specified and has agents
        if ticket.department:
            self._auto_assign_ticket(ticket)
        
        detail_serializer = TicketDetailSerializer(ticket, context={'request': request})
        return self.success_response(
            message="Ticket created successfully",
            data=detail_serializer.data,
            status_code=status.HTTP_201_CREATED,
            request=request
        )
    
    def _auto_assign_ticket(self, ticket):
        """Auto-assign ticket using round-robin"""
        available_agents = Agent.objects.filter(
            department=ticket.department,
            is_available=True
        ).order_by('current_tickets', 'id')
        
        for agent in available_agents:
            if agent.can_accept_ticket():
                ticket.assign_to_agent(agent.user)
                break
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign ticket to agent (Admin/Manager only)"""
        ticket = self.get_object()
        serializer = TicketAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        agent_id = serializer.validated_data['agent_id']
        reason = serializer.validated_data.get('reason', 'Manual assignment')
        
        try:
            agent_user = User.objects.get(id=agent_id)
            # Verify agent belongs to ticket's department
            if ticket.department:
                agent = Agent.objects.filter(
                    user=agent_user,
                    department=ticket.department
                ).first()
                if not agent:
                    return self.error_response(
                        message="Agent does not belong to ticket's department",
                        status_code=status.HTTP_400_BAD_REQUEST,
                        request=request
                    )
            
            old_agent = ticket.assigned_to
            ticket.assign_to_agent(agent_user, assigned_by=request.user)
            
            # Create assignment history
            TicketAssignmentHistory.objects.create(
                ticket=ticket,
                assigned_from=old_agent,
                assigned_to=agent_user,
                assigned_by=request.user,
                reason=reason
            )
            
            detail_serializer = TicketDetailSerializer(ticket, context={'request': request})
            return self.success_response(
                message="Ticket assigned successfully",
                data=detail_serializer.data,
                request=request
            )
        except User.DoesNotExist:
            return self.error_response(
                message="Agent not found",
                status_code=status.HTTP_404_NOT_FOUND,
                request=request
            )
    
    @action(detail=True, methods=['post'])
    def reassign(self, request, pk=None):
        """Reassign ticket to another agent"""
        ticket = self.get_object()
        serializer = TicketReassignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        agent_id = serializer.validated_data['agent_id']
        reason = serializer.validated_data.get('reason', 'Reassignment')
        
        try:
            agent_user = User.objects.get(id=agent_id)
            old_agent = ticket.assigned_to
            
            ticket.assign_to_agent(agent_user, assigned_by=request.user)
            
            # Create assignment history
            TicketAssignmentHistory.objects.create(
                ticket=ticket,
                assigned_from=old_agent,
                assigned_to=agent_user,
                assigned_by=request.user,
                reason=reason
            )
            
            detail_serializer = TicketDetailSerializer(ticket, context={'request': request})
            return self.success_response(
                message="Ticket reassigned successfully",
                data=detail_serializer.data,
                request=request
            )
        except User.DoesNotExist:
            return self.error_response(
                message="Agent not found",
                status_code=status.HTTP_404_NOT_FOUND,
                request=request
            )
    
    @action(detail=True, methods=['post'])
    def pick(self, request, pk=None):
        """Agent picks ticket (self-assignment)"""
        ticket = self.get_object()
        
        # Check if ticket is already assigned
        if ticket.assigned_to:
            return self.error_response(
                message="Ticket is already assigned",
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        
        # Verify user is an agent in the ticket's department
        if ticket.department:
            try:
                agent = request.user.agent_profile
                if not agent or agent.department != ticket.department:
                    return self.error_response(
                        message="You are not an agent in this ticket's department",
                        status_code=status.HTTP_403_FORBIDDEN,
                        request=request
                    )
                
                if not agent.can_accept_ticket():
                    return self.error_response(
                        message="You have reached your maximum ticket limit",
                        status_code=status.HTTP_400_BAD_REQUEST,
                        request=request
                    )
            except (Agent.DoesNotExist, AttributeError):
                return self.error_response(
                    message="You are not an agent",
                    status_code=status.HTTP_403_FORBIDDEN,
                    request=request
                )
        
        ticket.assign_to_agent(request.user, assigned_by=request.user)
        
        # Create assignment history
        TicketAssignmentHistory.objects.create(
            ticket=ticket,
            assigned_from=None,
            assigned_to=request.user,
            assigned_by=request.user,
            reason="Self-assigned by agent"
        )
        
        detail_serializer = TicketDetailSerializer(ticket, context={'request': request})
        return self.success_response(
            message="Ticket picked successfully",
            data=detail_serializer.data,
            request=request
        )
    
    @action(detail=True, methods=['post'])
    def notes(self, request, pk=None):
        """Add note to ticket"""
        ticket = self.get_object()
        serializer = TicketNoteCreateSerializer(
            data=request.data,
            context={'ticket': ticket, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        note = serializer.save()
        
        note_serializer = TicketNoteSerializer(note)
        return self.success_response(
            message="Note added successfully",
            data=note_serializer.data,
            status_code=status.HTTP_201_CREATED,
            request=request
        )
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get ticket assignment history"""
        ticket = self.get_object()
        history = ticket.assignment_history.all().order_by('-created_at')
        
        data = [
            {
                'id': h.id,
                'assigned_from': h.assigned_from.username if h.assigned_from else None,
                'assigned_to': h.assigned_to.username if h.assigned_to else None,
                'assigned_by': h.assigned_by.username if h.assigned_by else None,
                'reason': h.reason,
                'created_at': h.created_at
            }
            for h in history
        ]
        
        return self.success_response(
            message="Ticket history retrieved successfully",
            data=data,
            request=request
        )
    
    @action(detail=True, methods=['post'])
    def attachments(self, request, pk=None):
        """Upload attachment to ticket"""
        ticket = self.get_object()
        
        if 'file' not in request.FILES:
            return self.error_response(
                message="File is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        
        attachment = TicketAttachment.objects.create(
            ticket=ticket,
            file=request.FILES['file'],
            uploaded_by=request.user
        )
        
        serializer = TicketAttachmentSerializer(attachment, context={'request': request})
        return self.success_response(
            message="Attachment uploaded successfully",
            data=serializer.data,
            status_code=status.HTTP_201_CREATED,
            request=request
        )
    
    @action(detail=True, methods=['put'])
    def status(self, request, pk=None):
        """Update ticket status"""
        ticket = self.get_object()
        serializer = TicketStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        ticket.update_status(new_status, request.user)
        
        detail_serializer = TicketDetailSerializer(ticket, context={'request': request})
        return self.success_response(
            message="Ticket status updated successfully",
            data=detail_serializer.data,
            request=request
        )
    
    @action(detail=False, methods=['get'])
    def unassigned(self, request):
        """Get unassigned tickets"""
        queryset = self.get_queryset().filter(assigned_to__isnull=True, status='NEW')
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = TicketListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = TicketListSerializer(queryset, many=True, context={'request': request})
        return self.success_response(
            message="Unassigned tickets retrieved successfully",
            data=serializer.data,
            request=request
        )
    
    @action(detail=False, methods=['get'])
    def my_tickets(self, request):
        """Get current user's tickets"""
        queryset = self.get_queryset().filter(created_by=request.user)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = TicketListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = TicketListSerializer(queryset, many=True, context={'request': request})
        return self.success_response(
            message="Your tickets retrieved successfully",
            data=serializer.data,
            request=request
        )
