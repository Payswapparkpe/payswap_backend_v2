import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { App } from './app/app';
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

initSentry()
  .then(() => bootstrapApplication(App, appConfig))
  .catch((err) => console.error(err));
