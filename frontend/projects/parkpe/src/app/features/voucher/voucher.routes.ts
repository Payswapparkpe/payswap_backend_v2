import { Routes } from '@angular/router';

export const VOUCHER_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () =>
      import('./vouchers-page/vouchers-page.component').then(
        (m) => m.VouchersPageComponent
      ),
  },
  {
    path: 'list',
    loadComponent: () =>
      import('./voucher-list-detail/voucher-list-detail.component').then(
        (m) => m.VoucherListDetailComponent
      ),
  },
  {
    path: 'list/:id',
    loadComponent: () =>
      import('./voucher-list-detail/voucher-list-detail.component').then(
        (m) => m.VoucherListDetailComponent
      ),
  },
  {
    path: ':id',
    loadComponent: () =>
      import('./voucher-detail/voucher-detail.component').then(
        (m) => m.VoucherDetailComponent
      ),
  },
];
