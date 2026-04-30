import { Routes } from '@angular/router';

export const CHALLAN_ROUTES: Routes = [
  {
    path: 'search',
    redirectTo: '',
    pathMatch: 'full',
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
  {
    path: 'pay/:id/methods',
    loadComponent: () =>
      import('./challan-payment-methods/challan-payment-methods.component').then(
        (m) => m.ChallanPaymentMethodsComponent
      ),
  },
  {
    path: 'pay/:id/processing',
    loadComponent: () =>
      import('./challan-processing/challan-processing.component').then(
        (m) => m.ChallanProcessingComponent
      ),
  },
  {
    path: 'pay/:id/success',
    loadComponent: () =>
      import('./challan-success/challan-success.component').then(
        (m) => m.ChallanSuccessComponent
      ),
  },
  {
    path: 'pay/:id/failed',
    loadComponent: () =>
      import('./challan-failed/challan-failed.component').then(
        (m) => m.ChallanFailedComponent
      ),
  },
  {
    path: 'receipt/:id',
    loadComponent: () =>
      import('./challan-receipt/challan-receipt.component').then(
        (m) => m.ChallanReceiptComponent
      ),
  },
  {
    path: 'history',
    loadComponent: () =>
      import('./challan-history/challan-history.component').then(
        (m) => m.ChallanHistoryComponent
      ),
  },
  {
    path: 'vehicles',
    loadComponent: () =>
      import('./my-vehicles/my-vehicles.component').then(
        (m) => m.MyVehiclesComponent
      ),
  },
  {
    path: '',
    loadComponent: () =>
      import('./challan-shell/challan-shell.component').then(
        (m) => m.ChallanShellComponent
      ),
  },
];
