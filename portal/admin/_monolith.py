"""
Django Admin configuration for portal app
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.messages import success as messages_success, error as messages_error
from django.urls import path
from django.shortcuts import render, redirect
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from portal.models import (
    User, Profile, Role, KYC, Wallet, WalletTransaction, UserPermission, LogEntry, CashfreeAPILog,
    EmailQueue,
    Department, Agent, Ticket, TicketNote, TicketAssignmentHistory, TicketAttachment,
    Vehicle, VehicleQRCode,
    ConnectPredefinedMessage, ConnectThread, ConnectMessage, ConnectCallLog, ConnectReport,
    GiftVoucherBrand, GiftVoucher, GiftVoucherTransaction, GiftVoucherOTP, 
    BulkVoucherIssuanceBatch, GiftVoucherAuditLog, VoucherClient,
    ResellerPartner, APIKey, APIKeyUsageLog,
    ResellerPartnerPricing, ResellerPartnerTransaction, ResellerPartnerSettlement,
    Service, ServiceCost, BBPSBillerCategory, BBPSOperator, RBIRuleConfiguration,
    HubVendorCostRecord, HubCostRateConfig, HubIncomeRecord, ServiceIncomeConfig,
    IdempotencyRecord,
    ApprovalRequest,
    ApiVendor, VendorApi, ServiceFlowStep,
    ParkPeVoucherBalance, ParkPeVoucherTransaction, ParkPeServiceConfig,
    ParkPePaymentGatewayConfig, ParkPePaymentOrder,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'first_name', 'last_name', 'email', 'phone', 'type', 'status', 'created_at']
    list_filter = ['type', 'status', 'email_verified', 'phone_verified', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'user__username']
    readonly_fields = ['user', 'created_at', 'updated_at', 'last_updated_by']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Personal Information', {
            'fields': ('first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender', 'marital_status', 'profile_photo')
        }),
        ('Contact Details', {
            'fields': ('email', 'phone', 'alternate_phone', 'email_verified', 'phone_verified')
        }),
        ('Demographic Details', {
            'fields': ('nationality', 'country_of_residence', 'state', 'city', 'pincode', 'address_line_1', 'address_line_2')
        }),
        ('Banking Details', {
            'fields': ('bank_name', 'account_holder_name', 'account_number', 'ifsc_code', 'branch_name', 'account_type')
        }),
        ('Taxation Details', {
            'fields': ('pan_number', 'aadhaar_number', 'gst_number', 'tax_id')
        }),
        ('Business Details', {
            'fields': ('type', 'business_name', 'business_registration_number', 'business_type')
        }),
        ('Settings & Preferences', {
            'fields': ('language_preference', 'timezone', 'currency_preference', 'notification_preferences', 'settings')
        }),
        ('Account Security', {
            'fields': ('security_question_1', 'security_answer_1', 'security_question_2', 'security_answer_2', 'backup_codes', 'recovery_email', 'last_password_change')
        }),
        ('Status & Metadata', {
            'fields': ('status', 'created_by', 'last_updated_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'hierarchy_level', 'mfa_required']
    list_filter = ['category', 'mfa_required']
    search_fields = ['name', 'code']
    filter_horizontal = ['default_permissions']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'get_email', 'get_phone', 'role_code', 'is_active', 'email_verified', 'mfa_configured', 'kyc_completed']
    list_filter = ['role_code', 'is_active', 'email_verified', 'mfa_configured', 'kyc_completed', 'created_at']
    search_fields = ['username']
    readonly_fields = ['username', 'created_at', 'updated_at', 'last_login_ip', 'login_count']
    
    def get_email(self, obj):
        return obj.profile.email if hasattr(obj, 'profile') and obj.profile else '-'
    get_email.short_description = 'Email'
    
    def get_phone(self, obj):
        return obj.profile.phone if hasattr(obj, 'profile') and obj.profile else '-'
    get_phone.short_description = 'Phone'
    
    fieldsets = (
        ('Credentials', {
            'fields': ('username', 'password')
        }),
        ('Role & Authorization', {
            'fields': ('role_code', 'role')
        }),
        ('Login & Session', {
            'fields': ('last_login', 'last_login_ip', 'last_login_user_agent', 'login_count')
        }),
        ('Email Verification', {
            'fields': ('email_verified', 'email_verified_at')
        }),
        ('KYC Status', {
            'fields': ('kyc_completed', 'kyc_status')
        }),
        ('MFA Information', {
            'fields': ('mfa_enabled', 'mfa_configured', 'mfa_method', 'totp_secret')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {
            'fields': ('date_joined',)
        }),
        ('Security & Audit', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'fields': ('username', 'role_code', 'password1', 'password2'),
            'description': 'Username will be auto-generated if not provided. Profile will be created separately.'
        }),
    )


@admin.register(KYC)
class KYCAdmin(admin.ModelAdmin):
    list_display = ['user', 'document_type', 'status', 'verification_vendor', 'verified_at']
    list_filter = ['status', 'document_type', 'verification_vendor', 'created_at']
    search_fields = ['user__username', 'document_number']
    readonly_fields = ['created_at', 'updated_at', 'verification_response']
    
    actions = ['approve_kyc', 'reject_kyc']
    
    def approve_kyc(self, request, queryset):
        for kyc in queryset:
            kyc.approve(request.user)
        self.message_user(request, f'{queryset.count()} KYC(s) approved.')
    approve_kyc.short_description = 'Approve selected KYC'
    
    def reject_kyc(self, request, queryset):
        for kyc in queryset:
            kyc.reject(request.user, 'Rejected via admin')
        self.message_user(request, f'{queryset.count()} KYC(s) rejected.')
    reject_kyc.short_description = 'Reject selected KYC'


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'currency', 'status', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at', 'encrypted_seed_phrase']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'transaction_type', 'amount', 'status', 'created_at']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['wallet__user__username', 'reference']
    readonly_fields = ['created_at', 'encrypted_details']


# ParkPe (no wallet – voucher balance only)
@admin.register(ParkPeVoucherBalance)
class ParkPeVoucherBalanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'currency', 'updated_at']
    list_filter = ['currency']
    search_fields = ['user__username']
    readonly_fields = ['updated_at']


@admin.register(ParkPeVoucherTransaction)
class ParkPeVoucherTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'transaction_type', 'service_code', 'reference_id', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['user__username', 'reference_id', 'service_code']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(ParkPeServiceConfig)
class ParkPeServiceConfigAdmin(admin.ModelAdmin):
    list_display = ['service_code', 'voucher_allowed', 'pg_allowed', 'is_active', 'updated_at']
    list_filter = ['voucher_allowed', 'pg_allowed', 'is_active']
    search_fields = ['service_code']
    list_editable = ['voucher_allowed', 'pg_allowed', 'is_active']


@admin.register(ParkPePaymentGatewayConfig)
class ParkPePaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ['gateway', 'service_code', 'enabled', 'is_default_for_voucher_purchase', 'merchant_id', 'credential_key', 'updated_at']
    list_filter = ['gateway', 'enabled', 'is_default_for_voucher_purchase']
    search_fields = ['gateway', 'service_code', 'merchant_id', 'credential_key']
    list_editable = ['enabled', 'is_default_for_voucher_purchase']


@admin.register(ParkPePaymentOrder)
class ParkPePaymentOrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'amount', 'gateway', 'status', 'created_at']
    list_filter = ['gateway', 'status', 'created_at']
    search_fields = ['order_id', 'user__username', 'reference_id']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'permission', 'is_active', 'granted_at', 'revoked_at']
    list_filter = ['is_active', 'granted_at']
    search_fields = ['user__username', 'permission__name']
    readonly_fields = ['granted_at']


@admin.register(CashfreeAPILog)
class CashfreeAPILogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'api_type', 'status', 'endpoint', 'status_code', 'response_time', 'user', 'verification_id']
    list_filter = ['status', 'api_type', 'timestamp', 'status_code']
    search_fields = ['endpoint', 'verification_id', 'request_id', 'error_message', 'user__username']
    readonly_fields = ['timestamp', 'api_type', 'status', 'endpoint', 'method', 'request_payload', 'response_data',
                       'status_code', 'response_time', 'error_message', 'error_code', 'error_type', 'traceback',
                       'user', 'request_id', 'client_ip', 'user_agent', 'verification_id', 'log_entry']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    fieldsets = (
        ('API Call Information', {
            'fields': ('timestamp', 'api_type', 'status', 'endpoint', 'method', 'verification_id')
        }),
        ('Request Details', {
            'fields': ('request_payload',)
        }),
        ('Response Details', {
            'fields': ('status_code', 'response_time', 'response_data')
        }),
        ('Error Information', {
            'fields': ('error_message', 'error_code', 'error_type', 'traceback'),
            'classes': ('collapse',)
        }),
        ('User & Context', {
            'fields': ('user', 'request_id', 'client_ip', 'user_agent')
        }),
        ('Related Log Entry', {
            'fields': ('log_entry',)
        }),
    )


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'log_level', 'category', 'message_short', 'user', 'url', 'client_ip', 'resolved']
    list_filter = ['log_level', 'category', 'resolved', 'timestamp', 'module_name']
    search_fields = ['message', 'module_name', 'url', 'request_id', 'user__username', 'client_ip']
    readonly_fields = ['timestamp', 'log_level', 'category', 'message', 'module_name', 'url', 'request_id', 
                       'response_id', 'user', 'client_ip', 'user_agent', 'session_id', 'extra_data', 
                       'traceback', 'exception_type']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Log Information', {
            'fields': ('timestamp', 'log_level', 'category', 'message', 'module_name', 'url')
        }),
        ('Request Tracking', {
            'fields': ('request_id', 'response_id', 'client_ip', 'user_agent', 'session_id')
        }),
        ('User Information', {
            'fields': ('user',)
        }),
        ('Error Details', {
            'fields': ('exception_type', 'traceback'),
            'classes': ('collapse',)
        }),
        ('Additional Data', {
            'fields': ('extra_data',),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('resolved', 'resolved_at', 'resolved_by', 'notes')
        }),
    )
    
    actions = ['mark_resolved', 'mark_unresolved']
    
    def message_short(self, obj):
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message
    message_short.short_description = 'Message'
    
    def mark_resolved(self, request, queryset):
        for log in queryset:
            log.mark_resolved(resolved_by=request.user)
        self.message_user(request, f'{queryset.count()} log entry/entries marked as resolved.')
    mark_resolved.short_description = 'Mark selected logs as resolved'
    
    def mark_unresolved(self, request, queryset):
        for log in queryset:
            log.mark_unresolved()
        self.message_user(request, f'{queryset.count()} log entry/entries marked as unresolved.')
    mark_unresolved.short_description = 'Mark selected logs as unresolved'
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically, not manually
    
    def has_change_permission(self, request, obj=None):
        # Only allow changing resolution status
        return request.user.is_staff


@admin.register(EmailQueue)
class EmailQueueAdmin(admin.ModelAdmin):
    """Durable email queue: view pending/failed and resend without Celery."""
    list_display = ['id', 'to_email_masked', 'subject_short', 'status', 'retry_count', 'created_at', 'sent_at']
    list_filter = ['status', 'use_parkpe_smtp', 'created_at']
    search_fields = ['to_email', 'subject', 'last_error']
    readonly_fields = ['to_email', 'subject', 'body_html', 'body_text', 'status', 'retry_count', 'last_error',
                       'related_entity', 'use_parkpe_smtp', 'created_at', 'sent_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    list_per_page = 50

    def to_email_masked(self, obj):
        if not obj.to_email:
            return '-'
        parts = obj.to_email.split('@')
        return f"{parts[0][:2]}***@{parts[1]}" if len(parts) == 2 else '***@***'
    to_email_masked.short_description = 'To'

    def subject_short(self, obj):
        return (obj.subject[:50] + '...') if obj.subject and len(obj.subject) > 50 else (obj.subject or '-')
    subject_short.short_description = 'Subject'

    actions = ['resend_selected']

    def resend_selected(self, request, queryset):
        from portal.services.email_queue_service import send_email_from_queue_row
        from django.utils import timezone
        sent, failed = 0, 0
        for row in queryset.filter(status__in=[EmailQueue.STATUS_PENDING, EmailQueue.STATUS_FAILED]):
            success, err = send_email_from_queue_row(row)
            if success:
                row.status = EmailQueue.STATUS_SENT
                row.sent_at = timezone.now()
                row.save(update_fields=['status', 'sent_at'])
                sent += 1
            else:
                row.retry_count = (row.retry_count or 0) + 1
                row.last_error = (err or '')[:2000]
                row.save(update_fields=['retry_count', 'last_error'])
                failed += 1
        self.message_user(request, f'Resent: {sent} sent, {failed} failed.')
    resend_selected.short_description = 'Resend selected (PENDING/FAILED)'

    def has_add_permission(self, request):
        return False  # Emails are enqueued by app, not created in admin


# ============================================================================
# TICKET MANAGEMENT ADMIN
# ============================================================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'can_view_all_tickets', 'agents_count', 'tickets_count', 'created_by', 'created_at']
    list_filter = ['is_active', 'can_view_all_tickets', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def agents_count(self, obj):
        return obj.agents.count()
    agents_count.short_description = 'Agents'
    
    def tickets_count(self, obj):
        return obj.tickets.count()
    tickets_count.short_description = 'Tickets'


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['user', 'department', 'is_available', 'current_tickets', 'max_tickets', 'created_at']
    list_filter = ['department', 'is_available', 'created_at']
    search_fields = ['user__username', 'department__name']
    readonly_fields = ['created_at', 'updated_at', 'current_tickets']
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('user', 'department')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_id', 'subject', 'status', 'priority', 'created_by', 'assigned_to', 'department', 'created_at']
    list_filter = ['status', 'priority', 'department', 'created_at']
    search_fields = ['ticket_id', 'subject', 'description', 'created_by__username', 'assigned_to__username']
    readonly_fields = ['ticket_id', 'created_at', 'updated_at', 'resolved_at', 'closed_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_id', 'subject', 'description', 'status', 'priority', 'category', 'tags')
        }),
        ('Assignment', {
            'fields': ('created_by', 'assigned_to', 'department')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'resolved_at', 'closed_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('created_by', 'assigned_to', 'department')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['registration_number', 'user', 'brand', 'model', 'year', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['registration_number', 'brand', 'model', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user']


@admin.register(VehicleQRCode)
class VehicleQRCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'vehicle', 'created_at']
    search_fields = ['code', 'vehicle__registration_number']
    readonly_fields = ['created_at']
    raw_id_fields = ['vehicle']


@admin.register(ConnectPredefinedMessage)
class ConnectPredefinedMessageAdmin(admin.ModelAdmin):
    list_display = ['code', 'label_en', 'is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['code', 'label_en', 'body_en']
    ordering = ['order', 'code']


@admin.register(ConnectThread)
class ConnectThreadAdmin(admin.ModelAdmin):
    list_display = ['id', 'vehicle', 'scanner_user']
    search_fields = ['vehicle__registration_number', 'scanner_user__username']
    raw_id_fields = ['vehicle', 'scanner_user']


@admin.register(ConnectMessage)
class ConnectMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'thread', 'sender', 'message_type', 'body_short', 'created_at']
    list_filter = ['message_type', 'created_at']
    search_fields = ['body', 'sender__username']
    readonly_fields = ['created_at']
    raw_id_fields = ['thread', 'sender', 'predefined_message']

    def body_short(self, obj):
        return (obj.body[:60] + '...') if obj.body and len(obj.body) > 60 else (obj.body or '')
    body_short.short_description = 'Body'


@admin.register(ConnectCallLog)
class ConnectCallLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'vehicle_id', 'scanner_phone_masked', 'owner_id', 'success', 'created_at']
    list_filter = ['success', 'created_at']
    search_fields = ['qr_code', 'scanner_phone_masked']
    readonly_fields = ['created_at']
    ordering = ['-created_at']


@admin.register(ConnectReport)
class ConnectReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'reporter_user', 'reported_user', 'thread', 'status', 'ticket', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['reason', 'reporter_user__username', 'reported_user__username']
    readonly_fields = ['created_at']
    raw_id_fields = ['reporter_user', 'reported_user', 'thread', 'ticket']
    ordering = ['-created_at']


@admin.register(TicketNote)
class TicketNoteAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'created_by', 'is_internal', 'content_short', 'created_at']
    list_filter = ['is_internal', 'created_at']
    search_fields = ['ticket__ticket_id', 'content', 'created_by__username']
    readonly_fields = ['created_at']
    
    def content_short(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
    content_short.short_description = 'Content'
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('ticket', 'created_by')


@admin.register(TicketAssignmentHistory)
class TicketAssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'assigned_from', 'assigned_to', 'assigned_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['ticket__ticket_id', 'assigned_from__username', 'assigned_to__username']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('ticket', 'assigned_from', 'assigned_to', 'assigned_by')
    
    def has_add_permission(self, request):
        return False  # Assignment history is created automatically


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'file_name', 'file_size', 'file_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['ticket__ticket_id', 'file_name', 'uploaded_by__username']
    readonly_fields = ['uploaded_at', 'file_size', 'file_type']
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('ticket', 'uploaded_by')


# ============================================================================
# GIFT VOUCHER MANAGEMENT ADMIN
# ============================================================================

@admin.register(GiftVoucherBrand)
class GiftVoucherBrandAdmin(admin.ModelAdmin):
    list_display = ['brand_name', 'brand_code', 'onboarding_status', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'onboarding_status', 'created_at']
    search_fields = ['brand_name', 'brand_code', 'contact_email', 'contact_phone']
    readonly_fields = [
        'brand_code', 'created_at', 'updated_at', 'onboarding_completed_at',
        'onboarding_approved_by', 'rejected_at', 'agreement_signed_at', 'terms_accepted_at'
    ]
    
    fieldsets = (
        ('Brand Information', {
            'fields': ('brand_name', 'brand_code', 'status')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'contact_email', 'contact_phone', 'address')
        }),
        ('Onboarding Status', {
            'fields': ('onboarding_status', 'onboarding_completed_at', 'onboarding_approved_by', 'onboarding_notes')
        }),
        ('Business Details', {
            'fields': ('business_type', 'business_reg_no', 'pan_number', 'gst_number')
        }),
        ('Banking Information', {
            'fields': ('bank_name', 'bank_ifsc_code', 'account_holder_name', 'bank_account_number'),
            'classes': ('collapse',)
        }),
        ('Documents', {
            'fields': (
                'business_registration_doc', 'pan_document', 'gst_certificate',
                'bank_statement', 'agreement_document', 'other_documents'
            ),
            'classes': ('collapse',)
        }),
        ('Agreement & Terms', {
            'fields': ('terms_accepted', 'terms_accepted_at', 'agreement_signed', 'agreement_signed_at')
        }),
        ('Rejection Information', {
            'fields': ('rejection_reason', 'rejected_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['approve_onboarding', 'reject_onboarding']
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('created_by', 'updated_by', 'onboarding_approved_by')
    
    def approve_onboarding(self, request, queryset):
        """Approve selected brands' onboarding"""
        count = 0
        for brand in queryset:
            if brand.onboarding_status == 'SUBMITTED':
                brand.approve_onboarding(request.user)
                count += 1
        self.message_user(request, f'{count} brand(s) onboarding approved.')
    approve_onboarding.short_description = 'Approve onboarding for selected brands'
    
    def reject_onboarding(self, request, queryset):
        """Reject selected brands' onboarding"""
        count = 0
        for brand in queryset:
            if brand.onboarding_status == 'SUBMITTED':
                brand.reject_onboarding(request.user, 'Rejected via admin action')
                count += 1
        self.message_user(request, f'{count} brand(s) onboarding rejected.')
    reject_onboarding.short_description = 'Reject onboarding for selected brands'


