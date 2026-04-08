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
from portal.views.services_integrated import ServicesIntegratedView