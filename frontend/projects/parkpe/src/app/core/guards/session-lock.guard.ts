import { inject } from '@angular/core';
import { CanActivateChildFn, Router } from '@angular/router';
import { SessionLockService } from '../services/session-lock.service';
import { AuthService } from '../services/auth.service';

export const sessionLockGuard: CanActivateChildFn = (_route, state) => {
  const lock = inject(SessionLockService);
  const router = inject(Router);
  const auth = inject(AuthService);
  const url = state.url || '';
  if (url.startsWith('/unlock')) return true;
  if (!lock.locked()) return true;
  const fallback = auth.getPostLoginRoute();
  router.navigate(['/unlock'], { queryParams: { returnUrl: url || fallback } });
  return false;
};
