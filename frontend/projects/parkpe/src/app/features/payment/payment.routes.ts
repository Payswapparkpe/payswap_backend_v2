import { Routes } from '@angular/router';

export const PAYMENT_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'history',
  },
  {
    path: 'buy-voucher',
    redirectTo: '/vouchers',
    pathMatch: 'full',
  },
  {
    path: 'checkout',
    loadComponent: () =>
      import('./payment-page/payment-page.component').then(
        (m) => m.PaymentPageComponent
      ),
  },
  {
    path: 'status',
    loadComponent: () =>
      import('./payment-status/payment-status.component').then(
        (m) => m.PaymentStatusComponent
      ),
  },
  {
    path: 'callback/:gateway',
    loadComponent: () =>
      import('./payment-callback/payment-callback.component').then(
        (m) => m.PaymentCallbackComponent
      ),
  },
  {
    path: 'receipt/:transactionId',
    loadComponent: () =>
      import('./payment-receipt/payment-receipt.component').then(
        (m) => m.PaymentReceiptComponent
      ),
  },
  {
    path: 'invoice/:transactionId',
    loadComponent: () =>
      import('./payment-receipt/payment-receipt.component').then(
        (m) => m.PaymentReceiptComponent
      ),
  },
  {
    path: 'history',
    loadComponent: () =>
      import('./payment-history-shell/payment-history-shell.component').then(
        (m) => m.PaymentHistoryShellComponent
      ),
    children: [
      {
        path: 'receipt/:transactionId',
        loadComponent: () =>
          import('./payment-receipt/payment-receipt.component').then(
            (m) => m.PaymentReceiptComponent
          ),
      },
    ],
  },
  {
    path: 'reports',
    loadComponent: () =>
      import('./reports-shell/reports-shell.component').then(
        (m) => m.ReportsShellComponent
      ),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'payments' },
      {
        path: 'payments',
        loadComponent: () =>
          import('./reports/payment-report/payment-report.component').then(
            (m) => m.PaymentReportComponent
          ),
      },
      {
        path: 'voucher-statement',
        loadComponent: () =>
          import('./reports/voucher-statement/voucher-statement.component').then(
            (m) => m.VoucherStatementComponent
          ),
      },
    ],
  },
];
