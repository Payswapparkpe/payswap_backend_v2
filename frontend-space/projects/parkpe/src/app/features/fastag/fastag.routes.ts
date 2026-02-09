import { Routes } from '@angular/router';

export const FASTAG_ROUTES: Routes = [
  {
    path: '',
    redirectTo: 'recharge',
    pathMatch: 'full',
  },
  {
    path: 'recharge',
    loadComponent: () =>
      import('./fastag-form/fastag-form.component').then(
        (m) => m.FastagFormComponent
      ),
  },
  {
    path: 'confirm',
    loadComponent: () =>
      import('./fastag-confirm/fastag-confirm.component').then(
        (m) => m.FastagConfirmComponent
      ),
  },
];
