import { ChangeDetectorRef, Component, OnDestroy, OnInit, inject } from '@angular/core';
import { CommonModule, APP_BASE_HREF } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MobilityStateStore } from '../../../core/stores/mobility-state.store';
import { RealtimeStatusService } from '../../../core/services/realtime-status.service';
import { BBPSService } from '../../bbps/services/bbps.service';
import { race, Subject, Subscription, timer } from 'rxjs';
import { filter, map, switchMap, take, takeUntil } from 'rxjs/operators';
import type { PaymentGateway, PaymentStatus, TransactionType } from 'shared';

type Tone = 'success' | 'error' | 'warning' | 'pending';

@Component({
  selector: 'app-payment-status',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="status-container">
      <div class="status-card card scale-in" [ngClass]="toneClass">
        @if (bharatBillpayReceipt) {
          <header class="ps-brands" role="banner">
            <img class="ps-brand-parkpe" [src]="assetUrl('/assets/parkpe-logo.svg')" alt="ParkPe" />
            <div class="ps-brand-bharat" role="img" aria-label="Bharat Bill Pay">
              <img [src]="assetUrl('/assets/bbps/bharat-connect-logo.png')" alt="" />
              <span class="ps-brand-bharat-text">Bharat Bill Pay</span>
            </div>
          </header>
        } @else if (tone === 'success') {
          <div class="parkpe-mark" aria-hidden="true">ParkPe</div>
        }

        <div
          class="status-icon"
          [class.error]="tone === 'error'"
          [class.warning]="tone === 'warning' || tone === 'pending'"
        >
          <span class="material-icons" [class.sync-pulse]="tone === 'pending'">{{ statusIcon }}</span>
        </div>

        <h1 class="status-title">{{ headline }}</h1>
        <p class="status-message">{{ statusMessage }}</p>
        @if (usingCachedSnapshot) {
          <p class="cached-note">
            Showing last saved status from offline cache
            @if (snapshotTs) { · {{ snapshotTs | date: 'short' }} }
          </p>
        }

        @if (showPaymentReceipt) {
          <section
            class="receipt"
            [class.receipt--bbps]="bharatBillpayReceipt"
            [style.--b-assured-wm]="bharatBillpayReceipt ? bAssuredWatermarkCssUrl : null"
            aria-label="Payment receipt"
          >
            <div class="receipt-perf" aria-hidden="true"></div>
            <div class="receipt-title-row">
              <span class="receipt-title">Payment receipt</span>
              <span class="receipt-badge" [ngClass]="receiptBadgeClass">{{ badgeLabel }}</span>
            </div>
            <dl class="receipt-rows">
              <div class="receipt-row">
                <dt>Order ID</dt>
                <dd>{{ orderRef || '—' }}</dd>
              </div>
              <div class="receipt-row">
                <dt>Amount</dt>
                <dd>{{ amountLabel }}</dd>
              </div>
              <div class="receipt-row">
                <dt>Date &amp; time</dt>
                <dd>{{ currentDate | date: 'medium' }}</dd>
              </div>
              @if (gatewayLabel && !bharatBillpayReceipt) {
                <div class="receipt-row subtle">
                  <dt>Gateway</dt>
                  <dd>{{ gatewayLabel }}</dd>
                </div>
              }
            </dl>
          </section>
        }

        <div class="status-actions">
          @if (tone === 'success' && orderRef) {
            <button type="button" class="btn btn-outline" (click)="viewInvoice()">View Invoice</button>
          }
          @if (tone === 'pending') {
            <button type="button" class="btn btn-outline" routerLink="/bbps">Back to bills</button>
            <button type="button" class="btn btn-outline" routerLink="/payment/history">View History</button>
          }
          @if (tone !== 'success' && tone !== 'pending') {
            <button type="button" class="btn btn-primary" (click)="retry()">Try again</button>
            <button type="button" class="btn btn-outline" routerLink="/dashboard">Back to Dashboard</button>
          }
          @if (tone === 'success') {
            <button type="button" class="btn btn-primary" routerLink="/dashboard">Back to Dashboard</button>
          }
          @if (tone !== 'pending') {
            <a class="btn btn-outline" routerLink="/vouchers">Vouchers</a>
          }
          @if (tone === 'success' && bharatBillpayReceipt) {
            <a class="btn btn-outline" routerLink="/bbps">Pay another bill</a>
          }
          @if (tone !== 'pending') {
            <button type="button" class="btn btn-outline" routerLink="/payment/history">View History</button>
          }
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

      .parkpe-mark {
        font-weight: 800;
        font-size: 1.125rem;
        letter-spacing: 0.06em;
        color: var(--primary-700);
        margin: 0 auto 0.75rem;
      }
    }
    .ps-brands {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      margin: 0 0 1rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid color-mix(in srgb, var(--border) 75%, transparent);
      text-align: left;
    }
    .ps-brand-parkpe {
      width: 132px;
      max-height: 44px;
      height: auto;
      object-fit: contain;
    }
    .ps-brand-bharat {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.25rem;
      min-width: 0;
    }
    .ps-brand-bharat img {
      width: 108px;
      max-height: 48px;
      height: auto;
      object-fit: contain;
      object-position: right center;
    }
    .ps-brand-bharat-text {
      font-size: 0.65rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      color: #1e3a5f;
      text-transform: none;
    }
    .status-card.success .status-icon .material-icons {
      color: var(--success);
    }
    .status-card.error .status-icon .material-icons {
      color: var(--error);
    }
    .status-card.warning .status-icon .material-icons,
    .status-card.pending .status-icon .material-icons {
      color: var(--warning, #d97706);
    }
    .status-icon .material-icons {
      font-size: 72px;
      animation: scaleIn 0.5s ease;
    }
    .status-icon .material-icons.sync-pulse {
      animation: bbps-spin-pulse 1.2s linear infinite;
    }
    @keyframes bbps-spin-pulse {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
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
    .receipt {
      text-align: left;
      position: relative;
      margin-bottom: 1.5rem;
      padding: 1.25rem 1.25rem 1rem;
      background: var(--surface);
      border-radius: var(--radius-md);
      border: 1px dashed var(--border);
      box-shadow: 0 1px 0 rgba(0, 0, 0, 0.04), 0 8px 24px rgba(0, 0, 0, 0.06);
      overflow: hidden;
    }
    .receipt--bbps::before {
      content: '';
      position: absolute;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      background-image: var(--b-assured-wm, none);
      background-repeat: no-repeat;
      background-position: center center;
      background-size: min(88%, 280px) auto;
      opacity: 0.24;
      filter: grayscale(0.12);
    }
    .receipt--bbps .receipt-perf,
    .receipt--bbps .receipt-title-row,
    .receipt--bbps .receipt-rows {
      position: relative;
      z-index: 1;
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
      margin-bottom: 0.75rem;
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
    .badge-pending {
      background: color-mix(in srgb, var(--primary-500) 16%, transparent);
      color: var(--primary-700);
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
    @media (max-width: 420px) {
      .ps-brand-parkpe { width: 112px; max-height: 38px; }
      .ps-brand-bharat img { width: 92px; max-height: 40px; }
      .ps-brands { flex-wrap: wrap; }
    }
  `],
})
export class PaymentStatusComponent implements OnInit, OnDestroy {
  tone: Tone = 'success';
  currentDate = new Date();
  /** Our order / transaction reference (TID). */
  orderRef = '';
  /** True when this screen is a Bharat Billpay (BBPS) bill flow — show NPCI/Bharat marks. */
  bharatBillpayReceipt = false;
  amount: number | null = null;
  statusMessage = '';
  headline = '';
  gatewayLabel = '';
  usingCachedSnapshot = false;
  snapshotTs: number | null = null;

  private store = inject(MobilityStateStore);
  private realtime = inject(RealtimeStatusService);
  private bbps = inject(BBPSService);
  private cdr = inject(ChangeDetectorRef);
  private readonly appBaseHref = inject(APP_BASE_HREF);
  private realtimeSub: Subscription | null = null;
  private mobikwikPollSub: Subscription | null = null;
  private readonly destroy$ = new Subject<void>();

  constructor(private route: ActivatedRoute, private router: Router) {}

  get toneClass(): Record<string, boolean> {
    return {
      success: this.tone === 'success',
      error: this.tone === 'error',
      warning: this.tone === 'warning',
      pending: this.tone === 'pending',
    };
  }

  get statusIcon(): string {
    if (this.tone === 'success') return 'check_circle';
    if (this.tone === 'pending') return 'sync';
    if (this.tone === 'warning') return 'schedule';
    return 'error';
  }

  get badgeLabel(): string {
    if (this.tone === 'success') return 'Paid';
    if (this.tone === 'pending') return 'Waiting';
    if (this.tone === 'warning') return 'Pending';
    return 'Failed';
  }

  get receiptBadgeClass(): string {
    if (this.tone === 'success') return 'badge-success';
    if (this.tone === 'warning') return 'badge-warning';
    if (this.tone === 'error') return 'badge-error';
    return 'badge-pending';
  }

  /** BBPS: receipt on confirmed success or on failed attempt (Failed badge); not while pending. */
  get showPaymentReceipt(): boolean {
    if (this.tone === 'pending') return false;
    if (this.bharatBillpayReceipt) return this.tone === 'success' || this.tone === 'error';
    return true;
  }

  assetUrl(path: string): string {
    const p = path.startsWith('/') ? path : `/${path}`;
    const base = (this.appBaseHref || '/').replace(/\/$/, '');
    if (!base) return p;
    return `${base}${p}`;
  }

  get bAssuredWatermarkCssUrl(): string {
    const u = this.assetUrl('/assets/bbps/b-assured-logo.png');
    return `url(${JSON.stringify(u)})`;
  }

  get amountLabel(): string {
    if (this.amount != null && !Number.isNaN(this.amount)) {
      return '₹' + this.amount.toFixed(2);
    }
    return '—';
  }

  /**
   * Backend `generate_transaction_id`: fixed 20 chars — T + 18 digits + 1 [0-9A-Z].
   * Used for BBPS bill pay refs even when `gateway=bbps` is missing from the URL.
   */
  private inferParkPeBbpsTransactionRef(tid: string): boolean {
    const t = (tid || '').trim();
    return t.length === 20 && /^T\d{18}[0-9A-Z]$/.test(t);
  }

  /** Replace stale cached headline/body (older builds) with current product copy. */
  private applyCanonicalStatusCopy(): void {
    if (this.tone !== 'success') return;
    if (this.bharatBillpayReceipt) {
      this.headline = 'Payment confirmed';
      this.statusMessage =
        'Bharat Bill Pay (BBPS) bill payment. Mobikwik / biller network confirmed this transaction. Reference and amount are below.';
    } else {
      this.headline = 'Payment confirmed';
      this.statusMessage =
        'We received a successful confirmation from the payment gateway. Details are shown in the receipt below.';
    }
  }

  ngOnInit() {
    this.route.queryParamMap.pipe(takeUntil(this.destroy$)).subscribe(() => {
      this.hydrateFromRoute();
    });
  }

  /**
   * Runs on load and whenever query params change. Same-route navigations reuse the component;
   * without this, pasting `?status=failed` after a success visit would keep the old UI.
   */
  private hydrateFromRoute(): void {
    const q = this.route.snapshot.queryParamMap;
    const hasFreshQuery = !!(
      q.get('status') ||
      q.get('orderId') ||
      q.get('transactionId') ||
      q.get('transaction_id') ||
      q.get('gateway') ||
      q.get('bbps') ||
      q.get('gatewayPaymentId') ||
      q.get('reason') ||
      q.get('detail') ||
      q.get('amount')
    );
    const cached = this.store.paymentStatusSnapshot();
    if (!hasFreshQuery && cached) {
      this.usingCachedSnapshot = true;
      this.snapshotTs = this.store.paymentStatusSnapshotTs();
      this.tone = (cached.tone as Tone) || 'success';
      this.orderRef = cached.orderRef;
      this.amount = cached.amount;
      this.statusMessage = cached.statusMessage;
      this.headline = cached.headline;
      this.gatewayLabel = cached.gatewayLabel;
      this.bharatBillpayReceipt =
        !!cached.bharatBillpayReceipt ||
        cached.gatewayLabel === 'BBPS' ||
        this.inferParkPeBbpsTransactionRef(this.orderRef);
      this.applyCanonicalStatusCopy();
      if (
        this.tone === 'pending' &&
        this.bharatBillpayReceipt &&
        this.orderRef
      ) {
        queueMicrotask(() => this.startMobikwikStatusPoll());
      } else if (this.tone === 'pending' && this.orderRef && !this.bharatBillpayReceipt) {
        queueMicrotask(() => this.tryRealtimeUpgrade());
      }
      this.cdr.markForCheck();
      return;
    }
    this.usingCachedSnapshot = false;
    const reason = q.get('reason') || '';
    const rawStatus = (q.get('status') || '').toLowerCase();

    if (rawStatus === 'failed' || rawStatus === 'success') {
      this.mobikwikPollSub?.unsubscribe();
      this.mobikwikPollSub = null;
      this.realtimeSub?.unsubscribe();
      this.realtimeSub = null;
    }

    this.orderRef =
      (q.get('transactionId') || q.get('orderId') || '').trim() ||
      (q.get('transaction_id') || '').trim();
    const amt = q.get('amount');
    this.amount = amt != null && amt !== '' ? Number(amt) : null;
    if (Number.isNaN(this.amount as number)) {
      this.amount = null;
    }

    const gw = (q.get('gateway') || '').toLowerCase();
    this.gatewayLabel =
      gw === 'cashfree'
        ? 'Cashfree'
        : gw === 'bbps'
          ? 'BBPS'
          : '';
    const bbpsFlag = String(q.get('bbps') || '').toLowerCase();
    this.bharatBillpayReceipt =
      gw === 'bbps' ||
      bbpsFlag === '1' ||
      bbpsFlag === 'true' ||
      this.inferParkPeBbpsTransactionRef(
        (q.get('transactionId') || q.get('orderId') || q.get('transaction_id') || '').trim()
      );

    if (rawStatus === 'pending' && this.bharatBillpayReceipt && this.orderRef) {
      this.tone = 'pending';
      this.headline = 'Waiting for confirmation';
      this.statusMessage =
        'Your payment was submitted to the biller network. We are waiting for a final success response from Mobikwik before showing a receipt.';
      this.saveSnapshot();
      queueMicrotask(() => this.startMobikwikStatusPoll());
      this.cdr.markForCheck();
      return;
    }

    if (rawStatus === 'success') {
      this.tone = 'success';
      if (this.bharatBillpayReceipt) {
        this.headline = 'Payment confirmed';
        this.statusMessage =
          'Bharat Bill Pay (BBPS) bill payment. Mobikwik / biller network confirmed this transaction. Reference and amount are below.';
      } else {
        this.headline = 'Payment successful';
        this.statusMessage =
          'We received a successful confirmation from the payment gateway. Details are shown in the receipt below.';
      }
      this.saveSnapshot();
      this.cdr.markForCheck();
      return;
    }

    if (rawStatus === 'failed') {
      const fromQuery = (q.get('detail') || q.get('message') || '').toString().trim();
      this.tone = 'error';
      if (this.bharatBillpayReceipt) {
        this.headline = 'Bill payment not completed';
        this.statusMessage =
          fromQuery ||
          'This bill payment did not complete. Voucher or card holds are reversed when applicable—see transaction history.';
      } else {
        this.headline = 'Payment not completed';
        this.statusMessage = fromQuery || 'Something went wrong. You can try again or return to the dashboard.';
      }
      this.saveSnapshot();
      this.cdr.markForCheck();
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
      this.cdr.markForCheck();
      return;
    }

    /**
     * `reason=not_confirmed` without explicit status=failed: poll Mobikwik / payment stream.
     * When `status=failed` is present, we already handled it above — do not override with pending.
     */
    if (reason === 'not_confirmed' && this.orderRef) {
      if (this.bharatBillpayReceipt) {
        if (!this.gatewayLabel) {
          this.gatewayLabel = 'BBPS';
        }
        this.tone = 'pending';
        this.headline = 'Checking payment status';
        this.statusMessage =
          'Please wait while we confirm your bill payment with Mobikwik. Nothing is marked failed until we know the result.';
        this.saveSnapshot();
        queueMicrotask(() => this.startMobikwikStatusPoll());
        this.cdr.markForCheck();
        return;
      }
      this.tone = 'pending';
      this.headline = 'Checking payment status';
      this.statusMessage =
        'Please wait while we confirm your payment. Nothing is marked failed until we know the result.';
      this.saveSnapshot();
      queueMicrotask(() => this.tryRealtimeUpgrade());
      this.cdr.markForCheck();
      return;
    }

    this.tone = 'error';
    if (reason === 'incomplete') {
      this.headline = 'Payment incomplete';
      this.statusMessage =
        'You returned without completing payment. No amount was charged.';
    } else {
      this.headline = 'Payment not completed';
      this.statusMessage =
        'Something went wrong. You can try again or return to the dashboard.';
    }
    this.saveSnapshot();
    this.cdr.markForCheck();
  }

  viewInvoice() {
    if (!this.orderRef) return;
    const isBbps = this.bharatBillpayReceipt;
    const transaction = {
      id: this.orderRef,
      transactionId: this.orderRef,
      orderId: this.orderRef,
      amount: this.amount ?? 0,
      description: isBbps ? 'BBPS bill payment' : 'Voucher wallet top-up',
      gateway: (isBbps ? 'bbps' : 'cashfree') as PaymentGateway,
      timestamp: this.currentDate.toISOString(),
      status: 'success' as PaymentStatus,
      transactionType: (isBbps ? 'bbps' : 'voucher_purchase') as TransactionType,
      currency: 'INR',
      customer: { name: '', email: '', phone: '' },
    };
    this.router.navigate(['/payment/receipt', this.orderRef], {
      state: { transaction },
    });
  }

  retry() {
    if (this.bharatBillpayReceipt) {
      void this.router.navigate(['/bbps']);
    } else {
      void this.router.navigate(['/vouchers']);
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.realtimeSub?.unsubscribe();
    this.mobikwikPollSub?.unsubscribe();
  }

  private saveSnapshot(): void {
    this.store.setPaymentStatusSnapshot({
      tone: this.tone,
      orderRef: this.orderRef,
      gatewayRef: '',
      amount: this.amount,
      statusMessage: this.statusMessage,
      headline: this.headline,
      gatewayLabel: this.gatewayLabel,
      bharatBillpayReceipt: this.bharatBillpayReceipt,
    });
  }

  /** Poll Mobikwik until success/failed or timeout; then show receipt only on success. */
  private startMobikwikStatusPoll(): void {
    this.mobikwikPollSub?.unsubscribe();
    if (!this.orderRef) return;
    const ref = this.orderRef;
    this.mobikwikPollSub = race(
      timer(0, 3000).pipe(
        switchMap(() => this.bbps.getBillPaymentStatus(ref)),
        filter((r) => r.phase === 'success' || r.phase === 'failed'),
        take(1)
      ),
      timer(120_000).pipe(map(() => ({ phase: 'timeout' as const })))
    )
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (r) => {
          if (!r || (r as { phase?: string }).phase === 'timeout') {
            this.tone = 'warning';
            this.headline = 'Confirmation is taking longer';
            this.statusMessage =
              'We could not get a final Mobikwik status in time. Check Transaction History or try paying the bill again if needed.';
            this.saveSnapshot();
            this.cdr.markForCheck();
            return;
          }
          const row = r as { phase: string; message?: string };
          if (row.phase === 'success') {
            this.tone = 'success';
            this.headline = 'Payment confirmed';
            this.statusMessage =
              'Bharat Bill Pay (BBPS) bill payment. Mobikwik / biller network confirmed this transaction. Reference and amount are below.';
            this.currentDate = new Date();
            this.saveSnapshot();
            this.cdr.markForCheck();
            return;
          }
          if (row.phase === 'failed') {
            this.tone = 'error';
            this.headline = 'Bill payment not completed';
            this.statusMessage = (row.message || 'The biller reported that this payment did not complete.').slice(0, 280);
            this.saveSnapshot();
            this.cdr.markForCheck();
          }
        },
        error: () => {
          this.tone = 'warning';
          this.headline = 'Could not check status';
          this.statusMessage = 'Try again from Transaction History or BBPS.';
          this.saveSnapshot();
          this.cdr.markForCheck();
        },
      });
  }

  private tryRealtimeUpgrade(): void {
    if (!this.orderRef || this.tone === 'success' || this.bharatBillpayReceipt) {
      return;
    }
    this.realtimeSub?.unsubscribe();
    this.realtimeSub = this.realtime.watchPayment(this.orderRef, 45_000).subscribe((txn) => {
      if (!txn || txn.status !== 'success') return;
      this.tone = 'success';
      this.headline = 'Payment confirmed';
      this.statusMessage =
        'We received a successful confirmation from the payment gateway. Details are shown in the receipt below.';
      this.orderRef = txn.orderId || txn.transactionId || this.orderRef;
      this.amount = typeof txn.amount === 'number' ? txn.amount : this.amount;
      this.saveSnapshot();
      this.cdr.markForCheck();
    });
  }
}
