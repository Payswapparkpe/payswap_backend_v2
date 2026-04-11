import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { NotificationService } from '../services/notification.service';
import { LoggerService } from '../services/logger.service';

/**
 * Error Interceptor
 * Handles HTTP errors globally and logs every failure via LoggerService.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const authService = inject(AuthService);
  const notification = inject(NotificationService);
  const logger = inject(LoggerService);

  return next(req).pipe(
    catchError((error) => {
      logger.error('HTTP request failed', {
        service: 'http',
        url: req.url,
        method: req.method,
        status: error?.status ?? 0,
        message: error?.error?.detail ?? error?.error?.message ?? error?.message ?? 'Unknown error',
      });
      let errorMessage = 'An error occurred';
      const isAuthRequest =
        req.url.includes('/auth/login') ||
        req.url.includes('/auth/register') ||
        req.url.includes('/auth/otp/');

      if (error.status === 401) {
        if (isAuthRequest) {
          // Login/register failed – show backend message, do not redirect
          errorMessage = error.error?.detail || error.error?.message || 'Invalid email or password.';
        } else {
          authService.clearSession();
          router.navigate(['/auth/login']);
          errorMessage = 'Session expired. Please login again.';
        }
      } else if (error.status === 403) {
        errorMessage = 'Access denied. You do not have permission.';
      } else if (error.status === 404) {
        errorMessage = 'Resource not found.';
      } else if (error.status >= 500) {
        errorMessage = 'Server error. Please try again later.';
      } else if (error.status === 0) {
        errorMessage = 'Network error. Please check your connection.';
      } else if (error.error?.detail) {
        errorMessage = error.error.detail;
      } else if (error.error?.message) {
        errorMessage = error.error.message;
      }

      // Let login/register components show their own message to avoid duplicate toasts
      if (!isAuthRequest) {
        notification.showError(errorMessage);
      }

      return throwError(() => error);
    })
  );
};
