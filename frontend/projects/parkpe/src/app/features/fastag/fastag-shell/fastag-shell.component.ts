import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-fastag-shell',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterOutlet],
  template: `
    <div class="fastag-shell">
      <div class="fastag-shell-head">
        <a routerLink="/dashboard" class="back-link">
          <span class="material-icons">arrow_back</span> Back to Dashboard
        </a>
        <h1 class="page-title">FASTag</h1>
      </div>

      <div class="service-panel">
        <router-outlet />
      </div>
    </div>
  `,
  styles: [`
    .fastag-shell { padding: 1rem; max-width: 1400px; margin: 0 auto; }
    .fastag-shell-head { margin-bottom: 1rem; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 0.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .page-title { font-size: 1.5rem; font-weight: 700; margin: 0; }
  `],
})
export class FastagShellComponent {}
