import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ThemeService, Theme } from '../../core/services/theme.service';
import { AuthService } from '../../core/services/auth.service';
import { Router, RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="settings-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="settings-title">Settings</h1>

      <!-- Theme Section -->
      <section class="settings-section card">
        <h2 class="section-title">Appearance</h2>
        <div class="setting-item">
          <div class="setting-info">
            <h3>Theme</h3>
            <p>Choose your preferred theme</p>
          </div>
          <div class="theme-toggle">
            <button
              class="theme-btn"
              [class.active]="currentTheme() === 'light'"
              (click)="setTheme('light')"
            >
              <span class="material-icons">light_mode</span>
              <span>Light</span>
            </button>
            <button
              class="theme-btn"
              [class.active]="currentTheme() === 'dark'"
              (click)="setTheme('dark')"
            >
              <span class="material-icons">dark_mode</span>
              <span>Dark</span>
            </button>
          </div>
        </div>
      </section>

      <!-- Language Section -->
      <section class="settings-section card">
        <h2 class="section-title">Language</h2>
        <div class="setting-item">
          <div class="setting-info">
            <h3>App Language</h3>
            <p>Default: English</p>
          </div>
          <select class="language-select" [value]="selectedLanguage" (change)="changeLanguage($event)">
            @for (lang of supportedLanguages; track lang.code) {
              <option [value]="lang.code">{{ lang.label }}</option>
            }
          </select>
        </div>
      </section>

      <!-- Notifications Section -->
      <section class="settings-section card">
        <h2 class="section-title">Notifications</h2>
        <div class="setting-item">
          <div class="setting-info">
            <h3>Push Notifications</h3>
            <p>Receive notifications about transactions</p>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" [(ngModel)]="pushEnabled" (change)="togglePush()" />
            <span class="slider"></span>
          </label>
        </div>
        <div class="setting-item">
          <div class="setting-info">
            <h3>Email Notifications</h3>
            <p>Receive email updates</p>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" [(ngModel)]="emailEnabled" (change)="toggleEmail()" />
            <span class="slider"></span>
          </label>
        </div>
      </section>

      <!-- Account Section -->
      <section class="settings-section card">
        <h2 class="section-title">Account</h2>
        <div class="setting-item">
          <div class="setting-info">
            <h3>Signed in as</h3>
            <p>{{ user()?.email }}</p>
          </div>
        </div>
        <button class="btn btn-error" (click)="logout()">
          <span class="material-icons">logout</span>
          <span>Sign Out</span>
        </button>
      </section>

      <!-- App Info -->
      <section class="settings-section card">
        <h2 class="section-title">About</h2>
        <div class="setting-item">
          <div class="setting-info">
            <h3>Version</h3>
            <p>{{ appVersion }}</p>
          </div>
        </div>
        <div class="setting-item">
          <div class="setting-info">
            <h3>Mode</h3>
            <p>{{ useMockApi ? 'Development (Mock API)' : 'Production (Real API)' }}</p>
          </div>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .settings-container {
      min-height: 100vh;
      background: var(--background);
      padding: 2rem;
      max-width: 800px;
      margin: 0 auto;
    }

    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }

    .settings-title {
      font-size: 2rem;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 2rem;
    }

    .settings-section {
      margin-bottom: 1.5rem;
      padding: 1.5rem;
    }

    .section-title {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 1rem;
    }

    .setting-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 0;
      border-bottom: 1px solid var(--border-light);

      &:last-child {
        border-bottom: none;
      }
    }

    .setting-info {
      h3 {
        font-size: 1rem;
        font-weight: 500;
        color: var(--text-primary);
        margin-bottom: 0.25rem;
      }

      p {
        font-size: 0.875rem;
        color: var(--text-secondary);
      }
    }

    .theme-toggle {
      display: flex;
      gap: 0.5rem;
    }

    .theme-btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.25rem;
      padding: 0.75rem 1rem;
      border: 2px solid var(--border-light);
      border-radius: var(--radius-md);
      background: transparent;
      cursor: pointer;
      transition: all 0.2s ease;

      &.active {
        border-color: var(--primary-500);
        background: var(--primary-50);
        color: var(--primary-700);
      }

      &:hover {
        border-color: var(--primary-400);
      }

      .material-icons {
        font-size: 24px;
      }

      span:not(.material-icons) {
        font-size: 0.875rem;
      }
    }

    .language-select {
      padding: 0.5rem 1rem;
      border: 2px solid var(--border-light);
      border-radius: var(--radius-md);
      font-size: 1rem;
      cursor: pointer;
      background: white;

      &:focus {
        outline: none;
        border-color: var(--primary-500);
      }
    }

    .toggle-switch {
      position: relative;
      display: inline-block;
      width: 50px;
      height: 28px;

      input {
        opacity: 0;
        width: 0;
        height: 0;

        &:checked + .slider {
          background-color: var(--primary-500);

          &:before {
            transform: translateX(22px);
          }
        }
      }

      .slider {
        position: absolute;
        cursor: pointer;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: #ccc;
        transition: 0.4s;
        border-radius: 34px;

        &:before {
          position: absolute;
          content: "";
          height: 20px;
          width: 20px;
          left: 4px;
          bottom: 4px;
          background-color: white;
          transition: 0.4s;
          border-radius: 50%;
        }
      }
    }

    .btn-error {
      background-color: var(--error);
      color: white;
      display: flex;
      align-items: center;
      gap: 0.5rem;

      &:hover {
        background-color: #d32f2f;
      }
    }
  `],
})
export class SettingsComponent {
  private themeService = inject(ThemeService);
  private authService = inject(AuthService);
  private router = inject(Router);

  currentTheme = this.themeService.theme;
  user = this.authService.userSignal;
  
  selectedLanguage = environment.app.defaultLanguage;
  supportedLanguages = environment.app.supportedLanguages;
  appVersion = environment.appVersion;
  useMockApi = environment.useMockApi;
  
  pushEnabled = false;
  emailEnabled = true;

  setTheme(theme: Theme) {
    this.themeService.setTheme(theme);
  }

  changeLanguage(event: any) {
    this.selectedLanguage = event.target.value;
    // TODO: Implement language service
    console.log('Language changed to:', this.selectedLanguage);
  }

  togglePush() {
    // TODO: Implement push notification toggle
    console.log('Push notifications:', this.pushEnabled);
  }

  toggleEmail() {
    // TODO: Implement email notification toggle
    console.log('Email notifications:', this.emailEnabled);
  }

  logout() {
    if (confirm('Are you sure you want to sign out?')) {
      this.authService.logout();
    }
  }
}
