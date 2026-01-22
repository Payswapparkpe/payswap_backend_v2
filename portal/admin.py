"""
Django Admin configuration for portal app
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from portal.models import User, Profile, Role, KYC, Wallet, WalletTransaction, UserPermission


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


@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'permission', 'is_active', 'granted_at', 'revoked_at']
    list_filter = ['is_active', 'granted_at']
    search_fields = ['user__username', 'permission__name']
    readonly_fields = ['granted_at']
