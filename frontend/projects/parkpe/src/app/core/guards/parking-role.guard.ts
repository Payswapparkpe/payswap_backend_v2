import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

const hierarchy = {
  attendant: 1,
  manager: 2,
  owner: 3,
} as const;

export const parkingRoleGuard = (minRole: 'attendant' | 'manager' | 'owner'): CanActivateFn => {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    const role = auth.getParkingRole();
    if (!role) return router.createUrlTree(['/hub/parking/dashboard']);
    if (hierarchy[role] >= hierarchy[minRole]) return true;
    return router.createUrlTree(['/hub/parking/dashboard']);
  };
};

