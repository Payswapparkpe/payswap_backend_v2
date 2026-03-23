import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-reports-shell',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <div class="reports-shell">
      <div class="shell-head">
        <a routerLink="/dashboard" class="back-link">
          <span class="material-icons">arrow_back</span> Back to Dashboard
        </a>
        <h1 class="page-title">Reports</h1>
      </div>

      <div class="service-layout">
        <aside class="service-col-left">
          <div class="service-panel reports-options">
            <h3 class="reports-options-title">Report types</h3>
            <nav class="reports-nav">
              <a routerLink="/payment/reports/payments" routerLinkActive="active" class="reports-option" [routerLinkActiveOptions]="{ exact: false }">
                <span class="material-icons">payment</span>
                Payment Report
              </a>
              <a routerLink="/payment/history" class="reports-option">
                <span class="material-icons">receipt_long</span>
                Transaction History
              </a>
              <a routerLink="/payment/reports/voucher-statement" routerLinkActive="active" class="reports-option" [routerLinkActiveOptions]="{ exact: false }">
                <span class="material-icons">account_balance_wallet</span>
                Voucher Statement
              </a>
            </nav>
          </div>
        </aside>

        <main class="service-col-right">
          @if (hasReportChild()) {
            <div class="service-panel">
              <router-outlet />
            </div>
          } @else {
            <div class="service-placeholder">
              <p class="service-placeholder-title">Select a report</p>
              <p class="service-placeholder-hint">Choose a report type from the list to view payment history, transactions or voucher statement.</p>
            </div>
          }
        </main>
      </div>
    </div>
  `,
  styles: [`
    .reports-shell { padding: 1rem; max-width: 1400px; margin: 0 auto; }
    .shell-head { margin-bottom: 1rem; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 0.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .page-title { font-size: 1.5rem; font-weight: 700; margin: 0; }
    .reports-options-title { font-size: 0.9375rem; font-weight: 600; margin: 0 0 0.75rem; }
    .reports-nav { display: flex; flex-direction: column; gap: 0.25rem; }
    .reports-option {
      display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 1rem;
      border-radius: var(--radius-md); text-decoration: none; color: var(--text-primary);
      border: 1px solid transparent; transition: background 0.2s, border-color 0.2s;
    }
    .reports-option:hover { background: var(--surface-muted, #f8fafc); }
    .reports-option.active { background: var(--primary-50); border-color: var(--primary-400); color: var(--primary-700); font-weight: 600; }
    .reports-option .material-icons { font-size: 1.25rem; }
  `],
})
export class ReportsShellComponent {
  private router = inject(Router);

  hasReportChild(): boolean {
    const u = this.router.url;
    return u.includes('/payment/reports/payments') || u.includes('/payment/reports/voucher-statement');
  }
}
