import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const parkingOwnerGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  auth.activatePortal('parking');
  if (!auth.isAuthenticated()) return router.createUrlTree(['/auth/parking']);
  if (!auth.isParkingUser()) return router.createUrlTree(['/auth/parking']);
  return true;
};

