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
];
