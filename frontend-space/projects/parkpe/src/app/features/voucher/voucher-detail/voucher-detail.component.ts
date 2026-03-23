import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { VoucherService } from '../services/voucher.service';
import type { VoucherDetail } from '../../../core/models/voucher.model';

@Component({
  selector: 'app-voucher-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/vouchers" class="back-link">
        <span class="material-icons">arrow_back</span> Back to My Vouchers
      </a>

      @if (loading()) {
        <div class="loading-state"><div class="spinner"></div></div>
      } @else if (voucher()) {
        <div class="detail-card card">
          <h1 class="detail-title">Voucher Details</h1>

          <div class="voucher-code-block">
            <label>Voucher Code</label>
            <div class="code-value">{{ voucher()!.voucherCode }}</div>
            <button type="button" class="btn btn-outline btn-sm" (click)="copyCode()">
              <span class="material-icons">content_copy</span> Copy
            </button>
          </div>

          @if (pinRevealed() !== null) {
            <div class="pin-block">
              <label>PIN</label>
              <div class="pin-value">{{ pinRevealed() }}</div>
              <button type="button" class="btn btn-outline btn-sm" (click)="copyPin()">
                <span class="material-icons">content_copy</span> Copy PIN
              </button>
            </div>
          } @else if (pinLoading()) {
            <p class="pin-loading">Loading PIN…</p>
          } @else if (voucher()!.status === 'ACTIVE' || voucher()!.status === 'PARTIALLY_REDEEMED') {
            <button type="button" class="btn btn-outline" (click)="revealPin()">
              <span class="material-icons">visibility</span> Show PIN
            </button>
          }

          <div class="amounts-row">
            <div class="amount-box">
              <span class="amount-label">Current balance</span>
              <span class="amount-value">₹{{ voucher()!.currentBalance }}</span>
            </div>
            <div class="amount-box">
              <span class="amount-label">Original amount</span>
              <span class="amount-value">₹{{ voucher()!.originalAmount }}</span>
            </div>
          </div>

          <div class="meta-row">
            <span class="ref">Ref: {{ voucher()!.referenceNumber }}</span>
            <span class="status-badge" [class]="voucher()!.status.toLowerCase()">{{ voucher()!.status | titlecase }}</span>
            <span class="date">Issued {{ voucher()!.issuedAt | date:'medium' }}</span>
          </div>
        </div>

        <div class="transactions-section card">
          <h2 class="section-title">Transaction History</h2>
          @if (voucher()!.transactions.length === 0) {
            <p class="empty-txn">No transactions yet.</p>
          } @else {
            <div class="txn-wrap">
              <table class="txn-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Transaction ID</th>
                    <th>Type</th>
                    <th>Direction</th>
                    <th>Amount</th>
                    <th>Balance after</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  @for (t of voucher()!.transactions; track t.id) {
                    <tr>
                      <td>{{ t.createdAt | date:'short' }}</td>
                      <td class="txn-id">{{ t.transactionId || t.transactionRef || '—' }}</td>
                      <td>{{ t.transactionDirection === 'credit' && t.transactionType === 'REDEMPTION' ? 'REFUND' : t.transactionType }}</td>
                      <td>
                        <span class="txn-dir" [class.credit]="t.transactionDirection === 'credit'" [class.debit]="t.transactionDirection === 'debit'">
                          {{ (t.transactionDirection || 'debit') | titlecase }}
                        </span>
                      </td>
                      <td>
                        @if (t.transactionAmount != null) {
                          <span [class.credit-amt]="t.transactionDirection === 'credit'" [class.debit-amt]="t.transactionDirection !== 'credit'">
                            ₹{{ t.transactionAmount }}
                          </span>
                        } @else { — }
                      </td>
                      <td>₹{{ t.balanceAfter }}</td>
                      <td><span class="txn-status" [class.success]="t.transactionStatus === 'SUCCESS'">{{ t.transactionStatus }}</span></td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </div>

        <div class="actions-footer">
          <a routerLink="/vouchers" class="btn btn-outline">All Vouchers</a>
          <a routerLink="/vouchers" class="btn btn-primary">Buy Another Voucher</a>
        </div>
      } @else {
        <div class="empty-state card">
          <span class="material-icons">error_outline</span>
          <h3>Voucher not found</h3>
          <a routerLink="/vouchers" class="btn btn-primary">Back to My Vouchers</a>
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 1rem; max-width: 720px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .loading-state { display: flex; justify-content: center; padding: 3rem; }
    .spinner { width: 40px; height: 40px; border: 3px solid var(--border-light); border-top-color: var(--primary-500); border-radius: 50%; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .detail-card { padding: 1.5rem; margin-bottom: 1.5rem; }
    .detail-title { font-size: 1.25rem; font-weight: 700; margin-bottom: 1.5rem; }
    .voucher-code-block, .pin-block {
      margin-bottom: 1rem; padding: 1rem; background: var(--surface); border-radius: var(--radius-md);
      display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem;
    }
    .voucher-code-block label, .pin-block label { width: 100%; font-size: 0.75rem; font-weight: 600; color: var(--text-secondary); }
    .code-value, .pin-value { font-family: monospace; font-size: 1.25rem; font-weight: 600; }
    .pin-loading { font-size: 0.875rem; color: var(--text-muted); margin: 0.5rem 0; }
    .amounts-row { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
    .amount-box { flex: 1; min-width: 120px; padding: 1rem; background: var(--primary-50); border-radius: var(--radius-md); }
    .amount-label { display: block; font-size: 0.75rem; color: var(--text-secondary); }
    .amount-value { font-size: 1.5rem; font-weight: 700; color: var(--primary-700); }
    .meta-row { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; font-size: 0.875rem; color: var(--text-secondary); }
    .status-badge { padding: 0.25rem 0.75rem; border-radius: var(--radius-full); font-size: 0.75rem; font-weight: 600; }
    .status-badge.active { background: var(--success); color: white; }
    .status-badge.partially_redeemed { background: var(--warning); color: #1a1a1a; }
    .status-badge.fully_redeemed { background: var(--text-muted); color: white; }
    .transactions-section { padding: 1.5rem; overflow: hidden; }
    .section-title { font-size: 1.125rem; font-weight: 700; margin-bottom: 1rem; }
    .empty-txn { color: var(--text-muted); font-size: 0.9375rem; margin: 0; }
    .txn-wrap { width: 100%; overflow: hidden; }
    .txn-table { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 0.81rem; }
    .txn-table th, .txn-table td {
      padding: 0.45rem 0.45rem;
      text-align: left;
      border-bottom: 1px solid var(--border-light);
      vertical-align: middle;
      word-break: break-word;
      overflow-wrap: anywhere;
      white-space: normal;
    }
    .txn-table th { font-weight: 600; color: var(--text-secondary); }
    .txn-status.success { color: var(--success); font-weight: 600; }
    .txn-id {
      font-family: monospace;
      font-size: 0.8rem;
      color: var(--text-secondary);
      word-break: break-all;
      min-width: 0;
      max-width: none;
    }
    .txn-dir {
      display: inline-flex; align-items: center; justify-content: center;
      min-width: 68px; padding: 0.2rem 0.55rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
      background: var(--surface); color: var(--text-secondary); border: 1px solid var(--border-light);
    }
    .txn-dir.credit { background: rgba(16, 185, 129, 0.12); color: #047857; border-color: rgba(16, 185, 129, 0.25); }
    .txn-dir.debit { background: rgba(239, 68, 68, 0.10); color: #b91c1c; border-color: rgba(239, 68, 68, 0.25); }
    .credit-amt { color: #047857; font-weight: 600; }
    .debit-amt { color: #b91c1c; font-weight: 600; }
    .actions-footer { display: flex; gap: 1rem; margin-top: 1.5rem; flex-wrap: wrap; }
    .empty-state { text-align: center; padding: 2rem; }
    .empty-state .material-icons { font-size: 48px; color: var(--text-muted); margin-bottom: 1rem; }
    .btn-sm .material-icons { font-size: 18px; }
  `],
})
export class VoucherDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private voucherService = inject(VoucherService);

  voucher = signal<VoucherDetail | null>(null);
  loading = signal(true);
  pinRevealed = signal<string | null>(null);
  pinLoading = signal(false);

  private voucherId = 0;

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      this.loading.set(false);
      return;
    }
    this.voucherId = +id;
    this.voucherService.getVoucherDetail(this.voucherId).subscribe({
      next: (v) => this.voucher.set(v),
      error: () => this.voucher.set(null),
      complete: () => this.loading.set(false),
    });
  }

  revealPin() {
    this.pinLoading.set(true);
    this.voucherService.revealPin(this.voucherId).subscribe({
      next: (res) => {
        this.pinRevealed.set(res.pin);
        this.pinLoading.set(false);
      },
      error: () => this.pinLoading.set(false),
    });
  }

  copyCode() {
    const v = this.voucher();
    if (v?.voucherCode && navigator.clipboard) {
      navigator.clipboard.writeText(v.voucherCode);
    }
  }

  copyPin() {
    const pin = this.pinRevealed();
    if (pin && navigator.clipboard) {
      navigator.clipboard.writeText(pin);
    }
  }
}
