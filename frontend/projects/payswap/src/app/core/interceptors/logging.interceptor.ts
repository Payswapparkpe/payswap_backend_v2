import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap } from 'rxjs/operators';
import { LoggerService } from '../services/logger.service';

/**
 * HTTP Logging Interceptor
 * Logs API request start, response (status, duration), and errors. No request/response bodies.
 */
export const loggingInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.url.startsWith('assets/')) {
    return next(req);
  }
  const logger = inject(LoggerService);
  const started = Date.now();
  const method = req.method;
  const url = req.url;

  logger.info('API request', { service: 'http', method, url });

  return next(req).pipe(
    tap({
      next: (event) => {
        if (event.type === 4) {
          const status = event.status ?? 0;
          const durationMs = Date.now() - started;
          logger.info('API response', { service: 'http', method, url, status, durationMs });
        }
      },
      error: (err) => {
        const status = err?.status ?? err?.statusCode ?? 0;
        const durationMs = Date.now() - started;
        logger.error('API error', { service: 'http', method, url, status, durationMs, error: err?.message ?? String(err) });
      },
    })
  );
};
