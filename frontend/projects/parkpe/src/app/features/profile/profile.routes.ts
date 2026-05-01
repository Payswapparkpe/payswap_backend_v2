import { Routes } from '@angular/router';

export const PROFILE_ROUTES: Routes = [
  {
    path: '',
    redirectTo: 'view',
    pathMatch: 'full',
  },
  {
    path: 'view',
    loadComponent: () =>
      import('./profile-view/profile-view.component').then(
        (m) => m.ProfileViewComponent
      ),
  },
  {
    path: 'edit',
    loadComponent: () =>
      import('./profile-edit/profile-edit.component').then(
        (m) => m.ProfileEditComponent
      ),
  },
  {
    path: 'vehicles',
    loadComponent: () =>
      import('./vehicles/vehicles.component').then((m) => m.VehiclesComponent),
  },
  {
    path: 'vehicles/:vehicleId/fastag',
    loadComponent: () =>
      import('./vehicles/fastag-link/fastag-link.component').then((m) => m.FastagLinkComponent),
  },
];
