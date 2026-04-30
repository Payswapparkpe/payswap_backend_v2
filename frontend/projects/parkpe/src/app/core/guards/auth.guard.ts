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

/**
 * Determine the correct login page.
 *
 * Resolution order:
 * 1. Explicit portal routes in the URL (/hub, /fleet) — strongest signal
 * 2. URL contains a parking hint (/parking/)
 * 3. Ambiguous shared routes (/unlock, /settings, etc.) — fall back to stored portal key
 *    (we intentionally keep PARKPE_AUTH_PORTAL_KEY across clearSession so this survives logout/expiry)
 * 4. Recurse into ?returnUrl param
 * 5. Default → /auth/login (consumer)
 */
function resolveLoginRoute(url: string, authService: AuthService): string {
  const lowerUrl = (url || '').toLowerCase().split('?')[0];

  // Fleet routes — fleet login always
  if (lowerUrl.startsWith('/fleet')) return '/fleet/login';

  // Hub routes — parking login always
  if (lowerUrl.startsWith('/hub')) return '/auth/parking';

  // URL contains a parking-specific segment
  if (
    lowerUrl.includes('/parking/') ||
    lowerUrl.includes('/parking%2f') ||
    decodeMaybe(lowerUrl).includes('/parking/')
  ) return '/auth/parking';

  // Ambiguous shared routes (/unlock, /profile, /settings, /notifications) —
  // use the stored portal key which survives session clearing.
  const ambiguous = ['/unlock', '/profile', '/settings', '/notifications'];
  if (ambiguous.some((p) => lowerUrl.startsWith(p))) {
    const storedPortal = authService.getAuthPortal();
    if (storedPortal === 'parking') return '/auth/parking';
    if (storedPortal === 'fleet') return '/fleet/login';
  }

  // Recurse into ?returnUrl — the returnUrl often contains the original portal hint
  const qIndex = url.indexOf('?');
  if (qIndex >= 0) {
    const query = new URLSearchParams(url.slice(qIndex + 1));
    const returnUrl = query.get('returnUrl');
    if (returnUrl) {
      return resolveLoginRoute(decodeMaybe(returnUrl), authService);
    }
  }

  // Default — consumer login
  return '/auth/login';
}

/**
 * Auth Guard
 * Protects routes that require authentication. Activates the correct portal namespace
 * from the URL so the right token is loaded into memory before the route renders.
 */
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const url = state.url || '';

  // Activate the portal namespace matching the route — but for /unlock and other
  // shared routes, do NOT override the portal; let the stored key govern it.
  if (url.startsWith('/fleet')) {
    authService.activatePortal('fleet');
  } else if (url.startsWith('/hub')) {
    authService.activatePortal('parking');
  } else if (!url.startsWith('/unlock')) {
    // /unlock is portal-agnostic — preserve whatever portal is already active
    authService.activatePortal('consumer');
  }

  if (authService.isAuthenticated()) {
    return true;
  }

  const loginRoute = resolveLoginRoute(url, authService);
  router.navigate([loginRoute], { queryParams: { returnUrl: url } });
  return false;
};
