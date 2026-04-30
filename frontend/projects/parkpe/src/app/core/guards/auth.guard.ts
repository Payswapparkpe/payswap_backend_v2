import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { AuthService } from '../services/auth.service';

function decodeMaybe(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function inferLoginRoute(url: string): string {
  const lowerUrl = (url || '').toLowerCase();
  const isFleetRoute = lowerUrl.startsWith('/fleet');
  if (isFleetRoute) return '/fleet/login';

  // Parking context can arrive via direct parking routes OR nested returnUrl chains
  // like /unlock?reason=idle&returnUrl=%2Fauth%2Flogin%3FreturnUrl%3D%252Fparking%252Flogin
  const maybeParking =
    lowerUrl.includes('/parking/') ||
    lowerUrl.includes('/parking%2f') ||
    decodeMaybe(lowerUrl).includes('/parking/');
  if (maybeParking) return '/auth/parking';

  // Try to parse returnUrl recursively if present
  const qIndex = url.indexOf('?');
  if (qIndex >= 0) {
    const query = new URLSearchParams(url.slice(qIndex + 1));
    const returnUrl = query.get('returnUrl');
    if (returnUrl) {
      const decoded = decodeMaybe(returnUrl);
      return inferLoginRoute(decoded);
    }
  }
  return '/auth/login';
}

/**
 * Auth Guard
 * Protects routes that require authentication
 */
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const url = state.url || '';
  if (url.startsWith('/fleet')) {
    authService.activatePortal('fleet');
  } else if (url.startsWith('/hub')) {
    authService.activatePortal('parking');
  } else {
    authService.activatePortal('consumer');
  }

  if (authService.isAuthenticated()) {
    return true;
  }

  const loginRoute = inferLoginRoute(state.url || '');
  // Redirect to login with return URL
  router.navigate([loginRoute], {
    queryParams: { returnUrl: state.url },
  });
  return false;
};
