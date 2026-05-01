import { ApplicationConfig, APP_INITIALIZER, inject } from '@angular/core';
import { provideRouter, withPreloading } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideCharts, withDefaultRegisterables } from 'ng2-charts';

import { routes } from './app.routes';
import { environment } from '../environments/environment';
import { API_BACKEND_TOKEN } from './core/constants';
import { MockApiService } from './core/api/mock-api.service';
import { RealApiService } from './core/api/real-api.service';
import { AuthService } from './core/services/auth.service';
import { SessionLockService } from './core/services/session-lock.service';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { ngrokDevInterceptor } from './core/interceptors/ngrok-dev.interceptor';
import { apiBaseInterceptor } from './core/interceptors/api-base.interceptor';
import { loggingInterceptor } from './core/interceptors/logging.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';
import { firstValueFrom, of } from 'rxjs';
import { catchError, timeout } from 'rxjs/operators';
import { PriorityPreloadingStrategy } from './core/routing/priority-preloading.strategy';

/**
 * Application Configuration
 * Sets up all providers, interceptors, and API backend.
 * PWA: manifest is linked in index.html; ngsw-config.json is ready.
 * To enable the service worker run: ng add @angular/pwa
 */
/** On app load/reload: refresh access token if we have refresh token so user stays logged in. */
function initAuthRefresh(): () => Promise<void> {
  const auth = inject(AuthService);
  return () =>
    firstValueFrom(
      auth.refreshTokenIfStored().pipe(
        timeout(15000),
        catchError(() => of(false)),
      ),
    ).then(() => undefined);
}

function initSessionLock(): () => void {
  const lock = inject(SessionLockService);
  return () => lock.startMonitoring();
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideAnimationsAsync(),
    provideRouter(routes, withPreloading(PriorityPreloadingStrategy)),
    provideHttpClient(
      withInterceptors([
        ngrokDevInterceptor,
        apiBaseInterceptor,
        authInterceptor,
        loggingInterceptor,
        errorInterceptor,
      ])
    ),
    provideCharts(withDefaultRegisterables()),
    {
      provide: API_BACKEND_TOKEN,
      useClass: environment.useMockApi ? MockApiService : RealApiService,
    },
    { provide: APP_INITIALIZER, useFactory: initAuthRefresh, multi: true },
    { provide: APP_INITIALIZER, useFactory: initSessionLock, multi: true },
  ],
};
