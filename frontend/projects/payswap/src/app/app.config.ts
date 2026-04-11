import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideCharts, withDefaultRegisterables } from 'ng2-charts';

import { routes } from './app.routes';
import { environment } from '../environments/environment';
import { API_BACKEND_TOKEN } from './core/constants';
import { MockApiService } from './core/api/mock-api.service';
import { RealApiService } from './core/api/real-api.service';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { apiBaseInterceptor } from './core/interceptors/api-base.interceptor';
import { loggingInterceptor } from './core/interceptors/logging.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(
      withInterceptors([apiBaseInterceptor, authInterceptor, loggingInterceptor, errorInterceptor])
    ),
    provideCharts(withDefaultRegisterables()),
    {
      provide: API_BACKEND_TOKEN,
      useClass: environment.useMockApi ? MockApiService : RealApiService,
    },
  ],
};
