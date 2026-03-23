import { Injectable, signal } from '@angular/core';

export type Theme = 'light' | 'dark';

/**
 * Theme Service
 * Manages light/dark theme switching
 */
@Injectable({
  providedIn: 'root',
})
export class ThemeService {
  private currentTheme = signal<Theme>('light');
  theme = this.currentTheme.asReadonly();

  constructor() {
    // App uses light theme only; ignore system preference
    this.setTheme('light');
  }

  setTheme(theme: Theme): void {
    // App is light-only; ignore dark
    const effective = theme === 'dark' ? 'light' : theme;
    this.currentTheme.set(effective);

    if (typeof document !== 'undefined') {
      document.documentElement.classList.remove('dark-theme');
    }
  }

  toggleTheme(): void {
    const newTheme = this.currentTheme() === 'light' ? 'dark' : 'light';
    this.setTheme(newTheme);
  }
}
