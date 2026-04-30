import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError, switchMap } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { NotificationService } from '../services/notification.service';
import { LoggerService } from '../services/logger.service';

/**
 * Error Interceptor
 * Handles HTTP errors globally. On 401, tries to refresh token once and retry so active users stay logged in.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const authService = inject(AuthService);
  const notification = inject(NotificationService);
  const logger = inject(LoggerService);

  /** Where to send user after session cleared — per portal.
   *  Checks router URL first (most reliable at call time), then stored portal key as fallback. */
  const loginRouteAfter401 = (reqUrl: string, routerUrl: string) => {
    if (
      routerUrl.startsWith('/hub') ||
      routerUrl.includes('/auth/parking') ||
      reqUrl.includes('auth/parking')
    ) return '/auth/parking';
    if (
      routerUrl.startsWith('/fleet') ||
      reqUrl.includes('/auth/fleet') ||
      reqUrl.includes('dashboard/fleet')
    ) return '/fleet/login';
    // Fallback: use stored portal key (survives clearSession so it's valid even after token removal)
    const storedPortal = authService.getAuthPortal();
    if (storedPortal === 'parking') return '/auth/parking';
    if (storedPortal === 'fleet') return '/fleet/login';
    return '/auth/login';
  };
  return next(req).pipe(
    catchError((error) => {
      const isAuthRequest =
        req.url.includes('/auth/login') ||
        req.url.includes('/auth/register') ||
        req.url.includes('/auth/otp/') ||
        req.url.includes('/auth/parking/login');
      const isRefreshRequest = req.url.includes('token/refresh');
      const alreadyRetried = req.headers.has('X-ParkPe-Retried');
      const willRetryWithRefresh =
        error?.status === 401 && !isAuthRequest && !isRefreshRequest && !alreadyRetried && !!authService.getRefreshToken();

      const isConnectChatPollThrottle =
        error?.status === 429 &&
        req.method === 'GET' &&
        typeof req.url === 'string' &&
        req.url.includes('/connect/chat/threads/') &&
        req.url.includes('/messages/');

      // Don't log 401 as error when we're about to retry with refresh (token expired is normal)
      if (!willRetryWithRefresh && !isConnectChatPollThrottle) {
        logger.error('HTTP request failed', {
          service: 'http',
          url: req.url,
          method: req.method,
          status: error?.status ?? 0,
          message: error?.error?.detail ?? error?.error?.message ?? error?.message ?? 'Unknown error',
        });
      }

      let errorMessage = 'An error occurred';

      if (error.status === 401) {
        if (isAuthRequest) {
          // Login/register failed – show backend message, do not redirect
          errorMessage = error.error?.detail || error.error?.message || 'Invalid email or password.';
        } else if (!isRefreshRequest && !alreadyRetried && authService.getRefreshToken()) {
          // Try refresh once and retry so active users don't get logged out (5 min access token; refresh extends session)
          return authService.refreshToken().pipe(
            switchMap((newToken) => {
              if (newToken) {
                const cloned = req.clone({
                  setHeaders: { Authorization: `Bearer ${newToken}`, 'X-ParkPe-Retried': '1' },
                });
                return next(cloned);
              }
              authService.clearSession();
              router.navigate([loginRouteAfter401(req.url, router.url)]);
              notification.showError('Session expired. Please login again.');
              return throwError(() => error);
            }),
            catchError(() => {
              authService.clearSession();
              router.navigate([loginRouteAfter401(req.url, router.url)]);
              notification.showError('Session expired. Please login again.');
              return throwError(() => error);
            })
          );
        } else {
          authService.clearSession();
          router.navigate([loginRouteAfter401(req.url, router.url)]);
          errorMessage = 'Session expired. Please login again.';
        }
      } else if (
        error.status === 403 &&
        typeof req.url === 'string' &&
        (req.url.includes('/api/') || req.url.startsWith('api/'))
      ) {
        errorMessage = 'Access denied. You do not have permission for this action.';
        const portal = authService.inferPortalFromUrls(req.url, router.url);
        authService.clearSessionForPortal(portal);
        router.navigate([authService.getLoginPathForPortal(portal)]);
      } else if (error.status === 404) {
        errorMessage = 'Resource not found.';
      } else if (error.status >= 500) {
        errorMessage =
          (typeof error.error?.detail === 'string' && error.error.detail) ||
          error.error?.message ||
          'Server error. Please try again later.';
      } else if (error.status === 0) {
        errorMessage = 'Network error. Please check your connection.';
      } else if (error.error?.detail) {
        errorMessage = error.error.detail;
      } else if (error.error?.message) {
        errorMessage = error.error.message;
      }

      // Let login/register components show their own message to avoid duplicate toasts
      // RC paywall: vehicle detail shows inline copy for fetch-rc payment required (402)
      const skipToastForHandledRcPaywall =
        error.status === 402 &&
        typeof req.url === 'string' &&
        req.url.includes('/connect/vehicles/') &&
        req.url.includes('/fetch-rc/');
      // Chat message polling uses a separate throttle bucket; transient 429 should not spam global error toasts.
      const skipToastForConnectChatPollThrottle =
        error.status === 429 &&
        req.method === 'GET' &&
        typeof req.url === 'string' &&
        req.url.includes('/connect/chat/threads/') &&
        req.url.includes('/messages/');
      // Chat send shows inline toast in ConnectChatService (avoid duplicate global toasts)
      const skipToastForConnectChatMessageSend =
        req.method === 'POST' &&
        typeof req.url === 'string' &&
        req.url.includes('/connect/chat/threads/') &&
        req.url.includes('/messages/');
      const skipToastFor403Redirect = error.status === 403;
      if (
        !isAuthRequest &&
        !skipToastForHandledRcPaywall &&
        !skipToastForConnectChatPollThrottle &&
        !skipToastForConnectChatMessageSend &&
        !skipToastFor403Redirect
      ) {
        notification.showError(errorMessage);
      }

      return throwError(() => error);
    })
  );
};
