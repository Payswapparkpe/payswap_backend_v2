import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

@Component({
  selector: 'app-payment-status',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="status-container">
      @if (status === 'success') {
        <div class="status-card success card scale-in">
          <img class="b-assured-logo" src="assets/bbps/b-assured-logo.png" alt="B Assured" />
          <div class="status-icon">
            <span class="material-icons">check_circle</span>
          </div>
          <h1 class="status-title">Payment Successful!</h1>
          <p class="status-message">Your payment has been processed successfully</p>
          
          <div class="status-details">
            @if (balance != null && balance !== '') {
              <div class="detail-item highlight"><span>Voucher balance:</span><span>₹{{ balance }}</span></div>
            }
            <div class="detail-item"><span>Transaction ID:</span><span>{{ transactionId || 'TXN123456' }}</span></div>
            <div class="detail-item"><span>Amount:</span><span>{{ amount ? ('₹' + amount) : '₹500' }}</span></div>
            <div class="detail-item"><span>Date:</span><span>{{ currentDate | date:'short' }}</span></div>
          </div>

          <div class="status-actions">
            @if (transactionId) {
              <button class="btn btn-outline" (click)="viewInvoice()">
                View Invoice
              </button>
            }
            <button class="btn btn-primary" routerLink="/dashboard">Back to Dashboard</button>
            <a class="btn btn-outline" routerLink="/vouchers">Vouchers</a>
            <a class="btn btn-outline" routerLink="/bbps">Pay another bill</a>
            <button class="btn btn-outline" routerLink="/payment/history">View History</button>
          </div>
        </div>
      } @else {
        <div class="status-card error card scale-in">
          <div class="status-icon error">
            <span class="material-icons">error</span>
          </div>
          <h1 class="status-title">Payment not completed</h1>
          <p class="status-message">{{ statusMessage }}</p>

          <div class="status-actions">
            <button class="btn btn-primary" (click)="retry()">Try again</button>
            <a class="btn btn-outline" routerLink="/vouchers">Vouchers</a>
            <button class="btn btn-outline" routerLink="/dashboard">Back to Dashboard</button>
          </div>
        </div>
      }
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
      max-width: 500px;
      padding: 3rem 2rem;
      text-align: center;

      /* B Assured – Brand Book: mandatory on Payment Successful; clear space = half B mnemonic width */
      .b-assured-logo {
        display: block;
        height: 48px;
        width: auto;
        max-width: 180px;
        margin: 0 auto 1rem;
        padding: 12px; /* clear space around logo (half B width) */
        object-fit: contain;
      }
      &.success .status-icon .material-icons { color: var(--success); }
      &.error .status-icon .material-icons { color: var(--error); }
    }
    .status-icon .material-icons {
      font-size: 100px;
      animation: scaleIn 0.5s ease;
    }
    .status-title {
      font-size: 2rem;
      font-weight: 700;
      margin: 1rem 0;
      color: var(--text-primary);
    }
    .status-message {
      color: var(--text-secondary);
      margin-bottom: 2rem;
    }
    .status-details {
      background: var(--surface);
      padding: 1.5rem;
      border-radius: var(--radius-md);
      margin-bottom: 2rem;
      text-align: left;
    }
    .detail-item {
      display: flex;
      justify-content: space-between;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--border-light);

      &:last-child { border-bottom: none; }
      
      span:last-child { font-weight: 600; }
      &.highlight span:last-child { color: var(--primary-700); }
    }
    .status-actions {
      display: flex;
      gap: 1rem;
      justify-content: center;
      flex-wrap: wrap;
    }
  `],
})
export class PaymentStatusComponent implements OnInit {
  status: 'success' | 'failed' = 'success';
  currentDate = new Date();
  transactionId = '';
  amount: number | null = null;
  balance: string | null = null;
  statusMessage = '';

  constructor(private route: ActivatedRoute, private router: Router) {}

  ngOnInit() {
    const q = this.route.snapshot.queryParams;
    this.status = q['status'] === 'success' ? 'success' : 'failed';
    this.transactionId = q['transactionId'] || q['orderId'] || '';
    const amt = q['amount'];
    this.amount = amt != null && amt !== '' ? Number(amt) : null;
    const bal = q['balance'];
    this.balance = bal != null && bal !== '' ? String(bal) : null;
    const reason = q['reason'];
    if (this.status === 'failed') {
      this.statusMessage = reason === 'incomplete'
        ? 'You returned without completing payment. No amount was charged.'
        : reason === 'not_confirmed'
          ? 'Payment could not be confirmed. If you paid, your voucher balance will update shortly.'
          : reason === 'voucher_delayed'
            ? (this.transactionId
                ? `Your payment was successful but the voucher could not be added right now. We'll add it shortly. Order ID: ${this.transactionId}. Contact support if it doesn't appear.`
                : `Your payment was successful but the voucher could not be added right now. We'll add it shortly. Contact support with your payment details if it doesn't appear.`)
            : 'Something went wrong. You can try again or go back to dashboard.';
    }
  }

  viewInvoice() {
    if (!this.transactionId) return;
    const transaction = {
      id: this.transactionId,
      transactionId: this.transactionId,
      orderId: this.transactionId,
      amount: this.amount ?? 0,
      description: 'BBPS Bill Payment',
      gateway: 'bbps' as const,
      timestamp: this.currentDate.toISOString(),
      status: 'success' as const,
      transactionType: 'bbps' as const,
      currency: 'INR',
      customer: { name: '', email: '', phone: '' },
    };
    this.router.navigate(['/payment/receipt', this.transactionId], { state: { transaction } });
  }

  retry() {
    this.router.navigate(['/vouchers']);
  }
}
