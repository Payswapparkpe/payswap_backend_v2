import { Routes } from '@angular/router';

export const CHALLAN_ROUTES: Routes = [
  {
    path: 'search',
    redirectTo: '',
    pathMatch: 'full',
  },
  {
    path: 'list',
    redirectTo: '',
    pathMatch: 'full',
  },
  {
    path: '',
    loadComponent: () =>
      import('./challan-shell/challan-shell.component').then(
        (m) => m.ChallanShellComponent
      ),
    children: [
      {
        path: 'detail/:id',
        loadComponent: () =>
          import('./challan-detail/challan-detail.component').then(
            (m) => m.ChallanDetailComponent
          ),
      },
      {
        path: 'pay/:id',
        loadComponent: () =>
          import('./challan-pay/challan-pay.component').then(
            (m) => m.ChallanPayComponent
          ),
      },
    ],
  },
];
