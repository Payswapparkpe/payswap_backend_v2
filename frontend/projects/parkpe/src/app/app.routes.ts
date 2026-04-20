import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { fleetAuthGuard } from './core/guards/fleet-auth.guard';
import { guestGuard } from './core/guards/guest.guard';
import { homeEntryGuard } from './core/guards/root-redirect.guard';
import { sessionLockGuard } from './core/guards/session-lock.guard';
import { AppLayoutComponent } from './layouts/app-layout/app-layout.component';

/**
 * Application Routes
 * Implements lazy loading for all features
 */
export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'home',
  },
  {
    path: 'home',
    canActivate: [homeEntryGuard],
    loadComponent: () =>
      import('./features/home/home.component').then((m) => m.HomeComponent),
  },
  // Public scan result – no auth, no app layout (anyone who scans QR lands here)
  {
    path: 'connect/scan/:qrCode',
    loadComponent: () =>
      import('./features/connect/connect-scan-result/connect-scan-result.component').then(
        (m) => m.ConnectScanResultComponent
      ),
  },
  {
    path: 'auth',
    canActivate: [guestGuard],
    children: [
      {
        path: 'login',
        loadComponent: () =>
          import('./features/auth/login/login.component').then(
            (m) => m.LoginComponent
          ),
      },
      {
        path: 'register',
        loadComponent: () =>
          import('./features/auth/register/register.component').then(
            (m) => m.RegisterComponent
          ),
      },
      {
        path: 'forgot-password',
        loadComponent: () =>
          import('./features/auth/forgot-password/forgot-password.component').then(
            (m) => m.ForgotPasswordComponent
          ),
      },
    ],
  },
  {
    path: 'fleet/login',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/login/login.component').then(
        (m) => m.LoginComponent
      ),
  },
  {
    path: 'unlock',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/security/session-lock/session-lock.component').then(
        (m) => m.SessionLockComponent
      ),
  },
  {
    path: '',
    component: AppLayoutComponent,
    canActivate: [authGuard],
    canActivateChild: [sessionLockGuard],
    children: [
      {
        path: 'fleet/interest',
        loadComponent: () =>
          import('./features/fleet/fleet-interest.component').then((m) => m.FleetInterestComponent),
      },
      {
        path: 'fleet/control-center',
        canActivate: [fleetAuthGuard],
        loadComponent: () =>
          import('./features/fleet/fleet-control-center.component').then(
            (m) => m.FleetControlCenterComponent
          ),
      },
      {
        path: 'fleet/vehicles',
        canActivate: [fleetAuthGuard],
        loadComponent: () =>
          import('./features/fleet/fleet-vehicles.component').then(
            (m) => m.FleetVehiclesComponent
          ),
      },
      {
        path: 'fleet/drivers',
        canActivate: [fleetAuthGuard],
        loadComponent: () =>
          import('./features/fleet/fleet-drivers.component').then(
            (m) => m.FleetDriversComponent
          ),
      },
      {
        path: 'fleet/trips',
        canActivate: [fleetAuthGuard],
        loadComponent: () =>
          import('./features/fleet/fleet-trips.component').then(
            (m) => m.FleetTripsComponent
          ),
      },
      {
        path: 'fleet/compliance',
        canActivate: [fleetAuthGuard],
        loadComponent: () =>
          import('./features/fleet/fleet-compliance.component').then(
            (m) => m.FleetComplianceComponent
          ),
      },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then(
            (m) => m.DashboardComponent
          ),
      },
      {
        path: 'connect',
        data: { preload: { enabled: true, priority: 1 } },
        loadChildren: () =>
          import('./features/connect/connect.routes').then((m) => m.CONNECT_ROUTES),
      },
      {
        path: 'parking',
        data: { preload: { enabled: true, priority: 1 } },
        loadChildren: () =>
          import('./features/parking/parking.routes').then((m) => m.PARKING_ROUTES),
      },
      {
        path: 'bbps',
        data: { preload: { enabled: true, priority: 2 } },
        loadChildren: () =>
          import('./features/bbps/bbps.routes').then((m) => m.BBPS_ROUTES),
      },
      {
        path: 'fastag',
        data: { preload: { enabled: true, priority: 2 } },
        loadChildren: () =>
          import('./features/fastag/fastag.routes').then((m) => m.FASTAG_ROUTES),
      },
      {
        path: 'challan',
        data: { preload: { enabled: true, priority: 2 } },
        loadChildren: () =>
          import('./features/challan/challan.routes').then((m) => m.CHALLAN_ROUTES),
      },
      {
        path: 'payment',
        data: { preload: { enabled: true, priority: 1 } },
        loadChildren: () =>
          import('./features/payment/payment.routes').then((m) => m.PAYMENT_ROUTES),
      },
      {
        path: 'vouchers',
        data: { preload: { enabled: true, priority: 1 } },
        loadChildren: () =>
          import('./features/voucher/voucher.routes').then((m) => m.VOUCHER_ROUTES),
      },
      {
        path: 'profile',
        data: { preload: { enabled: true, priority: 3 } },
        loadChildren: () =>
          import('./features/profile/profile.routes').then((m) => m.PROFILE_ROUTES),
      },
      {
        path: 'settings',
        loadComponent: () =>
          import('./features/settings/settings.component').then(
            (m) => m.SettingsComponent
          ),
      },
      {
        path: 'notifications',
        loadComponent: () =>
          import('./features/notifications/notification-inbox.component').then(
            (m) => m.NotificationInboxComponent
          ),
      },
    ],
  },
  {
    path: '**',
    redirectTo: '/home',
  },
];
