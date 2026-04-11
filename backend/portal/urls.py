"""
Portal URL Configuration
No "portal" prefix in URLs
"""
from django.urls import path, include
from django.views.generic.base import RedirectView
from portal import views
urlpatterns = [
    # Landing and Auth
    path('', views.LandingPageView.as_view(), name='landing'),
    path('signin/', views.SignInView.as_view(), name='signin'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('signup/otp/', views.SignUpView.as_view(), name='signup_otp'),
    path('logout/', views.sign_out_view, name='logout'),
    
    # Social Auth
    path('accounts/social/callback/', views.social_callback_view, name='social_callback'),
    
    # Profile Completion
    path('profile/complete/', views.ProfileCompletionView.as_view(), name='profile_complete'),
    
    # Password Management
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('password/reset/<uidb64>/<token>/', views.PasswordResetView.as_view(), name='password_reset'),
    path('password/change/', views.PasswordChangeView.as_view(), name='password_change'),
    
    # MFA
    path('mfa/setup/', views.MFASetupView.as_view(), name='mfa_setup'),
    path('mfa/verify/', views.MFAVerifyView.as_view(), name='mfa_verify'),
    path('mfa/resend-otp/', views.resend_otp_view, name='resend_otp'),
    
    # Session lock / PIN unlock (secondary re-unlock; OTP/2FA is primary)
    path('auth/set-pin/', views.SetPinView.as_view(), name='set_pin'),
    path('auth/unlock-with-pin/', views.UnlockWithPinView.as_view(), name='unlock_with_pin'),
    path('auth/unlock-expired/', views.unlock_expired_view, name='unlock_expired'),
    path('auth/lock/', views.lock_screen_view, name='lock_screen'),
    
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/mobikwik-balance/', views.MobikwikBalanceApiView.as_view(), name='dashboard_mobikwik_balance'),
    path('dashboard/business/', views.BusinessOverviewView.as_view(), name='dashboard_business'),
    path('dashboard/hub-pnl/', views.HubPnlView.as_view(), name='dashboard_hub_pnl'),
    path('dashboard/system-map/', RedirectView.as_view(url='/dashboard/', permanent=False), name='system_map'),
    path('dashboard/partner-quality/', RedirectView.as_view(url='/dashboard/projects/', permanent=False), name='partner_quality'),
    path('dashboard/partners/<path:subpath>', RedirectView.as_view(url='/dashboard/projects/', permanent=False), name='partner_ops'),
    path('dashboard/admin/', RedirectView.as_view(url='/dashboard/', permanent=False), name='dashboard_admin'),
    path('dashboard/employee/', views.EmployeeDashboardView.as_view(), name='dashboard_employee'),
    path('dashboard/super/', views.SuperDashboardView.as_view(), name='dashboard_super'),
    path('dashboard/parkpe/transactions/', views.ParkPeTransactionsReportView.as_view(), name='dashboard_parkpe_transactions'),
    path('dashboard/distributor/', views.DistributorDashboardView.as_view(), name='dashboard_distributor'),
    path('dashboard/retailer/', views.RetailerDashboardView.as_view(), name='dashboard_retailer'),
    path('dashboard/customer/', views.CustomerDashboardView.as_view(), name='dashboard_customer'),
    path('dashboard/vendor/', views.VendorDashboardView.as_view(), name='dashboard_vendor'),
    # Hub RBAC (Super Admin only)
    path('dashboard/hub/', views.HubRbacDashboardView.as_view(), name='hub_rbac_dashboard'),
    path('dashboard/hub/departments/', views.DepartmentListView.as_view(), name='hub_rbac_department_list'),
    path('dashboard/hub/departments/add/', views.DepartmentCreateView.as_view(), name='hub_rbac_department_create'),
    path('dashboard/hub/departments/<int:pk>/edit/', views.DepartmentUpdateView.as_view(), name='hub_rbac_department_edit'),
    path('dashboard/hub/projects/', views.ProjectListView.as_view(), name='hub_rbac_project_list'),
    path('dashboard/hub/projects/add/', views.ProjectCreateView.as_view(), name='hub_rbac_project_create'),
    path('dashboard/hub/projects/<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='hub_rbac_project_edit'),
    path('dashboard/hub/roles/', views.HubRoleListView.as_view(), name='hub_rbac_hubrole_list'),
    path('dashboard/hub/roles/add/', views.HubRoleCreateView.as_view(), name='hub_rbac_hubrole_create'),
    path('dashboard/hub/roles/<int:pk>/edit/', views.HubRoleUpdateView.as_view(), name='hub_rbac_hubrole_edit'),
    path('dashboard/hub/assignments/', views.UserHubAssignmentListView.as_view(), name='hub_rbac_assignment_list'),
    path('dashboard/hub/assignments/add/', views.UserHubAssignmentCreateView.as_view(), name='hub_rbac_assignment_create'),
    path('dashboard/hub/assignments/<int:pk>/edit/', views.UserHubAssignmentUpdateView.as_view(), name='hub_rbac_assignment_edit'),
    # Project Management (Admin / Super Admin) – Parkpe & Payswap
    path('dashboard/projects/', views.ProjectManagementView.as_view(), name='project_management'),
    path('dashboard/projects/create-api-key/', views.CreateProjectAPIKeyView.as_view(), name='project_management_create_api_key'),
    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/create/', views.ProfileCreateView.as_view(), name='profile_create'),
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    
    # Settings
    path('settings/', views.SettingsView.as_view(), name='settings'),
    
    # Users
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:user_id>/edit/', views.UserEditView.as_view(), name='user_edit'),
    path('users/<int:user_id>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:user_id>/', views.UserDetailView.as_view(), name='user_detail'),
    
    # KYC
    path('kyc/', views.KYCListView.as_view(), name='kyc_list'),
    path('kyc/submit/', views.KYCSubmitView.as_view(), name='kyc_submit'),
    
    # Wallet
    path('wallet/', views.WalletView.as_view(), name='wallet'),
    path('wallet/transactions/', views.WalletTransactionView.as_view(), name='wallet_transactions'),
    
    # Permissions
    path('permissions/', views.PermissionManageView.as_view(), name='permissions'),
    path('permissions/user/<int:user_id>/manage/', views.PermissionManageUserView.as_view(), name='permissions_manage_user'),
    path('permissions/role/<int:role_id>/manage/', views.PermissionManageRoleView.as_view(), name='permissions_manage_role'),
    path('permissions/assign/', views.assign_permission_view, name='permission_assign'),
    path('permissions/revoke/', views.revoke_permission_view, name='permission_revoke'),
    path('roles/change/', views.change_role_view, name='role_change'),

    # Log Management (All logs including Cashfree)
    path('logs/', views.LogListView.as_view(), name='log_list'),
    path('logs/debug/', views.debug_voucher_logs, name='debug_voucher_logs'),
    path('logs/export/', views.LogExportView.as_view(), name='log_export'),
    path('logs/<int:pk>/', views.LogDetailView.as_view(), name='log_detail'),
    path('logs/<int:log_id>/resolve/', views.log_resolve_view, name='log_resolve'),
    
    # Ticket Management
    path('tickets/', views.TicketListView.as_view(), name='ticket_list'),
    path('tickets/create/', views.TicketCreateView.as_view(), name='ticket_create'),
    path('tickets/<int:pk>/', views.TicketDetailView.as_view(), name='ticket_detail'),
    
    # API Documentation / Explorer – removed; redirect to dashboard
    path('api-docs/', RedirectView.as_view(url='/dashboard/', permanent=False), name='api_docs'),
    path('api-explorer/', RedirectView.as_view(url='/dashboard/', permanent=False), name='api_explorer'),

    # Services Management
    path('services/', views.ServicesIntegratedView.as_view(), name='services_list'),
    # API Vendors: redirect to Services (API Explorer removed)
    path('services/api-vendors/', RedirectView.as_view(url='/services/', permanent=False), name='api_vendor_list'),
    path('services/api-vendors/postman-sync/', views.postman_sync_view, name='postman_sync'),
    path('services/api-vendors/postman-save-key/', views.postman_save_key_view, name='postman_save_key'),
    path('services/api-vendors/<str:vendor_code>/', RedirectView.as_view(url='/services/', permanent=False), name='api_vendor_detail'),
    path('services/api-vendors/<str:vendor_code>/apis/<str:api_code>/try/', views.api_vendor_try_api_view, name='api_vendor_try_api'),
    path('services/<int:service_id>/', views.ServiceDetailView.as_view(), name='service_detail'),
    path('services/<str:service_code>/', views.ServiceDetailByCodeView.as_view(), name='service_detail_by_code'),
    path('services/<int:service_id>/vendor/<str:vendor_code>/', views.VendorDetailView.as_view(), name='vendor_detail'),
    path('services/<int:service_id>/vendor/<str:vendor_code>/save-test-params/', views.save_vendor_test_params_view, name='save_vendor_test_params'),
    path('services/<int:service_id>/vendor/<str:vendor_code>/test-all-apis/', views.test_all_vendor_apis_view, name='test_all_vendor_apis'),
    path('services/<int:service_id>/bbps-test/balance/', views.bbps_test_balance_view, name='bbps_test_balance'),
    path('services/<int:service_id>/bbps-test/billers/', views.bbps_test_billers_view, name='bbps_test_billers'),
    path('services/<int:service_id>/bbps-test/operators/', views.bbps_test_operators_view, name='bbps_test_operators'),
    path('services/<int:service_id>/bbps-test/fetch-bill/', views.bbps_test_fetch_bill_view, name='bbps_test_fetch_bill'),
    path('services/<int:service_id>/bbps-test/pay-bill/', views.bbps_test_pay_bill_view, name='bbps_test_pay_bill'),
    path('services/<int:service_id>/bbps-test/status/', views.bbps_test_status_view, name='bbps_test_status'),
    path('services/<int:service_id>/test-api/', views.test_verification_api_view, name='test_verification_api'),
    path('services/<int:service_id>/toggle-service/', views.toggle_vendor_service_view, name='toggle_vendor_service'),
    path('services/<int:service_id>/manage-bridge-numbers/', views.manage_kaleyra_bridge_numbers_view, name='manage_kaleyra_bridge_numbers'),
    
    # Gift Voucher Management
    path('vouchers/brands/', views.BrandListView.as_view(), name='voucher_brand_list'),
    path('vouchers/brands/create/', views.BrandCreateView.as_view(), name='voucher_brand_create'),
    path('vouchers/brands/<int:brand_id>/', views.BrandDetailView.as_view(), name='voucher_brand_detail'),
    path('vouchers/brands/<int:brand_id>/delete/', views.BrandDeleteView.as_view(), name='voucher_brand_delete'),
    
    # Brand Voucher Dashboard
    path('vouchers/brands/<int:brand_id>/dashboard/', views.BrandVoucherDashboardView.as_view(), name='brand_voucher_dashboard'),
    
    # Voucher Client Management
    path('vouchers/clients/', views.VoucherClientListView.as_view(), name='voucher_client_list'),
    path('vouchers/clients/create/', views.VoucherClientCreateView.as_view(), name='voucher_client_create'),
    path('vouchers/clients/<int:client_id>/', views.VoucherClientDetailView.as_view(), name='voucher_client_detail'),
    path('vouchers/clients/<int:client_id>/delete/', views.VoucherClientDeleteView.as_view(), name='voucher_client_delete'),
    
    # Voucher Batch Management
    path('vouchers/batches/', views.VoucherBatchListView.as_view(), name='voucher_batch_list'),
    path('vouchers/batches/<int:batch_id>/', views.VoucherBatchDetailView.as_view(), name='voucher_batch_detail'),
    path('vouchers/batches/<int:batch_id>/process/', views.VoucherBatchProcessView.as_view(), name='voucher_batch_process'),
    path('vouchers/batches/<int:batch_id>/processing/', views.VoucherBatchProcessingView.as_view(), name='voucher_batch_processing'),
    path('vouchers/batches/<int:batch_id>/processing/status/', views.VoucherBatchProcessingStatusView.as_view(), name='voucher_batch_processing_status'),
    path('vouchers/batches/<int:batch_id>/export/', views.VoucherBatchExportView.as_view(), name='voucher_batch_export'),
    
    # Brand Onboarding
    path('vouchers/brands/onboarding/', views.BrandOnboardingStartView.as_view(), name='brand_onboarding_start'),
    path('vouchers/brands/onboarding/<int:brand_id>/', views.BrandOnboardingStartView.as_view(), name='brand_onboarding_start_brand'),
    path('vouchers/brands/onboarding/<int:brand_id>/step/<int:step>/', views.BrandOnboardingStepView.as_view(), name='brand_onboarding_step'),
    path('vouchers/brands/onboarding/<int:brand_id>/status/', views.BrandOnboardingStatusView.as_view(), name='brand_onboarding_status'),
    
    # Brand Onboarding Admin
    path('vouchers/brands/onboarding/admin/', views.BrandOnboardingAdminListView.as_view(), name='brand_onboarding_admin_list'),
    path('vouchers/brands/onboarding/admin/<int:brand_id>/', views.BrandOnboardingAdminDetailView.as_view(), name='brand_onboarding_admin_detail'),
    
    path('vouchers/issue/single/', views.VoucherIssueSingleView.as_view(), name='voucher_issue_single'),
    path('vouchers/issue/single/success/', views.VoucherIssueSingleSuccessView.as_view(), name='voucher_issue_single_success'),
    path('vouchers/issue/bulk/', views.VoucherIssueBulkView.as_view(), name='voucher_issue_bulk'),
    path('vouchers/issue/bulk/<int:batch_id>/status/', views.BulkIssuanceStatusView.as_view(), name='voucher_bulk_status'),
    path('vouchers/', views.VoucherListView.as_view(), name='voucher_list'),
    path('vouchers/search/', views.VoucherSearchView.as_view(), name='voucher_search'),
    path('vouchers/<int:voucher_id>/', views.VoucherDetailView.as_view(), name='voucher_detail'),
    path('vouchers/reports/issuance/', views.VoucherIssuanceReportView.as_view(), name='voucher_report_issuance'),
    path('vouchers/reports/redemption/', views.VoucherRedemptionReportView.as_view(), name='voucher_report_redemption'),
    path('vouchers/reports/outstanding/', views.VoucherOutstandingBalanceReportView.as_view(), name='voucher_report_outstanding'),
    
    # VoucherX Unified Solution
    path('voucherx/', views.VoucherXDashboardView.as_view(), name='voucherx_dashboard'),
    path('voucherx/balance/', views.VoucherXBalanceCheckView.as_view(), name='voucherx_balance'),
    path('voucherx/debit/', views.VoucherXDebitView.as_view(), name='voucherx_debit'),
    path('voucherx/tabs/', views.VoucherXTabbedView.as_view(), name='voucherx_tabs'),
    path('voucherx/brands/onboard/', views.BrandAdminOnboardingView.as_view(), name='voucherx_admin_onboard'),
    path('voucherx/wizard/issue/', views.VoucherXQuickIssueWizard.as_view(), name='voucherx_wizard_issue'),
    
    # Reseller/Partner UI removed — redirect to Project Management (ParkPe / Payswap)
    path('reseller/', RedirectView.as_view(url='/dashboard/projects/', permanent=False), name='reseller_dashboard'),
    path('reseller/<path:subpath>', RedirectView.as_view(url='/dashboard/projects/', permanent=False)),
    path('partners/', RedirectView.as_view(url='/dashboard/projects/', permanent=False), name='partner_dashboard'),
    path('partner/dashboard/', RedirectView.as_view(url='/dashboard/projects/', permanent=False), name='partner_console'),
    path('partner/<path:subpath>', RedirectView.as_view(url='/dashboard/projects/', permanent=False)),

    # ParkPe App Management – removed; redirect to dashboard
    path('parkpe/app-management/', RedirectView.as_view(url='/dashboard/', permanent=False), name='parkpe_app_management'),
    path('parkpe/connect/', RedirectView.as_view(url='/dashboard/', permanent=False), name='parkpe_connect_dashboard'),
    path('parkpe/app-management/service-config/add/', RedirectView.as_view(url='/dashboard/', permanent=False), name='parkpe_service_config_add'),
    path('parkpe/app-management/service-config/<int:pk>/edit/', RedirectView.as_view(url='/dashboard/', permanent=False), name='parkpe_service_config_edit'),
    path('parkpe/app-management/gateway-config/add/', RedirectView.as_view(url='/dashboard/', permanent=False), name='parkpe_gateway_config_add'),
    path('parkpe/app-management/gateway-config/<int:pk>/edit/', RedirectView.as_view(url='/dashboard/', permanent=False), name='parkpe_gateway_config_edit'),

    # API registry removed (internal apps – no external partners)
    path('dashboard/admin/api-registry/', RedirectView.as_view(url='/dashboard/projects/', permanent=False), name='api_product_list'),
    path('dashboard/admin/api-registry/<path:subpath>', RedirectView.as_view(url='/dashboard/projects/', permanent=False)),

    # Super Admin / Analytics – removed; redirect to dashboard
    path('dashboard/super-admin/', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('dashboard/super-admin/<path:subpath>', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('super-admin/', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('super-admin/<path:subpath>', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('analytics/', RedirectView.as_view(url='/dashboard/', permanent=False), name='analytics_dashboard'),
]
