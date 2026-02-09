import { Routes } from '@angular/router';

/**
 * BBPS – single internal screen (PhonePe/GPay style).
 * All steps: Category → Operator → Consumer details → Bill → Pay on one screen.
 */
export const BBPS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./bbps-internal/bbps-internal.component').then(
        (m) => m.BBPSInternalComponent
      ),
  },
];
