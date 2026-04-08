import { HttpInterceptorFn } from '@angular/common/http';
import { environment } from '../../../environments/environment';

/**
 * ngrok free: without this header, some requests can get the browser-warning HTML instead of JSON.
 * Only applies in dev when the app is opened via an ngrok hostname.
 */
export const ngrokDevInterceptor: HttpInterceptorFn = (req, next) => {
  if (environment.production || typeof window === 'undefined') {
    return next(req);
  }
  if (!window.location.hostname.includes('ngrok')) {
    return next(req);
  }
  return next(
    req.clone({
      setHeaders: { 'ngrok-skip-browser-warning': 'true' },
    }),
  );
};
