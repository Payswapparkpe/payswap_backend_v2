import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';

import { routes } from './app.routes';
import { environment } from '../environments/environment';
import { API_BACKEND_TOKEN } from './core/constants';
import { MockApiService } from './core/api/mock-api.service';
import { RealApiService } from './core/api/real-api.service';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { apiBaseInterceptor } from './core/interceptors/api-base.interceptor';
import { loggingInterceptor } from './core/interceptors/logging.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';

/**
 * Application Configuration
 * Sets up all providers, interceptors, and API backend.
 * PWA: manifest is linked in index.html; ngsw-config.json is ready.
 * To enable the service worker run: ng add @angular/pwa
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(
      withInterceptors([apiBaseInterceptor, authInterceptor, loggingInterceptor, errorInterceptor])
    ),
    {
      provide: API_BACKEND_TOKEN,
      useClass: environment.useMockApi ? MockApiService : RealApiService,
    },
  ],
};
