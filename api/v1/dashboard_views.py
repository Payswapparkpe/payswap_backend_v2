"""
Dashboard and Analytics Views for API v1
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, Avg, F
from django.utils import timezone
from datetime import timedelta

from api.mixins.response_mixin import StandardResponseMixin
from portal.models import Ticket, Department, Agent, User
from portal.permissions import IsRoleOrHigher
from django.db.models import Q


class DashboardOverviewView(StandardResponseMixin, APIView):
    """
    Dashboard overview endpoint
    
    GET /api/v1/dashboard/overview/
    Returns ticket statistics and overview data
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get dashboard overview"""
        user = request.user
        
        # Base queryset based on user role
        if user.role_code in ['super', 'admin']:
            tickets_qs = Ticket.objects.all()
        elif user.role_code == 'dept_manager':
            # Get user's department
            try:
                agent = user.agent_profile
                if agent and agent.department:
                    tickets_qs = Ticket.objects.filter(department=agent.department)
                else:
                    tickets_qs = Ticket.objects.none()
            except (Agent.DoesNotExist, AttributeError):
                tickets_qs = Ticket.objects.none()
        elif user.role_code == 'support_agent':
            try:
                agent = user.agent_profile
                if agent and agent.department:
                    tickets_qs = Ticket.objects.filter(
                        Q(assigned_to=user) | Q(department=agent.department)
                    )
                else:
                    tickets_qs = Ticket.objects.filter(assigned_to=user)
            except (Agent.DoesNotExist, AttributeError):
                tickets_qs = Ticket.objects.filter(assigned_to=user)
        else:
            tickets_qs = Ticket.objects.filter(created_by=user)
        
        # Calculate statistics
        total_tickets = tickets_qs.count()
        open_tickets = tickets_qs.filter(status__in=['NEW', 'OPEN', 'IN_PROGRESS', 'PENDING']).count()
        resolved_tickets = tickets_qs.filter(status='RESOLVED').count()
        closed_tickets = tickets_qs.filter(status='CLOSED').count()
        
        # Today's statistics
        today = timezone.now().date()
        resolved_today = tickets_qs.filter(
            status='RESOLVED',
            resolved_at__date=today
        ).count()
        
        # Average resolution time (in hours)
        resolved_with_time = tickets_qs.filter(
            status='RESOLVED',
            resolved_at__isnull=False
        ).exclude(created_at__isnull=True)
        
        avg_resolution_time = None
        if resolved_with_time.exists():
            resolution_times = []
            for ticket in resolved_with_time:
                if ticket.resolved_at and ticket.created_at:
                    delta = ticket.resolved_at - ticket.created_at
                    resolution_times.append(delta.total_seconds() / 3600)
            
            if resolution_times:
                avg_resolution_time = round(sum(resolution_times) / len(resolution_times), 2)
        
        # Tickets by status
        tickets_by_status = tickets_qs.values('status').annotate(count=Count('id'))
        status_breakdown = {item['status']: item['count'] for item in tickets_by_status}
        
        # Tickets by priority
        tickets_by_priority = tickets_qs.values('priority').annotate(count=Count('id'))
        priority_breakdown = {item['priority']: item['count'] for item in tickets_by_priority}
        
        data = {
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'resolved_tickets': resolved_tickets,
            'closed_tickets': closed_tickets,
            'resolved_today': resolved_today,
            'avg_resolution_time_hours': avg_resolution_time,
            'tickets_by_status': status_breakdown,
            'tickets_by_priority': priority_breakdown
        }
        
        return self.success_response(
            message="Dashboard overview retrieved successfully",
            data=data,
            request=request
        )


class AgentPerformanceView(StandardResponseMixin, APIView):
    """
    Agent performance metrics endpoint
    
    GET /api/v1/dashboard/agent-performance/
    Returns agent performance statistics
    """
    permission_classes = [IsAuthenticated, IsRoleOrHigher('admin')]
    
    def get(self, request):
        """Get agent performance metrics"""
        agents = Agent.objects.select_related('user', 'department').all()
        
        performance_data = []
        for agent in agents:
            agent_tickets = Ticket.objects.filter(assigned_to=agent.user)
            
            total = agent_tickets.count()
            resolved = agent_tickets.filter(status='RESOLVED').count()
            open_count = agent_tickets.filter(
                status__in=['NEW', 'OPEN', 'IN_PROGRESS', 'PENDING']
            ).count()
            
            # Average resolution time
            resolved_with_time = agent_tickets.filter(
                status='RESOLVED',
                resolved_at__isnull=False
            ).exclude(created_at__isnull=True)
            
            avg_resolution_time = None
            if resolved_with_time.exists():
                resolution_times = []
                for ticket in resolved_with_time:
                    if ticket.resolved_at and ticket.created_at:
                        delta = ticket.resolved_at - ticket.created_at
                        resolution_times.append(delta.total_seconds() / 3600)
                
                if resolution_times:
                    avg_resolution_time = round(sum(resolution_times) / len(resolution_times), 2)
            
            # Recent activity (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_resolved = agent_tickets.filter(
                status='RESOLVED',
                resolved_at__gte=thirty_days_ago
            ).count()
            
            performance_data.append({
                'agent_id': agent.id,
                'agent_name': agent.user.profile.full_name if hasattr(agent.user, 'profile') else agent.user.username,
                'username': agent.user.username,
                'department': agent.department.name,
                'total_tickets': total,
                'resolved_tickets': resolved,
                'open_tickets': open_count,
                'avg_resolution_time_hours': avg_resolution_time,
                'recent_resolved_30_days': recent_resolved,
                'current_tickets': agent.current_tickets,
                'max_tickets': agent.max_tickets,
                'is_available': agent.is_available
            })
        
        return self.success_response(
            message="Agent performance metrics retrieved successfully",
            data=performance_data,
            request=request
        )


class DepartmentStatsView(StandardResponseMixin, APIView):
    """
    Department statistics endpoint
    
    GET /api/v1/dashboard/department-stats/
    Returns department-wise ticket statistics
    """
    permission_classes = [IsAuthenticated, IsRoleOrHigher('admin')]
    
    def get(self, request):
        """Get department statistics"""
        departments = Department.objects.all()
        
        stats_data = []
        for dept in departments:
            dept_tickets = Ticket.objects.filter(department=dept)
            
            total = dept_tickets.count()
            open_count = dept_tickets.filter(
                status__in=['NEW', 'OPEN', 'IN_PROGRESS', 'PENDING']
            ).count()
            resolved = dept_tickets.filter(status='RESOLVED').count()
            closed = dept_tickets.filter(status='CLOSED').count()
            
            # Resolution rate
            resolution_rate = round((resolved / total * 100), 2) if total > 0 else 0
            
            # Average resolution time
            resolved_with_time = dept_tickets.filter(
                status='RESOLVED',
                resolved_at__isnull=False
            ).exclude(created_at__isnull=True)
            
            avg_resolution_time = None
            if resolved_with_time.exists():
                resolution_times = []
                for ticket in resolved_with_time:
                    if ticket.resolved_at and ticket.created_at:
                        delta = ticket.resolved_at - ticket.created_at
                        resolution_times.append(delta.total_seconds() / 3600)
                
                if resolution_times:
                    avg_resolution_time = round(sum(resolution_times) / len(resolution_times), 2)
            
            # Agents in department
            agents_count = dept.agents.count()
            
            stats_data.append({
                'department_id': dept.id,
                'department_name': dept.name,
                'total_tickets': total,
                'open_tickets': open_count,
                'resolved_tickets': resolved,
                'closed_tickets': closed,
                'resolution_rate_percent': resolution_rate,
                'avg_resolution_time_hours': avg_resolution_time,
                'agents_count': agents_count
            })
        
        return self.success_response(
            message="Department statistics retrieved successfully",
            data=stats_data,
            request=request
        )


class TicketsByStatusView(StandardResponseMixin, APIView):
    """
    Tickets by status analytics endpoint
    
    GET /api/v1/analytics/tickets-by-status/
    Returns ticket distribution by status
    """
    permission_classes = [IsAuthenticated, IsRoleOrHigher('admin')]
    
    def get(self, request):
        """Get tickets by status"""
        tickets_by_status = Ticket.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        data = [
            {
                'status': item['status'],
                'count': item['count']
            }
            for item in tickets_by_status
        ]
        
        return self.success_response(
            message="Tickets by status retrieved successfully",
            data=data,
            request=request
        )


class ResolutionTimeView(StandardResponseMixin, APIView):
    """
    Resolution time analytics endpoint
    
    GET /api/v1/analytics/resolution-time/
    Returns resolution time statistics
    """
    permission_classes = [IsAuthenticated, IsRoleOrHigher('admin')]
    
    def get(self, request):
        """Get resolution time statistics"""
        resolved_tickets = Ticket.objects.filter(
            status='RESOLVED',
            resolved_at__isnull=False
        ).exclude(created_at__isnull=True)
        
        resolution_times = []
        for ticket in resolved_tickets:
            if ticket.resolved_at and ticket.created_at:
                delta = ticket.resolved_at - ticket.created_at
                resolution_times.append({
                    'ticket_id': ticket.ticket_id,
                    'hours': round(delta.total_seconds() / 3600, 2),
                    'days': round(delta.total_seconds() / 86400, 2)
                })
        
        if resolution_times:
            hours_list = [rt['hours'] for rt in resolution_times]
            avg_hours = round(sum(hours_list) / len(hours_list), 2)
            min_hours = round(min(hours_list), 2)
            max_hours = round(max(hours_list), 2)
        else:
            avg_hours = min_hours = max_hours = None
        
        data = {
            'total_resolved': len(resolution_times),
            'avg_resolution_time_hours': avg_hours,
            'min_resolution_time_hours': min_hours,
            'max_resolution_time_hours': max_hours,
            'resolution_times': resolution_times[:50]  # Limit to 50 for response size
        }
        
        return self.success_response(
            message="Resolution time statistics retrieved successfully",
            data=data,
            request=request
        )
