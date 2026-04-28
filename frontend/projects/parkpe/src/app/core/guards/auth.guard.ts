import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { AuthService } from '../services/auth.service';

/**
 * Auth Guard
 * Protects routes that require authentication
 */
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }

  const isFleetRoute = state.url.startsWith('/fleet');
  const isParkingOwnerRoute =
    state.url.startsWith('/parking/dashboard') ||
    state.url.startsWith('/parking/locations') ||
    state.url.startsWith('/parking/sessions') ||
    state.url.startsWith('/parking/bookings');
  const loginRoute = isFleetRoute ? '/fleet/login' : isParkingOwnerRoute ? '/parking/login' : '/auth/login';
  // Redirect to login with return URL
  router.navigate([loginRoute], {
    queryParams: { returnUrl: state.url },
  });
  return false;
};
