import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ToastContainerComponent } from './ui/toast/toast-container.component';
import { AuthService } from './core/services/auth.service';

/** Throttle activity events so we don't reset timer every few ms (e.g. mousemove). */
const ACTIVITY_THROTTLE_MS = 1000;

/**
 * Root Application Component
 * Starts inactivity timer when user is logged in; resets on click/key/mouse.
 */
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, ToastContainerComponent],
  template: `
    <router-outlet />
    <app-toast-container />
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
      width: 100%;
    }
  `],
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'PARKPE';
  private auth = inject(AuthService);
  private lastActivityAt = 0;
  private activityListener = (): void => this.onUserActivity();

  ngOnInit(): void {
    if (this.auth.isAuthenticated()) {
      this.auth.startInactivityTimer();
    }
    window.document.addEventListener('click', this.activityListener);
    window.document.addEventListener('keydown', this.activityListener);
    window.document.addEventListener('mousemove', this.activityListener);
  }

  ngOnDestroy(): void {
    window.document.removeEventListener('click', this.activityListener);
    window.document.removeEventListener('keydown', this.activityListener);
    window.document.removeEventListener('mousemove', this.activityListener);
  }

  private onUserActivity(): void {
    const now = Date.now();
    if (now - this.lastActivityAt >= ACTIVITY_THROTTLE_MS) {
      this.lastActivityAt = now;
      this.auth.resetInactivityTimer();
    }
  }
}