@admin.register(GiftVoucher)
class GiftVoucherAdmin(admin.ModelAdmin):
    list_display = ['voucher_code', 'brand', 'original_amount', 'current_balance', 'status', 'issued_at', 'created_by']
    list_filter = ['status', 'brand', 'currency', 'issued_at']
    search_fields = ['voucher_code', 'reference_number', 'mobile_number', 'brand__brand_name']
    readonly_fields = ['voucher_code', 'voucher_code_hash', 'pin_hash', 'reference_number', 'issued_at', 'last_transaction_at']
    date_hierarchy = 'issued_at'
    ordering = ['-issued_at']
    
    fieldsets = (
        ('Voucher Information', {
            'fields': ('brand', 'voucher_code', 'reference_number', 'voucher_code_hash', 'pin_hash')
        }),
        ('Amount & Status', {
            'fields': ('original_amount', 'current_balance', 'currency', 'status')
        }),
        ('Recipient Information', {
            'fields': ('mobile_number',)
        }),
        ('PIN Security', {
            'fields': ('pin_retry_count', 'pin_blocked_until', 'last_pin_change', 'pin_history'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('issued_at', 'last_transaction_at')
        }),
        ('Metadata', {
            'fields': ('created_by', 'metadata')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('brand', 'created_by')


@admin.register(GiftVoucherTransaction)
class GiftVoucherTransactionAdmin(admin.ModelAdmin):
    list_display = ['voucher', 'transaction_type', 'transaction_amount', 'transaction_status', 'created_at']
    list_filter = ['transaction_type', 'transaction_status', 'created_at']
    search_fields = ['voucher__voucher_code', 'voucher__reference_number', 'transaction_ref']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('voucher', 'transaction_type', 'transaction_ref', 'transaction_amount', 'transaction_status')
        }),
        ('Balance Information', {
            'fields': ('balance_before', 'balance_after')
        }),
        ('Redemption Details', {
            'fields': ('redemption_method', 'failure_reason')
        }),
        ('Request Details', {
            'fields': ('ip_address', 'user_agent', 'created_at')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('voucher')


@admin.register(GiftVoucherOTP)
class GiftVoucherOTPAdmin(admin.ModelAdmin):
    list_display = ['voucher', 'otp_purpose', 'mobile_number', 'is_verified', 'attempt_count', 'generated_at', 'expires_at']
    list_filter = ['otp_purpose', 'is_verified', 'generated_at']
    search_fields = ['voucher__voucher_code', 'mobile_number']
    readonly_fields = ['otp_hash', 'generated_at', 'expires_at', 'verified_at', 'attempt_count']
    date_hierarchy = 'generated_at'
    ordering = ['-generated_at']
    
    fieldsets = (
        ('OTP Information', {
            'fields': ('voucher', 'otp_purpose', 'mobile_number', 'otp_hash')
        }),
        ('Verification Status', {
            'fields': ('is_verified', 'attempt_count', 'generated_at', 'expires_at', 'verified_at')
        }),
        ('Request Details', {
            'fields': ('ip_address',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('voucher')


@admin.register(VoucherClient)
class VoucherClientAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'client_code', 'brand', 'is_default', 'status', 'created_at', 'created_by']
    list_filter = ['status', 'is_default', 'brand', 'created_at']
    search_fields = ['client_name', 'client_code', 'contact_email', 'contact_phone', 'brand__brand_name']
    readonly_fields = ['client_code', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Client Information', {
            'fields': ('brand', 'client_name', 'client_code', 'is_default', 'status')
        }),
        ('Contact Details', {
            'fields': ('contact_person', 'contact_email', 'contact_phone')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'metadata')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('brand', 'created_by')


@admin.register(BulkVoucherIssuanceBatch)
class BulkVoucherIssuanceBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_reference', 'brand', 'client', 'total_vouchers', 'successful_vouchers', 'failed_vouchers', 'status', 'issuance_method', 'created_at', 'created_by']
    list_filter = ['status', 'brand', 'issuance_method', 'issuer_type', 'created_at']
    search_fields = ['batch_reference', 'batch_reference_number', 'brand__brand_name', 'client__client_name', 'created_by__username']
    readonly_fields = ['batch_reference', 'batch_reference_number', 'processed_vouchers', 'successful_vouchers', 'failed_vouchers', 'started_at', 'completed_at', 'created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Batch Information', {
            'fields': ('brand', 'client', 'batch_reference', 'batch_reference_number', 'status', 'total_vouchers', 'issuance_method')
        }),
        ('Issuer Information', {
            'fields': ('issued_by', 'issuer_type')
        }),
        ('Denomination Breakdown', {
            'fields': ('denomination_breakdown',),
            'classes': ('collapse',)
        }),
        ('Processing Status', {
            'fields': ('processed_vouchers', 'successful_vouchers', 'failed_vouchers', 'started_at', 'completed_at')
        }),
        ('Files', {
            'fields': ('uploaded_file_path', 'result_file_path')
        }),
        ('Error Log', {
            'fields': ('error_log',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset().select_related('brand', 'created_by')


@admin.register(GiftVoucherAuditLog)
class GiftVoucherAuditLogAdmin(admin.ModelAdmin):
    list_display = ['entity_type', 'entity_id', 'action', 'user_id', 'created_at']
    list_filter = ['entity_type', 'action', 'created_at']
    search_fields = ['entity_type', 'description', 'user_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Entity Information', {
            'fields': ('entity_type', 'entity_id', 'action')
        }),
        ('Details', {
            'fields': ('description', 'old_values', 'new_values', 'user_id', 'ip_address', 'user_agent', 'created_at')
        }),
    )


@admin.register(ResellerPartner)
class ResellerPartnerAdmin(admin.ModelAdmin):
    list_display = ['partner_code', 'company_name', 'contact_person', 'email', 'status', 'onboarding_status', 'created_at']
    list_filter = ['status', 'onboarding_status', 'business_type', 'created_at']
    search_fields = ['partner_code', 'company_name', 'contact_person', 'email', 'phone']
    readonly_fields = ['partner_code', 'created_at', 'updated_at', 'onboarding_completed_at']
    
    fieldsets = (
        ('Partner Information', {
            'fields': ('partner_code', 'company_name', 'contact_person', 'email', 'phone')
        }),
        ('Business Details', {
            'fields': ('business_type', 'gst_number', 'address')
        }),
        ('Status', {
            'fields': ('status', 'onboarding_status', 'onboarding_completed_at', 'onboarding_approved_by', 'onboarding_notes')
        }),
        ('Wallet', {
            'fields': ('wallet',)
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by')
        }),
    )
    
    actions = ['approve_onboarding', 'reject_onboarding', 'suspend_partner', 'activate_partner']
    
    def approve_onboarding(self, request, queryset):
        from portal.services.reseller_service import ResellerService
        service = ResellerService()
        count = 0
        for partner in queryset:
            if partner.onboarding_status == 'PENDING' or partner.onboarding_status == 'IN_PROGRESS':
                service.approve_onboarding(partner, request.user)
                count += 1
        self.message_user(request, f'{count} partner(s) approved.')
    approve_onboarding.short_description = "Approve selected partners"
    
    def reject_onboarding(self, request, queryset):
        from portal.services.reseller_service import ResellerService
        service = ResellerService()
        count = 0
        for partner in queryset:
            if partner.onboarding_status != 'REJECTED':
                service.reject_onboarding(partner, request.user, 'Rejected by admin')
                count += 1
        self.message_user(request, f'{count} partner(s) rejected.')
    reject_onboarding.short_description = "Reject selected partners"
    
    def suspend_partner(self, request, queryset):
        from portal.services.reseller_service import ResellerService
        service = ResellerService()
        count = 0
        for partner in queryset:
            if partner.status != 'SUSPENDED':
                service.suspend_partner(partner, request.user, 'Suspended by admin')
                count += 1
        self.message_user(request, f'{count} partner(s) suspended.')
    suspend_partner.short_description = "Suspend selected partners"
    
    def activate_partner(self, request, queryset):
        from portal.services.reseller_service import ResellerService
        service = ResellerService()
        count = 0
        for partner in queryset:
            if partner.status == 'SUSPENDED':
                service.activate_partner(partner, request.user)
                count += 1
        self.message_user(request, f'{count} partner(s) activated.')
    activate_partner.short_description = "Activate selected partners"


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['key_name', 'partner', 'key_type', 'status', 'last_used_at', 'created_at']
    list_filter = ['key_type', 'status', 'created_at']
    search_fields = ['key_name', 'partner__company_name', 'partner__partner_code', 'key_prefix']
    readonly_fields = ['api_key', 'api_secret', 'key_prefix', 'created_at', 'updated_at', 'last_used_at', 'revoked_at']
    
    fieldsets = (
        ('Key Information', {
            'fields': ('partner', 'key_name', 'key_type', 'status')
        }),
        ('Security', {
            'fields': ('api_key', 'api_secret', 'key_prefix', 'ip_whitelist')
        }),
        ('Permissions & Limits', {
            'fields': ('permissions', 'rate_limit')
        }),
        ('Webhook', {
            'fields': ('webhook_url', 'webhook_secret')
        }),
        ('Expiration', {
            'fields': ('expires_at',)
        }),
        ('Revocation', {
            'fields': ('revoked_at', 'revoked_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_used_at', 'created_by')
        }),
    )
    
    actions = ['revoke_keys']
    
    def revoke_keys(self, request, queryset):
        from portal.services.api_key_service import APIKeyService
        service = APIKeyService()
        count = 0
        for api_key in queryset:
            if api_key.status == 'ACTIVE':
                service.revoke_api_key(api_key, 'Revoked by admin', request.user)
                count += 1
        self.message_user(request, f'{count} API key(s) revoked.')
    revoke_keys.short_description = "Revoke selected API keys"


@admin.register(APIKeyUsageLog)
class APIKeyUsageLogAdmin(admin.ModelAdmin):
    list_display = ['api_key', 'partner', 'endpoint', 'method', 'status_code', 'response_time', 'created_at']
    list_filter = ['status_code', 'method', 'created_at']
    search_fields = ['api_key__key_name', 'partner__company_name', 'endpoint', 'request_id']
    readonly_fields = ['api_key', 'partner', 'endpoint', 'method', 'status_code', 'response_time', 'ip_address', 'user_agent', 'request_id', 'error_message', 'created_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('api_key', 'partner', 'endpoint', 'method', 'request_id')
        }),
        ('Response', {
            'fields': ('status_code', 'response_time', 'error_message')
        }),
        ('Client Information', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ResellerPartnerPricing)
class ResellerPartnerPricingAdmin(admin.ModelAdmin):
    list_display = ['partner', 'service', 'pricing_type', 'commission_type', 'is_active', 'created_at']
    list_filter = ['pricing_type', 'commission_type', 'is_active', 'created_at']
    search_fields = ['partner__company_name', 'partner__partner_code', 'service__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Partner & Service', {
            'fields': ('partner', 'service')
        }),
        ('Pricing Configuration', {
            'fields': ('pricing_type', 'base_price', 'markup_percentage', 'fixed_markup', 'tiered_pricing')
        }),
        ('Commission Configuration', {
            'fields': ('commission_type', 'commission_percentage', 'fixed_commission')
        }),
        ('Status', {
            'fields': ('is_active', 'effective_from', 'effective_until')
        }),
        ('Metadata', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by')
        }),
    )


@admin.register(ResellerPartnerTransaction)
class ResellerPartnerTransactionAdmin(admin.ModelAdmin):
    list_display = ['partner', 'transaction_type', 'amount', 'commission_amount', 'service', 'status', 'transaction_date']
    list_filter = ['transaction_type', 'status', 'transaction_date']
    search_fields = ['partner__company_name', 'reference_id', 'external_reference']
    readonly_fields = ['transaction_date', 'created_at', 'updated_at']
    date_hierarchy = 'transaction_date'
    
    fieldsets = (
        ('Partner & Service', {
            'fields': ('partner', 'service', 'api_key')
        }),
        ('Transaction Details', {
            'fields': ('transaction_type', 'amount', 'currency', 'status', 'transaction_date')
        }),
        ('Commission Details', {
            'fields': ('commission_amount', 'commission_rate', 'base_amount', 'markup_amount')
        }),
        ('Reference', {
            'fields': ('reference_id', 'external_reference', 'description')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'settled_at', 'created_by')
        }),
    )


@admin.register(ResellerPartnerSettlement)
class ResellerPartnerSettlementAdmin(admin.ModelAdmin):
    list_display = ['partner', 'settlement_reference', 'settlement_amount', 'status', 'settlement_period_end', 'completed_at']
    list_filter = ['status', 'settlement_period_end']
    search_fields = ['partner__company_name', 'settlement_reference', 'payment_reference']
    readonly_fields = ['settlement_reference', 'created_at', 'updated_at', 'processed_at', 'completed_at']
    date_hierarchy = 'settlement_period_end'
    
    fieldsets = (
        ('Partner', {
            'fields': ('partner',)
        }),
        ('Settlement Period', {
            'fields': ('settlement_period_start', 'settlement_period_end')
        }),
        ('Financial Summary', {
            'fields': ('total_revenue', 'total_commission', 'total_transactions', 'settlement_amount', 'currency')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'payment_reference')
        }),
        ('Metadata', {
            'fields': ('notes', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at', 'completed_at', 'created_by', 'processed_by')
        }),
    )


class ServiceFlowStepInline(admin.TabularInline):
    model = ServiceFlowStep
    extra = 0
    ordering = ['step_order']
    autocomplete_fields = ['vendor', 'vendor_api']
    fields = ('step_order', 'step_name', 'vendor', 'vendor_api', 'is_mandatory', 'halt_on_failure')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'status', 'is_enabled', 'requires_kyc', 'created_at']
    list_filter = ['status', 'is_enabled', 'requires_kyc', 'category', 'created_at']
    search_fields = ['name', 'code', 'description', 'category']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ServiceFlowStepInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'category', 'description', 'status')
        }),
        ('API Integration', {
            'fields': ('api_provider', 'api_endpoint', 'api_key', 'api_secret')
        }),
        ('Configuration', {
            'fields': ('is_enabled', 'requires_kyc', 'min_balance', 'vendor_config')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )


class VendorApiInline(admin.TabularInline):
    model = VendorApi
    extra = 0
    fields = ('name', 'api_code', 'api_type', 'purpose', 'http_method', 'is_active', 'timeout_seconds', 'retry_allowed')


@admin.register(ApiVendor)
class ApiVendorAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [VendorApiInline]


@admin.register(VendorApi)
class VendorApiAdmin(admin.ModelAdmin):
    list_display = ['name', 'api_code', 'vendor', 'api_type', 'purpose', 'is_active', 'http_method', 'created_at']
    list_filter = ['vendor', 'api_type', 'is_active', 'created_at']
    search_fields = ['name', 'api_code', 'vendor__name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['vendor']


@admin.register(ServiceFlowStep)
class ServiceFlowStepAdmin(admin.ModelAdmin):
    list_display = ['service', 'step_order', 'step_name', 'vendor', 'vendor_api', 'is_mandatory', 'halt_on_failure', 'created_at']
    list_filter = ['service', 'vendor', 'is_mandatory', 'halt_on_failure', 'created_at']
    search_fields = ['step_name', 'service__name', 'vendor__name']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['service', 'vendor', 'vendor_api']
    ordering = ['service', 'step_order']


@admin.register(ServiceCost)
class ServiceCostAdmin(admin.ModelAdmin):
    list_display = ['service', 'cost_type', 'base_cost', 'provides_commission', 'is_active', 'effective_from']
    list_filter = ['cost_type', 'provides_commission', 'is_active', 'effective_from']
    search_fields = ['service__name', 'service__code']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Service', {
            'fields': ('service',)
        }),
        ('Cost Configuration', {
            'fields': ('cost_type', 'base_cost', 'cost_percentage', 'cost_per_transaction', 'tiered_cost')
        }),
        ('Commission', {
            'fields': ('provides_commission', 'commission_on')
        }),
        ('Status', {
            'fields': ('is_active', 'effective_from', 'effective_until')
        }),
        ('Metadata', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by')
        }),
    )


