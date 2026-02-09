import { Component, inject, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { Transaction } from '../../../core/models/payment.model';
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
          <img class="b-assured-logo" src="assets/bbps/b-assured-logo.png" alt="B Assured" />
          <app-lottie-feedback type="success" message="Payment successful" />
          <div class="receipt-header">
            <h1>Payment Invoice</h1>
            <span class="material-icons">receipt</span>
          </div>

          <div class="receipt-body">
            <div class="detail-row"><span>Transaction ID:</span><span>{{ transaction.transactionId }}</span></div>
            <div class="detail-row"><span>Order ID:</span><span>{{ transaction.orderId }}</span></div>
            <div class="detail-row"><span>Date:</span><span>{{ transaction.timestamp | date:'medium' }}</span></div>
            <div class="detail-row"><span>Description:</span><span>{{ transaction.description }}</span></div>
            <div class="detail-row"><span>Gateway:</span><span>{{ transaction.gateway | titlecase }}</span></div>
            <div class="detail-row highlight">
              <span>Amount Paid:</span><span class="amount">₹{{ transaction.amount }}</span>
            </div>
          </div>

          <div class="receipt-actions">
            <button class="btn btn-outline" type="button" (click)="printReceipt()">
              <span class="material-icons">print</span> Print Receipt
            </button>
            <button class="btn btn-primary" routerLink="/dashboard">Done</button>
          </div>
        </div>
      } @else {
        <div class="receipt-card card receipt-fallback">
          <img class="b-assured-logo" src="assets/bbps/b-assured-logo.png" alt="B Assured" />
          <h1 class="receipt-header-fallback">Payment Invoice</h1>
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
    /* B Assured – Brand Book: mandatory on receipt; clear space = half B mnemonic width */
    .b-assured-logo {
      display: block;
      height: 48px;
      width: auto;
      max-width: 180px;
      margin: 0 auto 1.25rem;
      padding: 12px; /* clear space around logo */
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
    }
    .amount { font-size: 1.75rem; color: var(--primary-700); font-family: inherit; }
    .receipt-actions {
      display: flex;
      gap: 1rem;
      justify-content: center;

      button { display: flex; align-items: center; gap: 0.5rem; }
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

  /** Defer state update to next frame to avoid NG0100 (ExpressionChangedAfterItHasBeenCheckedError). */
  private setState(transaction: Transaction | null, loading: boolean) {
    requestAnimationFrame(() => {
      this.transaction = transaction;
      this.loading = loading;
      this.cdr.detectChanges();
    });
  }

  ngOnInit() {
    this.transactionId = this.route.snapshot.params['transactionId'] ?? '';
    const q = this.route.snapshot.queryParams;
    const amt = q['amount'];
    this.fallbackAmount = amt != null && amt !== '' ? Number(amt) : null;

    const state = history.state as { transaction?: Transaction } | null;
    if (state?.transaction) {
      this.setState(state.transaction, false);
      return;
    }

    if (!this.transactionId) {
      this.setState(null, false);
      return;
    }

    this.paymentService.getTransaction(this.transactionId).subscribe({
      next: (data) => this.setState(data, false),
      error: () => this.setState(null, false),
    });
  }

  printReceipt() {
    window.print();
  }
}
