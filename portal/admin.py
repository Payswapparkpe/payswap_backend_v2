"""
Django Admin configuration for portal app
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from portal.models import User, Profile, Role, KYC, Wallet, WalletTransaction, UserPermission


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'status', 'created_at']
    list_filter = ['type', 'status', 'created_at']
    search_fields = ['name', 'email', 'phone']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'hierarchy_level', 'mfa_required']
    list_filter = ['category', 'mfa_required']
    search_fields = ['name', 'code']
    filter_horizontal = ['default_permissions']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'first_name', 'email', 'phone', 'role_code', 'is_active', 'email_verified', 'mfa_configured', 'kyc_completed']
    list_filter = ['role_code', 'is_active', 'email_verified', 'mfa_configured', 'kyc_completed', 'created_at']
    search_fields = ['username', 'email', 'first_name', 'phone']
    readonly_fields = ['username', 'created_at', 'updated_at', 'last_login_ip']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Required Information', {
            'fields': ('first_name', 'email', 'phone', 'username', 'role_code')
        }),
        ('Portal Information', {
            'fields': ('profile', 'role', 'email_verified', 'email_verified_at')
        }),
        ('KYC Information', {
            'fields': ('kyc_completed', 'kyc_status')
        }),
        ('MFA Information', {
            'fields': ('mfa_enabled', 'mfa_configured', 'mfa_method', 'totp_secret')
        }),
        ('Security', {
            'fields': ('last_login_ip', 'created_by')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'fields': ('first_name', 'email', 'phone', 'username', 'role_code', 'password1', 'password2', 'profile')
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