@admin.register(HubVendorCostRecord)
class HubVendorCostRecordAdmin(admin.ModelAdmin):
    list_display = ['service_code', 'vendor_code', 'amount', 'unit_count', 'period_date', 'partner', 'created_at']
    list_filter = ['service_code', 'vendor_code', 'period_date']
    search_fields = ['reference_id', 'vendor_code']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 50


@admin.register(HubCostRateConfig)
class HubCostRateConfigAdmin(admin.ModelAdmin):
    list_display = ['service_code', 'vendor_code', 'unit_cost', 'is_active', 'updated_at']
    list_filter = ['service_code', 'vendor_code', 'is_active']
    search_fields = ['service_code', 'vendor_code']


@admin.register(HubIncomeRecord)
class HubIncomeRecordAdmin(admin.ModelAdmin):
    list_display = ['service_code', 'amount', 'transaction_amount', 'vendor_code', 'partner', 'period_date', 'created_at']
    list_filter = ['service_code', 'vendor_code', 'period_date']
    search_fields = ['reference_id', 'vendor_code']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    list_per_page = 50


@admin.register(ServiceIncomeConfig)
class ServiceIncomeConfigAdmin(admin.ModelAdmin):
    list_display = ['service', 'income_type', 'rate_per_txn', 'rate_percentage', 'vendor_code', 'is_active', 'updated_at']
    list_filter = ['income_type', 'is_active', 'service']
    search_fields = ['service__code', 'vendor_code']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(BBPSBillerCategory)
