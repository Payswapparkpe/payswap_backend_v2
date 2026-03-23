import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import type { Transaction } from 'shared';

@Component({
  selector: 'app-dashboard-recent-transactions',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="card-section mt-6">
      <div class="section-header">
        <h3 class="section-title">Recent Transactions</h3>
        <a routerLink="/payment/history" class="link-blue">History</a>
      </div>
      @if (transactions().length > 0) {
        <ul class="recent-list">
          <li class="recent-item" *ngFor="let tx of transactions()">
            <div class="recent-info">
              <div class="recent-name">{{ tx.description || 'Payment' }}</div>
              <div class="recent-meta">{{ tx.created_at || tx.timestamp | date:'mediumDate' }}</div>
              <div class="recent-txn-id">
                Txn ID: {{ tx.transactionId || tx.orderId || tx.id || '—' }}
              </div>
            </div>
            <div class="recent-right">
              <div
                class="recent-amount"
                [class.text-success]="tx.status === 'success'"
                [class.text-error]="tx.status === 'failed'"
              >
                ₹{{ tx.amount | number:'1.0-2' }}
              </div>
              <div class="recent-status" [class.status-success]="tx.status === 'success'" [class.status-failed]="tx.status === 'failed'">
                {{ tx.status | titlecase }}
              </div>
            </div>
          </li>
        </ul>
      } @else {
        <div class="recent-empty">
          <span class="material-icons">receipt_long</span>
          <p>No recent transactions</p>
        </div>
      }
    </div>
  `,
  styles: [`
    .recent-list {
      list-style: none;
      margin: 0;
      padding: 0;
    }

    .recent-item {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.9rem;
      padding: 0.85rem 0;
      border-bottom: 1px solid var(--border-light);
    }

    .recent-item:last-child {
      border-bottom: none;
    }

    .recent-info {
      min-width: 0;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }

    .recent-name {
      color: var(--text-primary);
      font-weight: 600;
      font-size: 1rem;
      line-height: 1.3;
    }

    .recent-meta {
      color: var(--text-secondary);
      font-size: 0.8rem;
    }

    .recent-txn-id {
      color: var(--text-muted);
      font-size: 0.75rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      word-break: break-all;
    }

    .recent-right {
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.35rem;
    }

    .recent-amount {
      font-weight: 700;
      color: var(--text-primary);
      font-size: 1.05rem;
      white-space: nowrap;
    }

    .recent-status {
      display: inline-block;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
      font-size: 0.68rem;
      font-weight: 600;
      background: var(--surface-dark);
      color: var(--text-secondary);
    }

    .recent-status.status-success {
      background: color-mix(in srgb, var(--success, #0d9488) 18%, transparent);
      color: var(--success, #0d9488);
    }

    .recent-status.status-failed {
      background: color-mix(in srgb, var(--error, #b91c1c) 14%, transparent);
      color: var(--error, #b91c1c);
    }

    .recent-empty {
      text-align: center;
      padding: 2rem 1rem;
      color: var(--text-muted);
      font-size: 0.9rem;
    }

    .recent-empty .material-icons {
      font-size: 2.5rem;
      opacity: 0.5;
      display: block;
      margin-bottom: 0.5rem;
    }
  `],
})
export class DashboardRecentTransactionsComponent {
  transactions = input.required<Transaction[]>();
}
