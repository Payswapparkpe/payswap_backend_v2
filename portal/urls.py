"""
Portal URL Configuration
No "portal" prefix in URLs
"""
from django.urls import path
from portal import views

urlpatterns = [
    # Landing and Auth
    path('', views.LandingPageView.as_view(), name='landing'),
    path('signin/', views.SignInView.as_view(), name='signin'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('logout/', views.sign_out_view, name='logout'),
    
    # Password Management
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('password/reset/<uidb64>/<token>/', views.PasswordResetView.as_view(), name='password_reset'),
    path('password/change/', views.PasswordChangeView.as_view(), name='password_change'),
    
    # MFA
    path('mfa/setup/', views.MFASetupView.as_view(), name='mfa_setup'),
    path('mfa/verify/', views.MFAVerifyView.as_view(), name='mfa_verify'),
    path('mfa/resend-otp/', views.resend_otp_view, name='resend_otp'),
    
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/admin/', views.AdminDashboardView.as_view(), name='dashboard_admin'),
    path('dashboard/employee/', views.EmployeeDashboardView.as_view(), name='dashboard_employee'),
    path('dashboard/super/', views.SuperDashboardView.as_view(), name='dashboard_super'),
    path('dashboard/distributor/', views.DistributorDashboardView.as_view(), name='dashboard_distributor'),
    path('dashboard/retailer/', views.RetailerDashboardView.as_view(), name='dashboard_retailer'),
    path('dashboard/customer/', views.CustomerDashboardView.as_view(), name='dashboard_customer'),
    path('dashboard/vendor/', views.VendorDashboardView.as_view(), name='dashboard_vendor'),
    
    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/create/', views.ProfileCreateView.as_view(), name='profile_create'),
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    
    # Settings
    path('settings/', views.SettingsView.as_view(), name='settings'),
    
    # Users
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:user_id>/', views.UserDetailView.as_view(), name='user_detail'),
    
    # KYC
    path('kyc/submit/', views.KYCSubmitView.as_view(), name='kyc_submit'),
    
    # Wallet
    path('wallet/', views.WalletView.as_view(), name='wallet'),
    path('wallet/transactions/', views.WalletTransactionView.as_view(), name='wallet_transactions'),
    
    # Permissions
    path('permissions/', views.PermissionManageView.as_view(), name='permissions'),
    path('permissions/assign/', views.assign_permission_view, name='permission_assign'),
    path('permissions/revoke/', views.revoke_permission_view, name='permission_revoke'),
    path('roles/change/', views.change_role_view, name='role_change'),
]
