import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule, APP_BASE_HREF } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { Transaction } from 'shared';
import { LottieFeedbackComponent } from '../../../shared/components/lottie-feedback/lottie-feedback.component';

@Component({
  selector: 'app-payment-receipt',
  standalone: true,
  imports: [CommonModule, RouterLink, LottieFeedbackComponent],
  template: `
    <div class="receipt-container">
      @if (loading) {
        <div class="spinner"></div>
      } @else if (transaction) {
        <div
          class="receipt-card card"
          [class.receipt-card--bbps]="showBbpsCompliance"
          [class.receipt-card--bbps-failed]="showBbpsCompliance && isFailedStatus"
        >
          <div class="receipt-card-surface">
            @if (showBbpsCompliance) {
              <header class="receipt-brands" role="banner">
                <div class="receipt-brand receipt-brand--left">
                  <img class="receipt-brand-logo receipt-brand-logo--parkpe" [src]="assetUrl('/assets/parkpe-logo.svg')" alt="ParkPe" />
                </div>
                <div class="receipt-brand receipt-brand--right">
                  <div class="bharat-billpay-lockup" role="img" aria-label="Bharat Bill Pay">
                    <img class="receipt-brand-logo receipt-brand-logo--bharat" [src]="assetUrl('/assets/bbps/bharat-connect-logo.png')" alt="" />
                    <span class="bharat-billpay-wordmark">Bharat Bill Pay</span>
                  </div>
                </div>
              </header>
            } @else {
              <header class="receipt-brands receipt-brands--solo">
                <img class="receipt-brand-logo receipt-brand-logo--parkpe" [src]="assetUrl('/assets/parkpe-logo.svg')" alt="ParkPe" />
              </header>
            }

            <div class="receipt-feedback-slot" [class.receipt-feedback-slot--bbps]="showBbpsCompliance">
              <app-lottie-feedback [type]="receiptFeedbackType" [message]="receiptFeedbackMessage" />
            </div>
            <div class="receipt-header">
              <h1>{{ receiptTitle }}</h1>
              <span class="material-icons receipt-header-icon" aria-hidden="true">receipt_long</span>
            </div>

            <div
              class="receipt-body"
              [class.receipt-body--bbps]="showBbpsCompliance"
              [style.--b-assured-wm]="showBbpsCompliance ? bAssuredWatermarkCssUrl : null"
            >
              <div class="receipt-body-inner">
            <div class="detail-row"><span>Transaction ID:</span><span>{{ transaction.transactionId }}</span></div>
            @if (transaction.customer.name) {
              <div class="detail-row"><span>Bill to:</span><span>{{ transaction.customer.name }}</span></div>
            }
            @if (transaction.customer.email) {
              <div class="detail-row subtle"><span>Email:</span><span>{{ transaction.customer.email }}</span></div>
            }
            @if (transaction.customer.phone) {
              <div class="detail-row subtle"><span>Mobile:</span><span>{{ transaction.customer.phone }}</span></div>
            }
            <div class="detail-row"><span>Order ID:</span><span>{{ transaction.orderId }}</span></div>
            <div class="detail-row"><span>Date:</span><span>{{ transaction.timestamp | date:'medium' }}</span></div>
            @if (transaction.transactionType) {
              <div class="detail-row"><span>Type:</span><span>{{ transaction.transactionType | titlecase }}</span></div>
            }
            <div class="detail-row"><span>Description:</span><span>{{ transaction.description }}</span></div>
            @if (transaction.status) {
              <div class="detail-row"><span>Status:</span><span>{{ transaction.status | titlecase }}</span></div>
            }
            <div class="detail-row"><span>Gateway:</span><span>{{ transaction.gateway | titlecase }}</span></div>
            @if (transaction.creditDebitLabel || transaction.transactionTypeDirection) {
              <div class="detail-row">
                <span>Credit / Debit:</span>
                <span>{{ transaction.creditDebitLabel || (transaction.transactionTypeDirection | titlecase) }}</span>
              </div>
            }
            <div class="detail-row highlight">
              <span>Amount Paid:</span><span class="amount">₹{{ transaction.amount }}</span>
            </div>
            @if (transaction.taxSnapshot) {
              <div class="tax-block" aria-label="Tax breakdown">
                <div class="detail-row subtle"><span>Taxable value</span><span>₹{{ transaction.taxSnapshot.taxableAmount | number:'1.2-2' }}</span></div>
                <div class="detail-row subtle"><span>CGST</span><span>₹{{ transaction.taxSnapshot.cgst | number:'1.2-2' }}</span></div>
                <div class="detail-row subtle"><span>SGST</span><span>₹{{ transaction.taxSnapshot.sgst | number:'1.2-2' }}</span></div>
                @if (transaction.taxSnapshot.igst > 0) {
                  <div class="detail-row subtle"><span>IGST</span><span>₹{{ transaction.taxSnapshot.igst | number:'1.2-2' }}</span></div>
                }
                <div class="detail-row subtle"><span>GST total</span><span>₹{{ transaction.taxSnapshot.gstTotal | number:'1.2-2' }}</span></div>
                @if (transaction.taxSnapshot.tdsAmount > 0) {
                  <div class="detail-row subtle"><span>TDS</span><span>₹{{ transaction.taxSnapshot.tdsAmount | number:'1.2-2' }}</span></div>
                }
                <div class="detail-row subtle"><span>Total (incl. tax)</span><span>₹{{ transaction.taxSnapshot.grandTotal | number:'1.2-2' }}</span></div>
                @if (transaction.taxSnapshot.sacOrHsn) {
                  <div class="detail-row subtle"><span>SAC / HSN</span><span>{{ transaction.taxSnapshot.sacOrHsn }}</span></div>
                }
              </div>
            }
              </div>
            </div>

          <div class="receipt-actions">
            <button class="btn btn-outline" type="button" (click)="printReceipt()">
              <span class="material-icons">print</span> Print
            </button>
            @if (transaction.status === 'success' && receiptDownloadId) {
              <button class="btn btn-outline" type="button" (click)="openReceiptDownload('html')">
                <span class="material-icons">download</span> HTML
              </button>
              <button class="btn btn-outline" type="button" (click)="openReceiptDownload('pdf')">
                <span class="material-icons">picture_as_pdf</span> PDF
              </button>
            }
            <button class="btn btn-primary" routerLink="/dashboard">Done</button>
          </div>
          @if (pdfUnavailable) {
            <p class="receipt-hint" role="status">PDF is not available on the server. Download HTML and use Print → Save as PDF.</p>
          }
          </div>
        </div>
      } @else {
        <div class="receipt-card card receipt-fallback">
          <header class="receipt-brands receipt-brands--solo">
            <img class="receipt-brand-logo receipt-brand-logo--parkpe" [src]="assetUrl('/assets/parkpe-logo.svg')" alt="ParkPe" />
          </header>
          <h1 class="receipt-header-fallback">Payment invoice</h1>
          <div class="receipt-body">
            <div class="detail-row"><span>Transaction ID:</span><span>{{ transactionId }}</span></div>
            @if (fallbackAmount != null) {
              <div class="detail-row highlight">
                <span>Amount Paid:</span><span class="amount">₹{{ fallbackAmount }}</span>
              </div>
            }
          </div>
          <p class="receipt-not-found">Full details will appear in payment history once synced.</p>
          <button class="btn btn-primary" routerLink="/dashboard">Back to Dashboard</button>
        </div>
      }
    </div>
  `,
  styles: [`
    .receipt-container {
      min-height: 100vh;
      padding: 1.5rem;
      display: flex;
      align-items: center;
      justify-content: center;
      background:
        radial-gradient(ellipse 120% 80% at 50% -20%, rgba(0, 74, 173, 0.08), transparent 55%),
        linear-gradient(180deg, var(--secondary-50, #f8fafc) 0%, var(--surface, #fff) 40%);
    }
    .receipt-card {
      position: relative;
      max-width: 560px;
      width: 100%;
      padding: 0;
      overflow: hidden;
      border-radius: var(--radius-lg, 16px);
      border: 1px solid color-mix(in srgb, var(--primary-500) 12%, var(--border, #e2e8f0));
      box-shadow:
        0 1px 2px rgba(0, 0, 0, 0.04),
        0 12px 40px rgba(0, 74, 173, 0.08);
      background: var(--surface, #fff);
    }
    .receipt-card--bbps .receipt-card-surface::before {
      content: '';
      position: absolute;
      left: 0;
      right: 0;
      top: 0;
      height: 4px;
      background: repeating-linear-gradient(
        90deg,
        var(--primary-400, #3b82f6),
        var(--primary-400, #3b82f6) 5px,
        transparent 5px,
        transparent 10px
      );
      opacity: 0.35;
      pointer-events: none;
    }
    .receipt-card--bbps-failed .receipt-card-surface::before {
      background: repeating-linear-gradient(
        90deg,
        #f87171,
        #f87171 5px,
        transparent 5px,
        transparent 10px
      );
      opacity: 0.45;
    }
    .receipt-card-surface {
      position: relative;
      z-index: 1;
      padding: 1.75rem 1.75rem 2rem;
    }
    .receipt-feedback-slot--bbps ::ng-deep .lottie-feedback {
      padding: 0.5rem 0.5rem 0.75rem;
    }
    .receipt-feedback-slot--bbps ::ng-deep .lottie-feedback .feedback-icon {
      width: 96px;
      height: 96px;
    }
    .receipt-feedback-slot--bbps ::ng-deep .lottie-feedback .feedback-icon .material-icons {
      font-size: 72px;
    }
    .receipt-feedback-slot--bbps ::ng-deep .lottie-feedback .feedback-message {
      font-size: 1.05rem;
      margin-top: 0.5rem;
    }
    .receipt-brands {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1.25rem;
      min-height: 56px;
      margin-bottom: 0.75rem;
      padding: 0.35rem 0.15rem 1rem;
      border-bottom: 1px solid color-mix(in srgb, var(--border) 80%, transparent);
    }
    .receipt-brands--solo {
      justify-content: flex-start;
      border-bottom: none;
      margin-bottom: 0.5rem;
      padding-bottom: 0;
    }
    .receipt-brand {
      flex: 0 1 auto;
      min-width: 0;
      display: flex;
      align-items: center;
    }
    .receipt-brand--left {
      justify-content: flex-start;
    }
    .receipt-brand--right {
      justify-content: flex-end;
      text-align: right;
    }
    .receipt-brand-logo {
      display: block;
      height: auto;
      object-fit: contain;
    }
    .receipt-brand-logo--parkpe {
      width: 158px;
      max-height: 52px;
    }
    .receipt-brands--solo .receipt-brand-logo--parkpe {
      width: 148px;
      max-height: 48px;
    }
    .bharat-billpay-lockup {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.35rem;
      max-width: 220px;
    }
    .receipt-brand-logo--bharat {
      width: 128px;
      max-height: 56px;
      object-fit: contain;
      object-position: right center;
    }
    .bharat-billpay-wordmark {
      font-size: 0.7rem;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: none;
      color: #1e3a5f;
      line-height: 1.2;
    }
    .receipt-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
      margin-bottom: 1.25rem;
      padding-bottom: 0.85rem;
      border-bottom: 2px solid color-mix(in srgb, var(--primary-500) 35%, transparent);

      h1 {
        margin: 0;
        font-size: 1.35rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        line-height: 1.25;
        color: var(--text-primary);
      }
    }
    .receipt-card--bbps-failed .receipt-header {
      border-bottom-color: color-mix(in srgb, #ef4444 45%, var(--border));
    }
    .receipt-header-icon {
      flex-shrink: 0;
      font-size: 2.25rem;
      color: color-mix(in srgb, var(--primary-500) 85%, #64748b);
      opacity: 0.9;
    }
    /* B Assured watermark – centered in the transaction-details block only */
    .receipt-body--bbps {
      position: relative;
      overflow: hidden;
      border-radius: var(--radius-md);
      min-height: 200px;
      margin-bottom: 1.75rem;
      padding: 0.65rem 0.75rem 0.5rem;
      background: linear-gradient(
        180deg,
        rgba(248, 250, 252, 0.9) 0%,
        rgba(255, 255, 255, 0.98) 100%
      );
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--primary-200) 25%, transparent);
    }
    .receipt-card--bbps-failed .receipt-body--bbps {
      box-shadow: inset 0 0 0 1px color-mix(in srgb, #fecaca 80%, transparent);
      background: linear-gradient(180deg, rgba(254, 242, 242, 0.5) 0%, rgba(255, 255, 255, 0.98) 100%);
    }
    /* B Assured: centered watermark via --b-assured-wm (set from TS for correct base href) */
    .receipt-body--bbps::before {
      content: '';
      position: absolute;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      background-image: var(--b-assured-wm, none);
      background-repeat: no-repeat;
      background-position: center center;
      background-size: min(88%, 340px) auto;
      opacity: 0.28;
      filter: grayscale(0.12);
    }
    .receipt-card--bbps-failed .receipt-body--bbps::before {
      opacity: 0.22;
    }
    .receipt-body-inner {
      position: relative;
      z-index: 1;
    }
    .receipt-body:not(.receipt-body--bbps) {
      margin-bottom: 1.75rem;
    }
    .detail-row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 1rem;
      padding: 0.65rem 0;
      border-bottom: 1px solid var(--border-light);

      &.highlight {
        background: linear-gradient(135deg, var(--primary-50) 0%, color-mix(in srgb, var(--primary-50) 70%, white) 100%);
        padding: 1rem 1rem;
        border-radius: var(--radius-md);
        margin-top: 0.75rem;
        border-bottom: none;
        box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--primary-200) 40%, transparent);
      }

      span:first-child { color: var(--text-secondary); font-size: 0.875rem; }
      span:last-child {
        font-weight: 600;
        font-family: ui-monospace, 'Cascadia Code', monospace;
        font-size: 0.9rem;
        text-align: right;
        word-break: break-word;
      }
      &.subtle span:first-child { font-size: 0.8125rem; }
      &.subtle span:last-child { font-weight: 500; font-size: 0.875rem; }
    }
    .tax-block {
      margin-top: 0.5rem;
      padding-top: 0.5rem;
      border-top: 1px dashed var(--border-light);
    }
    .amount { font-size: 1.5rem; color: var(--primary-700); font-family: inherit; font-weight: 700; }
    .receipt-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      justify-content: center;
      padding-top: 0.25rem;

      button { display: flex; align-items: center; gap: 0.5rem; }
    }
    .receipt-hint {
      margin-top: 1rem;
      text-align: center;
      font-size: 0.875rem;
      color: var(--text-muted);
      max-width: 28rem;
      margin-left: auto;
      margin-right: auto;
    }

    .receipt-fallback .receipt-header-fallback { font-size: 1.25rem; margin-bottom: 1rem; }
    .receipt-not-found { font-size: 0.875rem; color: var(--text-muted); margin: 1rem 0; }
    .receipt-fallback {
      padding: 1.75rem;
    }
    @media print {
      .receipt-container {
        background: #fff;
        padding: 0;
      }
      .receipt-card {
        box-shadow: none;
        border: none;
        max-width: 100%;
      }
      .receipt-body--bbps::before {
        opacity: 0.12;
      }
      .receipt-actions { display: none; }
    }
    @media (max-width: 480px) {
      .receipt-brand-logo--parkpe { width: 128px; max-height: 44px; }
      .receipt-brand-logo--bharat { width: 108px; max-height: 46px; }
      .bharat-billpay-wordmark { font-size: 0.62rem; }
      .receipt-header h1 { font-size: 1.2rem; }
    }
    .receipt-card--bbps-failed .receipt-body--bbps .detail-row.highlight {
      background: linear-gradient(135deg, #fef2f2 0%, #ffffff 100%);
      box-shadow: inset 0 0 0 1px color-mix(in srgb, #fecaca 70%, transparent);
    }
    .receipt-card--bbps-failed .receipt-body--bbps .amount {
      color: #b91c1c;
    }
  `],
})
export class PaymentReceiptComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private paymentService = inject(PaymentGatewayService);
  private cdr = inject(ChangeDetectorRef);
  private readonly appBaseHref = inject(APP_BASE_HREF);

  transactionId = '';
  transaction: Transaction | null = null;
  loading = true;
  fallbackAmount: number | null = null;
  pdfUnavailable = false;

  /** Resolves `/assets/...` against `<base href>` so images work on any deploy path. */
  assetUrl(path: string): string {
    const p = path.startsWith('/') ? path : `/${path}`;
    const base = (this.appBaseHref || '/').replace(/\/$/, '');
    if (!base) return p;
    return `${base}${p}`;
  }

  /** CSS `url("...")` for B Assured watermark layer. */
  get bAssuredWatermarkCssUrl(): string {
    const u = this.assetUrl('/assets/bbps/b-assured-logo.png');
    return `url(${JSON.stringify(u)})`;
  }

  /** BBPS payment did not succeed (for red-tint receipt). */
  get isFailedStatus(): boolean {
    return (this.transaction?.status ?? '').toLowerCase() === 'failed';
  }

  /** NPCI B Assured / Bharat Billpay marks apply only to BBPS bill payments. */
  get showBbpsCompliance(): boolean {
    const t = (this.transaction?.transactionType ?? '').toLowerCase();
    const g = (this.transaction?.gateway ?? '').toLowerCase();
    if (t === 'bbps' || g === 'bbps') return true;
    const desc = (this.transaction?.description ?? '').toLowerCase();
    return desc.includes('bbps');
  }

  get receiptTitle(): string {
    return this.showBbpsCompliance ? 'BBPS payment invoice' : 'Tax invoice / receipt';
  }

  /** Receipt heading and icon by actual transaction status (success / failed / pending). */
  get receiptFeedbackType(): 'success' | 'error' | 'pending' {
    const s = (this.transaction?.status ?? '').toLowerCase();
    if (s === 'success') return 'success';
    if (s === 'failed') return 'error';
    return 'pending';
  }
  get receiptFeedbackMessage(): string {
    const s = (this.transaction?.status ?? '').toLowerCase();
    if (s === 'success') return 'Payment successful';
    if (s === 'failed') return 'Payment failed';
    return 'Payment pending';
  }

  /** Prefer loaded transaction ids so download works when opened via router state without route param. */
  get receiptDownloadId(): string {
    return (
      (this.transaction?.transactionId || this.transaction?.orderId || this.transactionId || '') as string
    ).trim();
  }

  /** Defer state update to next frame to avoid NG0100 (ExpressionChangedAfterItHasBeenCheckedError). */
  private setState(transaction: Transaction | null, loading: boolean) {
    requestAnimationFrame(() => {
      this.transaction = transaction;
      this.loading = loading;
      this.cdr.detectChanges();
    });
  }

  ngOnInit() {
    this.pdfUnavailable = false;
    this.transactionId = this.route.snapshot.params['transactionId'] ?? '';
    const q = this.route.snapshot.queryParams;
    const amt = q['amount'];
    this.fallbackAmount = amt != null && amt !== '' ? Number(amt) : null;

    const state = history.state as { transaction?: Transaction } | null;
    if (!this.transactionId) {
      this.setState(state?.transaction ?? null, false);
      return;
    }

    this.paymentService.getTransaction(this.transactionId).subscribe({
      next: (data) => this.setState(data, false),
      error: () => this.setState(state?.transaction ?? null, false),
    });
  }

  printReceipt() {
    window.print();
  }

  openReceiptDownload(format: 'html' | 'pdf'): void {
    const id = this.receiptDownloadId;
    if (!id) return;
    this.pdfUnavailable = false;
    const opts =
      format === 'pdf' ? { format: 'pdf' as const } : { attachment: true as const };
    this.paymentService.downloadReceipt(id, opts).subscribe({
      next: (data: Blob | string) => {
        if (typeof data === 'string') {
          window.open(data, '_blank', 'noopener,noreferrer');
          return;
        }
        const url = URL.createObjectURL(data);
        window.open(url, '_blank', 'noopener,noreferrer');
        setTimeout(() => URL.revokeObjectURL(url), 120000);
      },
      error: (err: { status?: number }) => {
        if (format === 'pdf' && err?.status === 415) {
          this.pdfUnavailable = true;
          this.cdr.markForCheck();
        }
      },
    });
  }
}
