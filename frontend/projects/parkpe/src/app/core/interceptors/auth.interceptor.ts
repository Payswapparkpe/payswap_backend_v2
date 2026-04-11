import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';
import { environment } from '../../../environments/environment';

/**
 * Auth Interceptor
 * - Adds X-API-Key for Engine business APIs (partner identity; required for connect/bbps/payment/voucher).
 * - Adds Authorization: Bearer <JWT> for user identity (optional; used by profile, etc.).
 * Only attaches to trusted API origins (SEC-005: avoid token leakage).
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const token = authService.getToken();

  const url = req.url;
  const isRelativeApi = url.startsWith('/api/');
  const apiBase = environment.apiUrl ?? '/api';
  const isTrustedAbsoluteApi =
    typeof url === 'string' && url.startsWith(apiBase);
  if (!isRelativeApi && !isTrustedAbsoluteApi) {
    return next(req);
  }

  const isAuthPublic =
    url.includes('/auth/login') ||
    url.includes('/auth/register') ||
    url.includes('/auth/forgot-password') ||
    url.includes('/auth/otp/') ||
    url.includes('token/refresh') ||
    url.includes('assets/');

  const headers: Record<string, string> = {};
  if (environment.apiKey) {
    headers['X-API-Key'] = environment.apiKey;
  }
  if (!isAuthPublic && token) {
    authService.resetInactivityTimer();
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (Object.keys(headers).length) {
    return next(req.clone({ setHeaders: headers }));
  }
  return next(req);
};
