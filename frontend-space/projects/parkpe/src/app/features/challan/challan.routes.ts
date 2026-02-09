import { Routes } from '@angular/router';

export const CHALLAN_ROUTES: Routes = [
  {
    path: '',
    redirectTo: 'search',
    pathMatch: 'full',
  },
  {
    path: 'search',
    loadComponent: () =>
      import('./challan-search/challan-search.component').then(
        (m) => m.ChallanSearchComponent
      ),
  },
  {
    path: 'list',
    loadComponent: () =>
      import('./challan-list/challan-list.component').then(
        (m) => m.ChallanListComponent
      ),
  },
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
];
