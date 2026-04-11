import { Routes } from '@angular/router';

/**
 * Connect service routes – ParkPe Connect (Secure Vehicle Communication).
 * /connect = Hub (logged-in: manage vehicles, QR, scan). /connect/info = product description.
 * Public scan result is at top-level /connect/scan/:qrCode.
 */
export const CONNECT_ROUTES: Routes = [
  {
    path: '',
    redirectTo: 'vehicles',
    pathMatch: 'full',
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
    path: 'chats',
    loadComponent: () =>
      import('./connect-chats-shell/connect-chats-shell.component').then(
        (m) => m.ConnectChatsShellComponent
      ),
    children: [
      {
        path: ':threadId',
        loadComponent: () =>
          import('./connect-thread-chat/connect-thread-chat.component').then(
            (m) => m.ConnectThreadChatComponent
          ),
      },
    ],
  },
  {
    path: 'vehicles',
    loadComponent: () =>
      import('./connect-vehicles-shell/connect-vehicles-shell.component').then(
        (m) => m.ConnectVehiclesShellComponent
      ),
    children: [
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
