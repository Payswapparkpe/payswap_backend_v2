import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/**
 * Only sessions started via `/auth/parking` are kept out of the consumer `AppLayout`.
 * Dual customer+operator accounts signed in through `/auth/login` stay on `/dashboard` like normal customers.
 */
export const consumerGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.getAuthPortal() === 'parking') {
    return router.createUrlTree(['/hub/parking/dashboard']);
  }
  return true;
};

