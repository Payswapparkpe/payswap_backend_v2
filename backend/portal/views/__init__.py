"""
Portal views package.
Log management views in log_views; API Registry in api_registry.
Domain views in auth_views, dashboard_views, profile_views,
user_views, kyc_views, wallet_views, permission_views, ticket_views.
Everything else (auth, service, voucher, reseller, admin) still in legacy.
"""
from portal.views.legacy import *
from portal.views.log_views import (
    LogListView,
    LogExportView,
    LogDetailView,
    log_resolve_view,
    debug_voucher_logs,
)
# Override with split domain modules (so portal.urls and core.urls get these)
from portal.views.dashboard_views import (
    DashboardView,
    EmployeeDashboardView,
    SuperDashboardView,
    MobikwikBalanceApiView,
    VendorBalancesApiView,
    DistributorDashboardView,
    RetailerDashboardView,
    CustomerDashboardView,
    VendorDashboardView,
    ParkPeTransactionsReportView,
)
from portal.views.profile_views import (
    ProfileCreateView,
    ProfileView,
    ProfileUpdateView,
    SettingsView,
)
from portal.views.user_views import (
    UserListView,
    UserCreateView,
    UserEditView,
    UserDeleteView,
    UserDetailView,
)
from portal.views.kyc_views import KYCListView, KYCSubmitView
from portal.views.wallet_views import WalletView, WalletTransactionView
from portal.views.permission_views import (
    PermissionManageView,
    PermissionManageUserView,
    PermissionManageRoleView,
    assign_permission_view,
    revoke_permission_view,
    change_role_view,
)
from portal.views.ticket_views import TicketListView, TicketDetailView, TicketCreateView
from portal.views.hub_rbac_views import (
    HubRbacDashboardView,
    HubRoleOptionsView,
    DepartmentListView,
    DepartmentCreateView,
    DepartmentUpdateView,
    ProjectListView,
    ProjectCreateView,
    ProjectUpdateView,
    HubRoleListView,
    HubRoleCreateView,
    HubRoleUpdateView,
    UserHubAssignmentListView,
    UserHubAssignmentCreateView,
    UserHubAssignmentUpdateView,
)
from portal.views.project_management_views import ProjectManagementView, CreateProjectAPIKeyView
from portal.views.business_overview import BusinessOverviewView, HubPnlView
from portal.views.services_integrated import (
    ServicesIntegratedView,
    toggle_vendor_status_view,
    toggle_vendor_api_status_view,
)
from portal.views.notification_views import (
    NotificationCenterView,
    notification_banner_create_view,
    notification_banner_toggle_view,
    notification_banner_delete_view,
    notification_campaign_create_view,
    notification_campaign_toggle_view,
    notification_campaign_duplicate_view,
    notification_campaign_send_now_view,
    notification_campaign_audience_preview_view,
    notification_analytics_view,
)
from portal.views.connect_ops_views import (
    ConnectOpsCenterView,
    connect_moderation_action_view,
    connect_ops_analytics_view,
)
from portal.views.parkpe_hub_views import (
    ParkPeControlCenterView,
    ParkPeFleetAccessRequestsView,
    ParkPeSettingsGovernanceView,
    parkpe_settings_governance_analytics_view,
)
from portal.views.service_voucher_refund_views import ServiceVoucherRefundQueueView
from portal.views.accounting_views import (
    AccountingBillingDocumentDownloadView,
    AccountingBillingDocumentHtmlView,
    AccountingDashboardView,
    AccountingDocumentsView,
    AccountingReportsView,
    AccountingTaxProfileEditView,
    AccountingTaxProfilesView,
)