import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { environment } from './environments/environment';

async function initSentry(): Promise<void> {
  if (!environment.sentry?.dsn) return;
  const Sentry = await import('@sentry/angular');
  Sentry.init({
    dsn: environment.sentry.dsn,
    environment: environment.sentry.environment,
    tracesSampleRate: environment.sentry.tracesSampleRate ?? 0.1
  });
}

/**
 * Bootstrap the PARKPE application
 */
initSentry()
  .then(() => bootstrapApplication(AppComponent, appConfig))
  .catch((err) => console.error('Application bootstrap failed:', err));
