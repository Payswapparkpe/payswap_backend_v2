"""
Ticket Management Serializers for API v1
"""
from rest_framework import serializers
from portal.models import (
    Department, Agent, Ticket, TicketNote, 
    TicketAssignmentHistory, TicketAttachment, User
)


class DepartmentSerializer(serializers.ModelSerializer):
    """Department serializer"""
    agents_count = serializers.SerializerMethodField()
    tickets_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = [
            'id', 'name', 'description', 'is_active', 
            'can_view_all_tickets', 'created_by', 'created_by_name',
            'agents_count', 'tickets_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_agents_count(self, obj):
        """Get number of agents in department"""
        return obj.agents.count()
    
    def get_tickets_count(self, obj):
        """Get number of tickets in department"""
        return obj.tickets.count()
    
    def get_created_by_name(self, obj):
        """Get creator's name"""
        return obj.created_by.username if obj.created_by else None


class AgentSerializer(serializers.ModelSerializer):
    """Agent serializer"""
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.profile.email', read_only=True)
    full_name = serializers.CharField(source='user.profile.full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    can_accept_ticket = serializers.SerializerMethodField()
    
    class Meta:
        model = Agent
        fields = [
            'id', 'user_id', 'username', 'email', 'full_name',
            'department', 'department_name', 'is_available',
            'max_tickets', 'current_tickets', 'can_accept_ticket',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_tickets', 'created_at', 'updated_at']
    
    def get_can_accept_ticket(self, obj):
        """Check if agent can accept new tickets"""
        return obj.can_accept_ticket()


class TicketAttachmentSerializer(serializers.ModelSerializer):
    """Ticket attachment serializer"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = TicketAttachment
        fields = [
            'id', 'ticket', 'file', 'file_url', 'file_name', 
            'file_size', 'file_type', 'uploaded_by', 'uploaded_by_name',
            'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at', 'file_size', 'file_type']
    
    def get_file_url(self, obj):
        """Get file URL"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class TicketNoteSerializer(serializers.ModelSerializer):
    """Ticket note serializer"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    created_by_full_name = serializers.CharField(source='created_by.profile.full_name', read_only=True)
    
    class Meta:
        model = TicketNote
        fields = [
            'id', 'ticket', 'created_by', 'created_by_name', 
            'created_by_full_name', 'content', 'is_internal', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TicketListSerializer(serializers.ModelSerializer):
    """Ticket list serializer (lightweight)"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    notes_count = serializers.SerializerMethodField()
    attachments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_id', 'subject', 'status', 'priority', 'category',
            'created_by', 'created_by_name', 'assigned_to', 'assigned_to_name',
            'department', 'department_name', 'tags', 'notes_count',
            'attachments_count', 'created_at', 'updated_at', 'resolved_at', 'closed_at'
        ]
        read_only_fields = ['id', 'ticket_id', 'created_at', 'updated_at', 'resolved_at', 'closed_at']
    
    def get_notes_count(self, obj):
        """Get number of notes"""
        return obj.notes.count()
    
    def get_attachments_count(self, obj):
        """Get number of attachments"""
        return obj.attachments.count()


class TicketDetailSerializer(serializers.ModelSerializer):
    """Ticket detail serializer (full)"""
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    created_by_full_name = serializers.CharField(source='created_by.profile.full_name', read_only=True)
    created_by_email = serializers.EmailField(source='created_by.profile.email', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    assigned_to_full_name = serializers.CharField(source='assigned_to.profile.full_name', read_only=True, allow_null=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    notes = TicketNoteSerializer(many=True, read_only=True)
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    assignment_history = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_id', 'subject', 'description', 'status', 'priority', 'category',
            'created_by', 'created_by_name', 'created_by_full_name', 'created_by_email',
            'assigned_to', 'assigned_to_name', 'assigned_to_full_name',
            'department', 'department_name', 'tags',
            'notes', 'attachments', 'assignment_history',
            'created_at', 'updated_at', 'resolved_at', 'closed_at'
        ]
        read_only_fields = [
            'id', 'ticket_id', 'created_at', 'updated_at', 
            'resolved_at', 'closed_at', 'notes', 'attachments', 'assignment_history'
        ]
    
    def get_assignment_history(self, obj):
        """Get assignment history"""
        history = obj.assignment_history.all()[:10]  # Last 10 assignments
        return [
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


class TicketCreateSerializer(serializers.ModelSerializer):
    """Ticket creation serializer"""
    
    class Meta:
        model = Ticket
        fields = [
            'subject', 'description', 'priority', 'category', 
            'department', 'tags'
        ]
    
    def create(self, validated_data):
        """Create ticket with auto-generated ticket_id"""
        validated_data['created_by'] = self.context['request'].user
        ticket = super().create(validated_data)
        return ticket


class TicketAssignmentSerializer(serializers.Serializer):
    """Ticket assignment serializer"""
    agent_id = serializers.IntegerField(help_text="ID of agent to assign ticket to")
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Reason for assignment"
    )


class TicketReassignmentSerializer(serializers.Serializer):
    """Ticket reassignment serializer"""
    agent_id = serializers.IntegerField(help_text="ID of agent to reassign ticket to")
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Reason for reassignment"
    )


class TicketStatusUpdateSerializer(serializers.Serializer):
    """Ticket status update serializer"""
    status = serializers.ChoiceField(
        choices=Ticket.STATUS_CHOICES,
        help_text="New ticket status"
    )


class TicketPriorityUpdateSerializer(serializers.Serializer):
    """Ticket priority update serializer"""
    priority = serializers.ChoiceField(
        choices=Ticket.PRIORITY_CHOICES,
        help_text="New ticket priority"
    )


class TicketNoteCreateSerializer(serializers.ModelSerializer):
    """Ticket note creation serializer"""
    
    class Meta:
        model = TicketNote
        fields = ['content', 'is_internal']
    
    def create(self, validated_data):
        """Create note with ticket and user context"""
        validated_data['ticket'] = self.context['ticket']
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
