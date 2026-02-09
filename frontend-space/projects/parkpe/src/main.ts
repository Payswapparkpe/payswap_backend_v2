import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

/**
 * Bootstrap the PARKPE application
 */
bootstrapApplication(AppComponent, appConfig).catch((err) =>
  console.error('Application bootstrap failed:', err)
);
