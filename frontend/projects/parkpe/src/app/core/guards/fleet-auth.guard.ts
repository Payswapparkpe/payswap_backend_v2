import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const fleetAuthGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);
  authService.activatePortal('fleet');
  if (!authService.isAuthenticated()) {
    router.navigate(['/fleet/login']);
    return false;
  }
  if (!authService.isFleetUser()) {
    router.navigate(['/fleet/interest'], { replaceUrl: true });
    return false;
  }
  return true;
};
