import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MobilityStateStore } from '../../../core/stores/mobility-state.store';
import { RealtimeStatusService } from '../../../core/services/realtime-status.service';
import { Subscription } from 'rxjs';

type Tone = 'success' | 'error' | 'warning';

@Component({
  selector: 'app-payment-status',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="status-container">
      <div class="status-card card scale-in" [ngClass]="toneClass">
        @if (tone === 'success') {
          <img
            class="b-assured-logo"
            src="assets/bbps/b-assured-logo.png"
            alt="B Assured"
          />
        }

        <div class="status-icon" [class.error]="tone === 'error'" [class.warning]="tone === 'warning'">
          <span class="material-icons">{{ statusIcon }}</span>
        </div>

        <h1 class="status-title">{{ headline }}</h1>
        <p class="status-message">{{ statusMessage }}</p>
        @if (usingCachedSnapshot) {
          <p class="cached-note">
            Showing last saved status from offline cache
            @if (snapshotTs) { · {{ snapshotTs | date:'short' }} }
          </p>
        }

        @if (tone === 'success') {
          <p class="voucher-hint">Your new voucher is available under My Vouchers.</p>
        }

        <section class="receipt" aria-label="Payment receipt">
          <div class="receipt-perf" aria-hidden="true"></div>
          <div class="receipt-title-row">
            <span class="receipt-title">Payment receipt</span>
            <span class="receipt-badge" [ngClass]="'badge-' + tone">{{ badgeLabel }}</span>
          </div>
          <dl class="receipt-rows">
            <div class="receipt-row">
              <dt>Order ID</dt>
              <dd>{{ orderRef || '—' }}</dd>
            </div>
            <div class="receipt-row">
              <dt>Gateway payment ID</dt>
              <dd>{{ gatewayRef || '—' }}</dd>
            </div>
            <div class="receipt-row">
              <dt>Amount</dt>
              <dd>{{ amountLabel }}</dd>
            </div>
            <div class="receipt-row">
              <dt>Date &amp; time</dt>
              <dd>{{ currentDate | date: 'medium' }}</dd>
            </div>
            @if (gatewayLabel) {
              <div class="receipt-row subtle">
                <dt>Gateway</dt>
                <dd>{{ gatewayLabel }}</dd>
              </div>
            }
          </dl>
        </section>

        <div class="status-actions">
          @if (tone === 'success' && orderRef) {
            <button
              type="button"
              class="btn btn-outline"
              (click)="viewInvoice()"
            >
              View Invoice
            </button>
          }
          @if (tone !== 'success') {
            <button type="button" class="btn btn-primary" (click)="retry()">Try again</button>
            <button type="button" class="btn btn-outline" routerLink="/dashboard">Back to Dashboard</button>
          } @else {
            <button type="button" class="btn btn-primary" routerLink="/dashboard">Back to Dashboard</button>
          }
          <a class="btn btn-outline" routerLink="/vouchers">Vouchers</a>
          @if (tone === 'success') {
            <a class="btn btn-outline" routerLink="/bbps">Pay another bill</a>
          }
          <button type="button" class="btn btn-outline" routerLink="/payment/history">View History</button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .status-container {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      background: linear-gradient(135deg, var(--primary-50) 0%, var(--secondary-50) 100%);
    }
    .status-card {
      max-width: 440px;
      width: 100%;
      padding: 2rem 1.75rem 2.25rem;
      text-align: center;

      .b-assured-logo {
        display: block;
        height: 48px;
        width: auto;
        max-width: 180px;
        margin: 0 auto 0.75rem;
        padding: 12px;
        object-fit: contain;
      }
    }
    .status-card.success .status-icon .material-icons {
      color: var(--success);
    }
    .status-card.error .status-icon .material-icons {
      color: var(--error);
    }
    .status-card.warning .status-icon .material-icons {
      color: var(--warning, #d97706);
    }
    .status-icon .material-icons {
      font-size: 72px;
      animation: scaleIn 0.5s ease;
    }
    .status-title {
      font-size: 1.5rem;
      font-weight: 700;
      margin: 0.5rem 0 0.75rem;
      color: var(--text-primary);
      line-height: 1.3;
    }
    .status-message {
      color: var(--text-secondary);
      margin: 0 0 1.25rem;
      font-size: 0.95rem;
      line-height: 1.5;
    }
    .cached-note {
      margin: -0.5rem 0 1rem;
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .voucher-hint {
      color: var(--text-secondary);
      font-size: 0.95rem;
      margin: 0 0 1rem;
    }
    .receipt {
      text-align: left;
      position: relative;
      margin-bottom: 1.5rem;
      padding: 1.25rem 1.25rem 1rem;
      background: var(--surface);
      border-radius: var(--radius-md);
      border: 1px dashed var(--border);
      box-shadow: 0 1px 0 rgba(0, 0, 0, 0.04), 0 8px 24px rgba(0, 0, 0, 0.06);
    }
    .receipt-perf {
      height: 4px;
      margin: -1.25rem -1.25rem 0.75rem;
      border-radius: var(--radius-md) var(--radius-md) 0 0;
      background: repeating-linear-gradient(
        90deg,
        var(--border-light),
        var(--border-light) 4px,
        transparent 4px,
        transparent 8px
      );
      opacity: 0.85;
    }
    .receipt-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      margin-bottom: 1rem;
    }
    .receipt-title {
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-secondary);
    }
    .receipt-badge {
      font-size: 0.7rem;
      font-weight: 600;
      padding: 0.2rem 0.55rem;
      border-radius: 999px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .badge-success {
      background: color-mix(in srgb, var(--success) 18%, transparent);
      color: var(--success);
    }
    .badge-error {
      background: color-mix(in srgb, var(--error) 15%, transparent);
      color: var(--error);
    }
    .badge-warning {
      background: color-mix(in srgb, var(--warning, #d97706) 18%, transparent);
      color: var(--warning, #b45309);
    }
    .receipt-rows {
      margin: 0;
    }
    .receipt-row {
      display: grid;
      grid-template-columns: minmax(0, 42%) minmax(0, 58%);
      gap: 0.75rem;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--border-light);
      font-size: 0.875rem;
    }
    .receipt-row:last-child {
      border-bottom: none;
      padding-bottom: 0;
    }
    .receipt-row.subtle dt,
    .receipt-row.subtle dd {
      font-size: 0.8rem;
      color: var(--text-secondary);
    }
    .receipt-row dt {
      margin: 0;
      color: var(--text-secondary);
      font-weight: 500;
    }
    .receipt-row dd {
      margin: 0;
      font-weight: 600;
      color: var(--text-primary);
      word-break: break-word;
    }
    .status-actions {
      display: flex;
      gap: 0.75rem;
      justify-content: center;
      flex-wrap: wrap;
    }
  `],
})
export class PaymentStatusComponent implements OnInit, OnDestroy {
  tone: Tone = 'success';
  currentDate = new Date();
  /** Our order / transaction reference (TID). */
  orderRef = '';
  /** Payment gateway payment id (e.g. Cashfree cf_payment_id). */
  gatewayRef = '';
  amount: number | null = null;
  statusMessage = '';
  headline = '';
  gatewayLabel = '';
  usingCachedSnapshot = false;
  snapshotTs: number | null = null;

  private store = inject(MobilityStateStore);
  private realtime = inject(RealtimeStatusService);
  private realtimeSub: Subscription | null = null;

  constructor(private route: ActivatedRoute, private router: Router) {}

  get toneClass(): Record<string, boolean> {
    return {
      success: this.tone === 'success',
      error: this.tone === 'error',
      warning: this.tone === 'warning',
    };
  }

  get statusIcon(): string {
    if (this.tone === 'success') return 'check_circle';
    if (this.tone === 'warning') return 'schedule';
    return 'error';
  }

  get badgeLabel(): string {
    if (this.tone === 'success') return 'Paid';
    if (this.tone === 'warning') return 'Pending';
    return 'Failed';
  }

  get amountLabel(): string {
    if (this.amount != null && !Number.isNaN(this.amount)) {
      return '₹' + this.amount.toFixed(2);
    }
    return '—';
  }

  ngOnInit() {
    const q = this.route.snapshot.queryParams;
    const hasFreshQuery = !!(q['status'] || q['orderId'] || q['transactionId'] || q['gatewayPaymentId']);
    const cached = this.store.paymentStatusSnapshot();
    if (!hasFreshQuery && cached) {
      this.usingCachedSnapshot = true;
      this.snapshotTs = this.store.paymentStatusSnapshotTs();
      this.tone = cached.tone;
      this.orderRef = cached.orderRef;
      this.gatewayRef = cached.gatewayRef;
      this.amount = cached.amount;
      this.statusMessage = cached.statusMessage;
      this.headline = cached.headline;
      this.gatewayLabel = cached.gatewayLabel;
      return;
    }
    this.usingCachedSnapshot = false;
    const status = q['status'] === 'success' ? 'success' : 'failed';
    const reason = q['reason'];

    this.orderRef =
      (q['transactionId'] || q['orderId'] || '').trim() ||
      (q['transaction_id'] || '').trim();
    this.gatewayRef =
      (q['gatewayPaymentId'] || q['pgPaymentId'] || q['cf_payment_id'] || '').trim();
    const amt = q['amount'];
    this.amount = amt != null && amt !== '' ? Number(amt) : null;
    if (Number.isNaN(this.amount as number)) {
      this.amount = null;
    }

    const gw = (q['gateway'] || '').toLowerCase();
    this.gatewayLabel =
      gw === 'cashfree'
        ? 'Cashfree'
        : gw === 'bbps'
          ? 'BBPS'
          : '';

    if (status === 'success') {
      this.tone = 'success';
      this.headline = 'Payment successful';
      this.statusMessage = 'Your payment has been processed successfully.';
      this.saveSnapshot();
      return;
    }

    if (reason === 'voucher_delayed') {
      this.tone = 'warning';
      this.headline = 'Payment received — voucher pending';
      this.statusMessage = this.orderRef
        ? `Your payment went through, but your voucher could not be added immediately. It should appear shortly under My Vouchers. If not, contact support with Order ID: ${this.orderRef}.`
        : `Your payment went through, but your voucher could not be added immediately. It should appear shortly under My Vouchers. Contact support with your payment details if it does not.`;
      this.saveSnapshot();
      this.tryRealtimeUpgrade();
      return;
    }

    this.tone = 'error';
    if (reason === 'incomplete') {
      this.headline = 'Payment incomplete';
      this.statusMessage =
        'You returned without completing payment. No amount was charged.';
    } else if (reason === 'not_confirmed') {
      this.headline = 'Payment not confirmed';
      this.statusMessage =
        'We could not confirm this payment with the gateway. If money was debited, it may be reversed automatically or your voucher may appear shortly under My Vouchers. Keep your Order ID and gateway payment ID handy for support.';
    } else {
      this.headline = 'Payment not completed';
      this.statusMessage =
        'Something went wrong. You can try again or return to the dashboard.';
    }
    this.saveSnapshot();
    this.tryRealtimeUpgrade();
  }

  viewInvoice() {
    if (!this.orderRef) return;
    const transaction = {
      id: this.orderRef,
      transactionId: this.orderRef,
      orderId: this.orderRef,
      amount: this.amount ?? 0,
      description: 'BBPS Bill Payment',
      gateway: 'bbps' as const,
      timestamp: this.currentDate.toISOString(),
      status: 'success' as const,
      transactionType: 'bbps' as const,
      currency: 'INR',
      customer: { name: '', email: '', phone: '' },
    };
    this.router.navigate(['/payment/receipt', this.orderRef], {
      state: { transaction },
    });
  }

  retry() {
    this.router.navigate(['/vouchers']);
  }

  ngOnDestroy(): void {
    this.realtimeSub?.unsubscribe();
  }

  private saveSnapshot(): void {
    this.store.setPaymentStatusSnapshot({
      tone: this.tone,
      orderRef: this.orderRef,
      gatewayRef: this.gatewayRef,
      amount: this.amount,
      statusMessage: this.statusMessage,
      headline: this.headline,
      gatewayLabel: this.gatewayLabel,
    });
  }

  private tryRealtimeUpgrade(): void {
    if (!this.orderRef || this.tone === 'success') return;
    this.realtimeSub?.unsubscribe();
    this.realtimeSub = this.realtime.watchPayment(this.orderRef, 45_000).subscribe((txn) => {
      if (!txn || txn.status !== 'success') return;
      this.tone = 'success';
      this.headline = 'Payment confirmed';
      this.statusMessage = 'We just received a successful confirmation from the gateway.';
      this.orderRef = txn.orderId || txn.transactionId || this.orderRef;
      this.amount = typeof txn.amount === 'number' ? txn.amount : this.amount;
      this.saveSnapshot();
    });
  }
}
