import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/**
 * `/home` — marketing shell for guests; authenticated users go to dashboard / fleet (same as post-login).
 * Used on the `home` route (after `/` redirects to `/home`).
 */
export const homeEntryGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isAuthenticated()) {
    return true;
  }
  return router.parseUrl(auth.getPostLoginRoute());
};
