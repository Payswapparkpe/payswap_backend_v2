import { HttpInterceptorFn } from '@angular/common/http';
import { environment } from '../../../environments/environment';

/**
 * API Base Interceptor
 * Prepends API base URL to relative URLs. Paths starting with / are used as-is (for dev proxy).
 */
export const apiBaseInterceptor: HttpInterceptorFn = (req, next) => {
  // Skip if URL is absolute or points to assets
  if (req.url.startsWith('http://') || req.url.startsWith('https://') || req.url.startsWith('assets/')) {
    return next(req);
  }
  // Same-origin relative path (e.g. /api/auth/login when using dev proxy) – use as-is
  if (req.url.startsWith('/')) {
    return next(req);
  }

  // Prepend API URL to relative paths
  const apiReq = req.clone({
    url: `${environment.apiUrl}${req.url}`,
  });

  return next(apiReq);
};
