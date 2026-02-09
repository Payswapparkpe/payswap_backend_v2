import { Routes } from '@angular/router';

/**
 * Connect service routes – ParkPe Connect (Secure Vehicle Communication).
 * /connect = Hub (logged-in: manage vehicles, QR, scan). /connect/info = product description.
 * Public scan result is at top-level /connect/scan/:qrCode.
 */
export const CONNECT_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./connect-hub/connect-hub.component').then(
        (m) => m.ConnectHubComponent
      ),
  },
  {
    path: 'info',
    loadComponent: () =>
      import('./connect-landing/connect-landing.component').then(
        (m) => m.ConnectLandingComponent
      ),
  },
  {
    path: 'scan',
    loadComponent: () =>
      import('./connect-scan/connect-scan.component').then(
        (m) => m.ConnectScanComponent
      ),
  },
  {
    path: 'vehicles',
    children: [
      {
        path: '',
        loadComponent: () =>
          import('./connect-vehicles-list/connect-vehicles-list.component').then(
            (m) => m.ConnectVehiclesListComponent
          ),
      },
      {
        path: 'add',
        loadComponent: () =>
          import('./connect-vehicle-form/connect-vehicle-form.component').then(
            (m) => m.ConnectVehicleFormComponent
          ),
      },
      {
        path: ':id/edit',
        loadComponent: () =>
          import('./connect-vehicle-form/connect-vehicle-form.component').then(
            (m) => m.ConnectVehicleFormComponent
          ),
      },
      {
        path: ':id',
        loadComponent: () =>
          import('./connect-vehicle-detail/connect-vehicle-detail.component').then(
            (m) => m.ConnectVehicleDetailComponent
          ),
      },
    ],
  },
  {
    path: 'app',
    loadComponent: () =>
      import('./connect-app-embed/connect-app-embed.component').then(
        (m) => m.ConnectAppEmbedComponent
      ),
  },
];