class BBPSBillerCategoryAdmin(admin.ModelAdmin):
    list_display = ['category_name', 'category_code', 'category_type', 'default_commission_percentage', 'is_active']
    list_filter = ['category_type', 'commission_type', 'is_active']
    search_fields = ['category_name', 'category_code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Service', {
            'fields': ('service',)
        }),
        ('Category Information', {
            'fields': ('category_code', 'category_name', 'category_type', 'description')
        }),
        ('Commission Configuration', {
            'fields': ('commission_type', 'default_commission_percentage', 'default_fixed_commission')
        }),
        ('Cost Configuration', {
            'fields': ('base_cost',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(BBPSOperator)
class BBPSOperatorAdmin(admin.ModelAdmin):
    list_display = ['name', 'biller_id', 'category', 'bbps_enabled', 'is_active', 'updated_at']
    list_filter = ['category', 'bbps_enabled', 'is_active']
    search_fields = ['name', 'biller_id', 'category']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 50


@admin.register(RBIRuleConfiguration)
class RBIRuleConfigurationAdmin(admin.ModelAdmin):
    list_display = ['service', 'rule_name', 'is_active', 'effective_from', 'rbi_circular_reference']
    list_filter = ['is_active', 'effective_from', 'service']
    search_fields = ['rule_name', 'rule_description', 'rbi_circular_reference', 'service__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Service', {
            'fields': ('service',)
        }),
        ('Rule Information', {
            'fields': ('rule_name', 'rule_description', 'rbi_circular_reference')
        }),
        ('Rule Configuration', {
            'fields': ('rule_config',)
        }),
        ('Status', {
            'fields': ('is_active', 'effective_from', 'effective_until')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'created_by')
        }),
    )


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ['scope', 'idempotency_key_short', 'status', 'response_http_status', 'created_at']
    list_filter = ['status', 'response_http_status', 'created_at']
    search_fields = ['scope', 'idempotency_key']
    readonly_fields = ['scope', 'idempotency_key', 'status', 'response_http_status', 'response_body', 'created_at']

    def idempotency_key_short(self, obj):
        return (obj.idempotency_key[:20] + '...') if obj.idempotency_key and len(obj.idempotency_key) > 20 else obj.idempotency_key
    idempotency_key_short.short_description = 'Idempotency Key'


# ============================================================================
# APPROVAL WORKFLOW (4-eye) – read-only; approve/reject via actions and custom view
# ============================================================================

@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    """
    Approval requests are read-only in admin. Execution happens ONLY via
    Approve and execute action (checker). Prevents one-click high-risk execution.
    """
    list_display = [
        'id', 'action_type', 'entity_type', 'entity_id', 'status',
        'requested_by', 'requested_at', 'approved_by', 'approved_at', 'approve_action_link', 'reject_action_link',
    ]
    list_filter = ['status', 'action_type', 'entity_type', 'requested_at']
    search_fields = ['entity_id', 'requested_by__username', 'approved_by__username']
    readonly_fields = [
        'action_type', 'entity_type', 'entity_id', 'payload',
        'requested_by', 'requested_at', 'status',
        'approved_by', 'approved_at', 'rejection_reason', 'execution_result',
    ]
    date_hierarchy = 'requested_at'
    ordering = ['-requested_at']

    fieldsets = (
        ('Request', {
            'fields': ('action_type', 'entity_type', 'entity_id', 'payload', 'requested_by', 'requested_at'),
        }),
        ('Approval', {
            'fields': ('status', 'approved_by', 'approved_at', 'rejection_reason', 'execution_result'),
        }),
    )

    def approve_action_link(self, obj):
        if obj.status != ApprovalRequest.STATUS_PENDING:
            return format_html('<span>{}</span>', obj.get_status_display())
        from django.urls import reverse
        url = reverse('admin:portal_approvalrequest_approve', args=[obj.pk])
        return format_html('<a href="{}">Approve and execute</a>', url)
    approve_action_link.short_description = 'Approve'

    def reject_action_link(self, obj):
        if obj.status != ApprovalRequest.STATUS_PENDING:
            return format_html('<span>—</span>')
        from django.urls import reverse
        url = reverse('admin:portal_approvalrequest_reject', args=[obj.pk])
        return format_html('<a href="{}">Reject</a>', url)
    reject_action_link.short_description = 'Reject'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/approve/', self.admin_site.admin_view(self.approve_view), name='portal_approvalrequest_approve'),
            path('<int:pk>/reject/', self.admin_site.admin_view(self.reject_view), name='portal_approvalrequest_reject'),
        ]
        return custom + urls

    def approve_view(self, request, pk):
        from portal.services.approval_service import approve_and_execute
        req = ApprovalRequest.objects.get(pk=pk)
        if req.status != ApprovalRequest.STATUS_PENDING:
            messages_error(request, f'Request #{pk} is not PENDING (current: {req.status}).')
            return redirect('admin:portal_approvalrequest_changelist')
        if request.user.id == req.requested_by_id:
            messages_error(request, 'Self-approval is not allowed (4-eye).')
            return redirect('admin:portal_approvalrequest_changelist')
        try:
            approve_and_execute(pk, request.user)
            messages_success(request, f'Approval request #{pk} approved and executed.')
        except Exception as e:
            messages_error(request, str(e))
        return redirect('admin:portal_approvalrequest_changelist')

    def reject_view(self, request, pk):
        from portal.services.approval_service import reject
        req = ApprovalRequest.objects.get(pk=pk)
        if req.status != ApprovalRequest.STATUS_PENDING:
            messages_error(request, f'Request #{pk} is not PENDING.')
            return redirect('admin:portal_approvalrequest_changelist')
        if request.user.id == req.requested_by_id:
            messages_error(request, 'Self-approval/reject by maker is not allowed (4-eye).')
            return redirect('admin:portal_approvalrequest_changelist')
        if request.method == 'POST':
            reason = (request.POST.get('rejection_reason') or '').strip() or 'Rejected via admin'
            try:
                reject(pk, request.user, reason)
                messages_success(request, f'Approval request #{pk} rejected.')
                return redirect('admin:portal_approvalrequest_changelist')
            except Exception as e:
                messages_error(request, str(e))
        return render(
            request,
            'admin/portal/approvalrequest/reject_form.html',
            context={'approval_request': req, 'opts': self.model._meta},
        )

    def has_add_permission(self, request):
        # Creation is via approval_service.create_approval_request only (maker flow).
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of approval requests (audit trail).
        return False


# ============================================================================
# AUDIT HISTORY (django-simple-history) – read-only, immutable
# Revert disabled globally via SIMPLE_HISTORY_REVERT_DISABLED = True
# ============================================================================

class ReadOnlyHistoryAdmin(SimpleHistoryAdmin):
    """
    Audit history models: view and search only. No add, edit, delete.
    Compliance: append-only, immutable audit trail.
    """
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Allow viewing list and detail; get_readonly_fields makes form non-editable
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.get_fields()]

    list_display = ['history_id', 'history_date', 'history_user', 'history_type', 'id']
    list_filter = ['history_type', 'history_date', 'history_user']
    search_fields = ['history_id', 'id', 'history_type']
    date_hierarchy = 'history_date'
    ordering = ['-history_date']


# Register historical models (read-only audit)
_AUDITED_MODELS = [
    KYC, Wallet, WalletTransaction, GiftVoucher,
    ResellerPartner, APIKey, ResellerPartnerPricing,
    ResellerPartnerTransaction, ResellerPartnerSettlement,
    Service, ApprovalRequest,
]
for _model in _AUDITED_MODELS:
    _history_model = _model.history.model
    if not admin.site.is_registered(_history_model):
        admin.site.register(_history_model, ReadOnlyHistoryAdmin)
