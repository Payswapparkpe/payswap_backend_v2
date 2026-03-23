import { inject } from '@angular/core';
import { CanActivateChildFn, Router } from '@angular/router';
import { SessionLockService } from '../services/session-lock.service';

export const sessionLockGuard: CanActivateChildFn = (_route, state) => {
  const lock = inject(SessionLockService);
  const router = inject(Router);
  const url = state.url || '';
  if (url.startsWith('/unlock')) return true;
  if (!lock.locked()) return true;
  router.navigate(['/unlock'], { queryParams: { returnUrl: url || '/dashboard' } });
  return false;
};
