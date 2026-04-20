import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { VoucherService } from '../services/voucher.service';
import type { VoucherDetail, VoucherListItem } from '../../../core/models/voucher.model';

@Component({
  selector: 'app-voucher-list-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="list-detail-page">
      <a routerLink="/vouchers" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Vouchers
      </a>
      <h1 class="page-title">All Vouchers</h1>

      <div class="service-layout">
        <!-- Left: voucher list -->
        <aside class="service-col-left">
          <div class="service-panel voucher-list-wrap">
            @if (listLoading()) {
              <div class="loading-state"><div class="spinner"></div></div>
            } @else if (vouchers().length === 0) {
              <div class="empty-list">
                <span class="material-icons">card_giftcard</span>
                <p>No vouchers yet.</p>
              </div>
            } @else {
              <div class="voucher-list">
                @for (v of vouchers(); track v.id) {
                  <a
                    [routerLink]="['/vouchers/list', v.id]"
                    class="voucher-row"
                    [class.selected]="selectedId() === v.id"
                  >
                    <div class="row-header">
                      <span class="voucher-code">{{ v.voucherCode }}</span>
                      <span class="status-badge" [class]="v.status.toLowerCase()">{{ v.status | titlecase }}</span>
                    </div>
                    <div class="row-meta">
                      <span class="balance">₹{{ v.currentBalance }}</span>
                      <span class="of">of ₹{{ v.originalAmount }} · {{ v.issuedAt | date:'shortDate' }}</span>
                    </div>
                    @if (v.linkedUserPhone) {
                      <span class="row-linked">Linked: {{ v.linkedUserPhone }}</span>
                    } @else if (v.parkpeLinked === false) {
                      <span class="row-linked not-linked">Not linked</span>
                    }
                    <span class="material-icons chevron">chevron_right</span>
                  </a>
                }
              </div>
            }
          </div>
        </aside>

        <!-- Right: voucher detail or placeholder -->
        <main class="service-col-right">
          @if (!selectedId()) {
            <div class="service-placeholder">
              <p class="service-placeholder-title">Select a voucher</p>
              <p class="service-placeholder-hint">Choose a voucher from the list to view details, PIN and transaction history.</p>
            </div>
          } @else if (detailLoading()) {
            <div class="service-panel">
              <div class="loading-state"><div class="spinner"></div></div>
            </div>
          } @else if (detail()) {
            <div class="service-panel">
            <div class="detail-content">
              <h2 class="detail-title">Voucher Details</h2>

              <div class="voucher-code-block">
                <label>Voucher Code</label>
                <div class="code-value">{{ detail()!.voucherCode }}</div>
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
              } @else if (detail()!.status === 'ACTIVE' || detail()!.status === 'PARTIALLY_REDEEMED') {
                <button type="button" class="btn btn-outline" (click)="revealPin()">
                  <span class="material-icons">visibility</span> Show PIN
                </button>
              }

              <div class="amounts-row">
                <div class="amount-box">
                  <span class="amount-label">Current balance</span>
                  <span class="amount-value">₹{{ detail()!.currentBalance }}</span>
                </div>
                <div class="amount-box">
                  <span class="amount-label">Original amount</span>
                  <span class="amount-value">₹{{ detail()!.originalAmount }}</span>
                </div>
              </div>

              <div class="meta-row">
                <span class="ref">Ref: {{ detail()!.referenceNumber }}</span>
                <span class="status-badge" [class]="detail()!.status.toLowerCase()">{{ detail()!.status | titlecase }}</span>
                <span class="date">Issued {{ detail()!.issuedAt | date:'medium' }}</span>
              </div>

              <div class="link-row">
                <span class="link-label">Linked account (mobile)</span>
                @if (detail()!.linkedUserPhone) {
                  <span class="link-value">{{ detail()!.linkedUserPhone }}</span>
                } @else if (detail()!.parkpeLinked === false) {
                  <span class="link-value muted">Not linked</span>
                } @else {
                  <span class="link-value muted">—</span>
                }
              </div>
            </div>

            <div class="transactions-section">
              <h3 class="section-title">Transaction History</h3>
              @if (detail()!.transactions.length === 0) {
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
                      @for (t of detail()!.transactions; track t.id) {
                        <tr>
                          <td>{{ t.createdAt | date:'short' }}</td>
                          <td class="txn-id">{{ t.transactionId || t.transactionRef || '—' }}</td>
                          <td>{{ t.transactionDirection === 'credit' && t.transactionType === 'REDEMPTION' ? 'REFUND' : t.transactionType }}</td>
                          <td>
                            <span class="txn-dir" [class.credit]="t.transactionDirection === 'credit'" [class.debit]="t.transactionDirection !== 'credit'">
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
              <a routerLink="/vouchers" class="btn btn-outline">Buy Voucher</a>
            </div>
            </div>
          } @else {
            <div class="service-panel">
              <div class="placeholder-state error">
                <span class="material-icons">error_outline</span>
                <p>Voucher not found.</p>
              </div>
            </div>
          }
        </main>
      </div>
    </div>
  `,
  styles: [`
    .list-detail-page { padding: 1rem; max-width: 1400px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .page-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 1rem; }

    .voucher-list-wrap { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
    .voucher-list-wrap .voucher-list { flex: 1; min-height: 0; }
    .voucher-list {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      flex: 1 1 auto;
      min-height: 0;
      overflow-y: auto;
      overflow-x: hidden;
      padding-right: 0.25rem;
    }
    .voucher-list::-webkit-scrollbar { width: 6px; }
    .voucher-list::-webkit-scrollbar-track { background: var(--surface); border-radius: 3px; }
    .voucher-list::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 3px; }
    .voucher-list::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
    .voucher-row {
      display: block; text-decoration: none; color: inherit; padding: 0.85rem 1rem;
      border: 1px solid var(--border-light); border-radius: var(--radius-md);
      position: relative; transition: background 0.2s, border-color 0.2s;
    }
    .voucher-row:hover { background: var(--surface); border-color: var(--primary-200); }
    .voucher-row.selected { background: var(--primary-50); border-color: var(--primary-400); }
    .row-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; }
    .voucher-row .voucher-code { font-family: monospace; font-size: 0.875rem; font-weight: 600; }
    .status-badge {
      padding: 0.2rem 0.5rem; border-radius: var(--radius-full); font-size: 0.65rem; font-weight: 600;
    }
    .status-badge.active { background: var(--success); color: white; }
    .status-badge.partially_redeemed { background: var(--warning); color: #1a1a1a; }
    .status-badge.fully_redeemed { background: var(--text-muted); color: white; }
    .row-meta { display: flex; flex-direction: column; gap: 0.15rem; }
    .row-meta .balance { font-weight: 700; color: var(--primary-700); font-size: 1rem; }
    .row-meta .of { font-size: 0.7rem; color: var(--text-muted); }
    .row-linked { display: block; font-size: 0.65rem; color: var(--text-secondary); margin-top: 0.25rem; padding-right: 1.25rem; }
    .row-linked.not-linked { color: var(--text-muted); }
    .voucher-row .chevron { position: absolute; right: 0.75rem; top: 50%; transform: translateY(-50%); color: var(--text-muted); font-size: 18px; }

    .loading-state { display: flex; justify-content: center; padding: 2rem; }
    .spinner { width: 36px; height: 36px; border: 3px solid var(--border-light); border-top-color: var(--primary-500); border-radius: 50%; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .empty-list, .placeholder-state {
      text-align: center; padding: 2rem 1rem; color: var(--text-secondary);
    }
    .empty-list .material-icons, .placeholder-state .material-icons { font-size: 48px; color: var(--text-muted); margin-bottom: 0.75rem; display: block; }
    .placeholder-state.error .material-icons { color: var(--error-500); }
    .placeholder-state p, .empty-list p { margin: 0; font-size: 0.9375rem; }

    .detail-content { margin-bottom: 1.25rem; }
    .detail-title { font-size: 1.125rem; font-weight: 700; margin-bottom: 1rem; }
    .voucher-code-block, .pin-block {
      margin-bottom: 1rem; padding: 1rem; background: var(--surface); border-radius: var(--radius-md);
      display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem;
    }
    .voucher-code-block label, .pin-block label { width: 100%; font-size: 0.75rem; font-weight: 600; color: var(--text-secondary); }
    .code-value, .pin-value { font-family: monospace; font-size: 1.1rem; font-weight: 600; }
    .pin-loading { font-size: 0.875rem; color: var(--text-muted); margin: 0.5rem 0; }
    .amounts-row { display: flex; gap: 1rem; margin: 1rem 0; flex-wrap: wrap; }
    .amount-box { flex: 1; min-width: 100px; padding: 0.85rem; background: var(--primary-50); border-radius: var(--radius-md); }
    .amount-label { display: block; font-size: 0.75rem; color: var(--text-secondary); }
    .amount-value { font-size: 1.25rem; font-weight: 700; color: var(--primary-700); }
    .meta-row { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; font-size: 0.8125rem; color: var(--text-secondary); }
    .link-row {
      display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.5rem 1rem;
      margin-top: 0.85rem; padding-top: 0.85rem; border-top: 1px solid var(--border-light);
      font-size: 0.8125rem;
    }
    .link-label { font-weight: 600; color: var(--text-secondary); }
    .link-value { color: var(--text-primary); }
    .link-value.muted { color: var(--text-muted); }
    .transactions-section { flex: 1; min-height: 0; }
    .transactions-section .section-title { font-size: 1rem; font-weight: 700; margin-bottom: 0.75rem; }
    .empty-txn { color: var(--text-muted); font-size: 0.875rem; margin: 0; }
    .txn-wrap { width: 100%; overflow: hidden; }
    .txn-table { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 0.79rem; }
    .txn-table th, .txn-table td {
      padding: 0.42rem 0.42rem;
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
      font-size: 0.76rem;
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
    .actions-footer { margin-top: 1rem; }
    .btn-sm .material-icons { font-size: 18px; }
  `],
})
export class VoucherListDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private voucherService = inject(VoucherService);

  vouchers = signal<VoucherListItem[]>([]);
  listLoading = signal(true);
  selectedId = signal<number | null>(null);
  detail = signal<VoucherDetail | null>(null);
  detailLoading = signal(false);
  pinRevealed = signal<string | null>(null);
  pinLoading = signal(false);

  ngOnInit() {
    this.loadList();
    this.route.paramMap.subscribe((params) => {
      const id = params.get('id');
      if (id) {
        const numId = +id;
        this.selectedId.set(numId);
        this.pinRevealed.set(null);
        this.loadDetail(numId);
      } else {
        this.selectedId.set(null);
        this.detail.set(null);
      }
    });
  }

  loadList() {
    this.listLoading.set(true);
    this.voucherService.getVouchers({ limit: 100 }).subscribe({
      next: (res) => {
        this.vouchers.set(res.vouchers ?? []);
        this.listLoading.set(false);
      },
      error: () => this.listLoading.set(false),
    });
  }

  loadDetail(id: number) {
    this.detailLoading.set(true);
    this.detail.set(null);
    this.voucherService.getVoucherDetail(id).subscribe({
      next: (v) => {
        this.detail.set(v);
        this.detailLoading.set(false);
      },
      error: () => {
        this.detail.set(null);
        this.detailLoading.set(false);
      },
    });
  }

  revealPin() {
    const id = this.selectedId();
    if (id == null) return;
    this.pinLoading.set(true);
    this.voucherService.revealPin(id).subscribe({
      next: (res) => {
        this.pinRevealed.set(res.pin);
        this.pinLoading.set(false);
      },
      error: () => this.pinLoading.set(false),
    });
  }

  copyCode() {
    const v = this.detail();
    if (v?.voucherCode && navigator.clipboard) navigator.clipboard.writeText(v.voucherCode);
  }

  copyPin() {
    const pin = this.pinRevealed();
    if (pin && navigator.clipboard) navigator.clipboard.writeText(pin);
  }
}
