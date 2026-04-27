"""
Portal ticket management views.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, CreateView
from django.db import models

from portal.models import (
    User,
    Department,
    Agent,
    Ticket,
    TicketNote,
    TicketAssignmentHistory,
)


class TicketListView(ListView):
    """Ticket list view with filtering"""
    model = Ticket
    template_name = 'portal/tickets/list.html'
    context_object_name = 'tickets'
    paginate_by = 20

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        queryset = Ticket.objects.select_related(
            'created_by', 'assigned_to', 'department'
        ).all()
        user = self.request.user
        if getattr(user, 'role_code', None) in ['super_admin', 'admin']:
            pass
        elif getattr(user, 'role_code', None) == 'employee':
            try:
                agent = getattr(user, 'agent_profile', None)
                if agent and agent.department:
                    queryset = queryset.filter(department=agent.department)
            except (Agent.DoesNotExist, AttributeError):
                queryset = queryset.none()
        elif getattr(user, 'role_code', None) == 'employee':
            try:
                agent = getattr(user, 'agent_profile', None)
                if agent and agent.department:
                    queryset = queryset.filter(
                        models.Q(assigned_to=user) |
                        models.Q(department=agent.department)
                    )
                else:
                    queryset = queryset.filter(assigned_to=user)
            except (Agent.DoesNotExist, AttributeError):
                queryset = queryset.filter(assigned_to=user)
        else:
            queryset = queryset.filter(created_by=user)
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        department_id = self.request.GET.get('department')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(ticket_id__icontains=search) |
                models.Q(subject__icontains=search) |
                models.Q(description__icontains=search)
            )
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Ticket.STATUS_CHOICES
        context['priority_choices'] = Ticket.PRIORITY_CHOICES
        context['departments'] = Department.objects.filter(is_active=True)
        queryset = self.get_queryset()
        context['total_tickets'] = queryset.count()
        context['open_tickets'] = queryset.filter(
            status__in=['NEW', 'OPEN', 'IN_PROGRESS', 'PENDING']
        ).count()
        context['resolved_tickets'] = queryset.filter(status='RESOLVED').count()
        context['closed_tickets'] = queryset.filter(status='CLOSED').count()
        from portal.services.hub_ticket_ivr_service import user_may_use_hub_ivr
        context['show_hub_ivr'] = user_may_use_hub_ivr(self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        """Quick IVR from ticket list (no ticket context)."""
        if request.POST.get('action') != 'hub_ivr_call':
            return redirect('ticket_list')
        from portal.services.hub_ticket_ivr_service import initiate_hub_ticket_ivr, user_may_use_hub_ivr

        if not user_may_use_hub_ivr(request.user):
            messages.error(request, 'You do not have permission to start IVR calls.')
            return redirect('ticket_list')
        ok, user_msg, _raw = initiate_hub_ticket_ivr(
            from_raw=(request.POST.get('ivr_from') or '').strip(),
            to_raw=(request.POST.get('ivr_to') or '').strip(),
            ticket=None,
            actor=request.user,
            request=request,
        )
        if ok:
            messages.success(request, user_msg)
        else:
            messages.error(request, user_msg)
        return redirect('ticket_list')


class TicketDetailView(DetailView):
    """Ticket detail view"""
    model = Ticket
    template_name = 'portal/tickets/detail.html'
    context_object_name = 'ticket'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        queryset = Ticket.objects.select_related(
            'created_by', 'assigned_to', 'department'
        ).prefetch_related('notes', 'attachments', 'assignment_history')
        user = self.request.user
        if getattr(user, 'role_code', None) in ['super_admin', 'admin']:
            return queryset
        elif getattr(user, 'role_code', None) == 'employee':
            try:
                agent = getattr(user, 'agent_profile', None)
                if agent and agent.department:
                    return queryset.filter(department=agent.department)
            except (Agent.DoesNotExist, AttributeError):
                pass
        elif getattr(user, 'role_code', None) == 'employee':
            try:
                agent = getattr(user, 'agent_profile', None)
                if agent and agent.department:
                    return queryset.filter(
                        models.Q(assigned_to=user) |
                        models.Q(department=agent.department)
                    )
            except (Agent.DoesNotExist, AttributeError):
                pass
            return queryset.filter(assigned_to=user)
        return queryset.filter(created_by=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticket = self.object
        context['internal_notes'] = ticket.notes.filter(is_internal=True).order_by('-created_at')
        context['customer_notes'] = ticket.notes.filter(is_internal=False).order_by('-created_at')
        context['all_notes'] = ticket.notes.all().order_by('-created_at')
        context['attachments'] = ticket.attachments.all().order_by('-uploaded_at')
        context['assignment_history'] = ticket.assignment_history.all().order_by('-created_at')[:10]
        user = self.request.user
        if getattr(user, 'role_code', None) in ['super_admin', 'admin', 'employee']:
            if ticket.department:
                context['available_agents'] = Agent.objects.filter(
                    department=ticket.department,
                    is_available=True
                ).select_related('user')
            else:
                context['available_agents'] = Agent.objects.filter(
                    is_available=True
                ).select_related('user')
        context['status_choices'] = Ticket.STATUS_CHOICES
        context['priority_choices'] = Ticket.PRIORITY_CHOICES
        from portal.services.hub_ticket_ivr_service import user_may_use_hub_ivr
        context['show_hub_ivr'] = user_may_use_hub_ivr(self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        ticket = self.get_object()
        action = request.POST.get('action')
        user = request.user
        if action == 'update_status':
            new_status = request.POST.get('status')
            if new_status in dict(Ticket.STATUS_CHOICES):
                ticket.update_status(new_status, user)
                messages.success(request, f'Ticket status updated to {new_status}')
        elif action == 'update_priority':
            new_priority = request.POST.get('priority')
            if new_priority in dict(Ticket.PRIORITY_CHOICES):
                ticket.priority = new_priority
                ticket.save()
                messages.success(request, f'Ticket priority updated to {new_priority}')
        elif action == 'assign':
            agent_id = request.POST.get('agent_id')
            try:
                agent_user = User.objects.get(id=agent_id)
                old_agent = ticket.assigned_to
                ticket.assign_to_agent(agent_user, assigned_by=user)
                TicketAssignmentHistory.objects.create(
                    ticket=ticket,
                    assigned_from=old_agent,
                    assigned_to=agent_user,
                    assigned_by=user,
                    reason=request.POST.get('reason', 'Manual assignment')
                )
                messages.success(request, f'Ticket assigned to {agent_user.username}')
            except User.DoesNotExist:
                messages.error(request, 'Agent not found')
        elif action == 'pick':
            try:
                agent = getattr(user, 'agent_profile', None)
                if not agent or (ticket.department and agent.department != ticket.department):
                    messages.error(request, 'You are not an agent in this ticket\'s department')
                elif not agent.can_accept_ticket():
                    messages.error(request, 'You have reached your maximum ticket limit')
                else:
                    ticket.assign_to_agent(user, assigned_by=user)
                    TicketAssignmentHistory.objects.create(
                        ticket=ticket,
                        assigned_from=None,
                        assigned_to=user,
                        assigned_by=user,
                        reason='Self-assigned by agent'
                    )
                    messages.success(request, 'Ticket picked successfully')
            except (Agent.DoesNotExist, AttributeError):
                messages.error(request, 'You are not an agent')
        elif action == 'add_note':
            content = request.POST.get('content', '').strip()
            is_internal = request.POST.get('is_internal') == 'on'
            if content:
                TicketNote.objects.create(
                    ticket=ticket,
                    created_by=user,
                    content=content,
                    is_internal=is_internal
                )
                messages.success(request, 'Note added successfully')
            else:
                messages.error(request, 'Note content is required')
        elif action == 'hub_ivr_call':
            from portal.services.hub_ticket_ivr_service import initiate_hub_ticket_ivr, user_may_use_hub_ivr

            if not user_may_use_hub_ivr(user):
                messages.error(request, 'You do not have permission to start IVR calls from tickets.')
            else:
                from_phone = (request.POST.get('ivr_from') or request.POST.get('from_phone') or '').strip()
                to_phone = (request.POST.get('ivr_to') or request.POST.get('to_phone') or '').strip()
                ok, user_msg, _raw = initiate_hub_ticket_ivr(
                    from_raw=from_phone,
                    to_raw=to_phone,
                    ticket=ticket,
                    actor=user,
                    request=request,
                )
                if ok:
                    messages.success(request, user_msg)
                    try:
                        TicketNote.objects.create(
                            ticket=ticket,
                            created_by=user,
                            content='[System] IVR call initiated via Hub (Kaleyra click-to-call). See Hub logs (category: Kaleyra) for masked details.',
                            is_internal=True,
                        )
                    except Exception:
                        pass
                else:
                    messages.error(request, user_msg)
        return redirect('ticket_detail', pk=ticket.pk)


class TicketCreateView(CreateView):
    """Create new ticket"""
    model = Ticket
    template_name = 'portal/tickets/create.html'
    fields = ['subject', 'description', 'priority', 'category', 'department']

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['subject'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]',
            'placeholder': 'Enter ticket subject'
        })
        form.fields['description'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]',
            'rows': 6,
            'placeholder': 'Describe your issue in detail'
        })
        form.fields['priority'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]'
        })
        form.fields['category'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]',
            'placeholder': 'Optional category'
        })
        form.fields['department'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC]'
        })
        form.fields['department'].queryset = Department.objects.filter(is_active=True)
        form.fields['department'].required = False
        return form

    def form_valid(self, form):
        ticket = form.save(commit=False)
        ticket.created_by = self.request.user
        ticket.save()
        if ticket.department:
            available_agents = Agent.objects.filter(
                department=ticket.department,
                is_available=True
            ).order_by('current_tickets', 'id')
            for agent in available_agents:
                if agent.can_accept_ticket():
                    ticket.assign_to_agent(agent.user)
                    break
        messages.success(self.request, f'Ticket {ticket.ticket_id} created successfully')
        return redirect('ticket_detail', pk=ticket.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['priority_choices'] = Ticket.PRIORITY_CHOICES
        context['departments'] = Department.objects.filter(is_active=True)
        return context
