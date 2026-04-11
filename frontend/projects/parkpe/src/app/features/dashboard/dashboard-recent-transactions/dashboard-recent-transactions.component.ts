import { Component, input } from '@angular/core';
import { CommonModule, TitleCasePipe, DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import type { Transaction } from 'shared';

/** Pick a Material icon based on transaction description. */
function txnIcon(tx: Transaction): string {
  const d = (tx.description || '').toLowerCase();
  if (d.includes('bill') || d.includes('bbps') || d.includes('electricity') || d.includes('water') || d.includes('gas')) return 'receipt_long';
  if (d.includes('fastag') || d.includes('toll') || d.includes('recharge')) return 'toll';
  if (d.includes('voucher') || d.includes('gift')) return 'card_giftcard';
  if (d.includes('parking')) return 'local_parking';
  if (d.includes('challan') || d.includes('fine')) return 'gavel';
  if (d.includes('wallet') || d.includes('topup') || d.includes('load')) return 'account_balance_wallet';
  return 'payments';
}

@Component({
  selector: 'app-dashboard-recent-transactions',
  standalone: true,
  imports: [CommonModule, RouterLink, TitleCasePipe, DatePipe, DecimalPipe],
  template: `
    <div class="card-section mt-6">
      <div class="section-header">
        <h3 class="section-title">Recent Transactions</h3>
        <a routerLink="/payment/history" class="link-blue">History</a>
      </div>
      @if (transactions().length > 0) {
        <ul class="recent-list" role="list">
          @for (tx of transactions(); track (tx.transactionId ?? tx.orderId ?? tx.id ?? $index)) {
            <li class="recent-item">
              <div class="recent-icon-wrap"
                [class.recent-icon-wrap--success]="tx.status === 'success'"
                [class.recent-icon-wrap--failed]="tx.status === 'failed'">
                <span class="material-icons recent-icon" aria-hidden="true">{{ getTxnIcon(tx) }}</span>
              </div>
              <div class="recent-info">
                <div class="recent-name">{{ tx.description || 'Payment' }}</div>
                <div class="recent-meta">{{ tx.created_at || tx.timestamp | date:'d MMM yyyy, h:mm a' }}</div>
              </div>
              <div class="recent-right">
                <div class="recent-amount"
                  [class.text-success]="tx.status === 'success'"
                  [class.text-error]="tx.status === 'failed'">
                  ₹{{ tx.amount | number:'1.0-2' }}
                </div>
                <div class="recent-status"
                  [class.status-success]="tx.status === 'success'"
                  [class.status-failed]="tx.status === 'failed'">
                  {{ tx.status | titlecase }}
                </div>
              </div>
            </li>
          }
        </ul>
      } @else {
        <div class="recent-empty">
          <span class="material-icons" aria-hidden="true">receipt_long</span>
          <p>No recent transactions</p>
        </div>
      }
    </div>
  `,
  styles: [`
    .recent-list { list-style: none; margin: 0; padding: 0; }

    .recent-item {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light);
    }
    .recent-item:last-child { border-bottom: none; }

    .recent-icon-wrap {
      flex-shrink: 0;
      width: 38px;
      height: 38px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(79, 70, 229, 0.08);
      color: var(--primary-600, #4f46e5);
    }
    .recent-icon-wrap--success { background: rgba(22, 163, 74, 0.1); color: #16a34a; }
    .recent-icon-wrap--failed  { background: rgba(220, 38, 38, 0.08); color: #dc2626; }
    .recent-icon { font-size: 18px !important; }

    .recent-info { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 0.15rem; }
    .recent-name { color: var(--text-primary); font-weight: 600; font-size: 0.875rem; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .recent-meta { color: var(--text-muted); font-size: 0.72rem; }

    .recent-right { flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem; }
    .recent-amount { font-weight: 700; color: var(--text-primary); font-size: 0.95rem; white-space: nowrap; }

    .recent-status {
      display: inline-block;
      padding: 0.12rem 0.4rem;
      border-radius: 999px;
      font-size: 0.65rem;
      font-weight: 600;
      background: var(--surface-dark, #f1f5f9);
      color: var(--text-secondary);
    }
    .recent-status.status-success { background: color-mix(in srgb, #0d9488 18%, transparent); color: #0d9488; }
    .recent-status.status-failed  { background: color-mix(in srgb, #b91c1c 14%, transparent); color: #b91c1c; }

    .recent-empty { text-align: center; padding: 2rem 1rem; color: var(--text-muted); font-size: 0.9rem; }
    .recent-empty .material-icons { font-size: 2.5rem; opacity: 0.5; display: block; margin-bottom: 0.5rem; }

    .text-success { color: #16a34a !important; }
    .text-error   { color: #dc2626 !important; }
  `],
})
export class DashboardRecentTransactionsComponent {
  transactions = input.required<Transaction[]>();
  getTxnIcon = txnIcon;
}
