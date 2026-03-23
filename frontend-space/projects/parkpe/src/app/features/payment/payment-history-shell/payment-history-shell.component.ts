import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { TransactionHistoryComponent } from '../transaction-history/transaction-history.component';

@Component({
  selector: 'app-payment-history-shell',
  standalone: true,
  imports: [CommonModule, RouterLink, TransactionHistoryComponent],
  template: `
    <div class="payment-history-shell">
      <div class="shell-head">
        <a routerLink="/dashboard" class="back-link">
          <span class="material-icons">arrow_back</span> Back to Dashboard
        </a>
        <h1 class="page-title">Transaction History</h1>
        <p class="page-subtitle">View and search all your payment and voucher transactions.</p>
      </div>

      <div class="history-full">
        <app-transaction-history [embedded]="true" />
      </div>
    </div>
  `,
  styles: [`
    .payment-history-shell { padding: 1rem; width: 100%; max-width: none; margin: 0; box-sizing: border-box; }
    .shell-head { margin-bottom: 1rem; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 0.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .page-title { font-size: 1.5rem; font-weight: 700; margin: 0 0 0.25rem; }
    .page-subtitle { font-size: 0.9375rem; color: var(--text-secondary); margin: 0; }
    .history-full { width: 100%; min-width: 0; min-height: 0; }
  `],
})
export class PaymentHistoryShellComponent {}
