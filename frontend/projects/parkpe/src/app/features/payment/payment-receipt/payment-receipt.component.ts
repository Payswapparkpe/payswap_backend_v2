import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
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
        <div class="receipt-card card">
          @if (showBbpsCompliance) {
            <img class="b-assured-logo" src="assets/bbps/b-assured-logo.png" alt="B Assured" />
          } @else {
            <div class="parkpe-mark" aria-hidden="true">ParkPe</div>
          }
          <app-lottie-feedback [type]="receiptFeedbackType" [message]="receiptFeedbackMessage" />
          <div class="receipt-header">
            <h1>{{ receiptTitle }}</h1>
            <span class="material-icons">receipt</span>
          </div>

          <div class="receipt-body">
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
            @if (transaction.transactionTypeDirection) {
              <div class="detail-row"><span>Transaction:</span><span>{{ transaction.transactionTypeDirection | titlecase }}</span></div>
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
      } @else {
        <div class="receipt-card card receipt-fallback">
          <div class="parkpe-mark" aria-hidden="true">ParkPe</div>
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
      padding: 2rem;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--surface);
    }
    .receipt-card {
      max-width: 600px;
      width: 100%;
      padding: 2.5rem;
    }
    .parkpe-mark {
      text-align: center;
      font-weight: 800;
      font-size: 1.125rem;
      letter-spacing: 0.06em;
      color: var(--primary-700);
      margin: 0 auto 1rem;
    }
    /* B Assured – BBPS bill payments only (NPCI brand book). */
    .b-assured-logo {
      display: block;
      height: 48px;
      width: auto;
      max-width: 180px;
      margin: 0 auto 1.25rem;
      padding: 12px;
      object-fit: contain;
    }
    .receipt-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      padding-bottom: 1rem;
      border-bottom: 2px solid var(--primary-500);

      h1 { font-size: 1.75rem; font-weight: 700; }
      .material-icons { font-size: 40px; color: var(--primary-500); }
    }
    .receipt-body { margin-bottom: 2rem; }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light);

      &.highlight {
        background: var(--primary-50);
        padding: 1rem;
        border-radius: var(--radius-md);
        margin-top: 1rem;
        border-bottom: none;
      }

      span:first-child { color: var(--text-secondary); }
      span:last-child { font-weight: 600; font-family: monospace; }
      &.subtle span:first-child { font-size: 0.875rem; }
      &.subtle span:last-child { font-weight: 500; font-size: 0.9rem; }
    }
    .tax-block {
      margin-top: 0.5rem;
      padding-top: 0.5rem;
      border-top: 1px dashed var(--border-light);
    }
    .amount { font-size: 1.75rem; color: var(--primary-700); font-family: inherit; }
    .receipt-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      justify-content: center;

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
    @media print {
      .receipt-actions { display: none; }
    }
  `],
})
export class PaymentReceiptComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private paymentService = inject(PaymentGatewayService);
  private cdr = inject(ChangeDetectorRef);

  transactionId = '';
  transaction: Transaction | null = null;
  loading = true;
  fallbackAmount: number | null = null;
  pdfUnavailable = false;

  /** NPCI B Assured / Bharat Billpay marks apply only to BBPS bill payments. */
  get showBbpsCompliance(): boolean {
    return (this.transaction?.transactionType ?? '').toLowerCase() === 'bbps';
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
