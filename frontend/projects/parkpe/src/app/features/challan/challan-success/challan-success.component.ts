import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { ChallanPaymentResponse } from '../../../core/models/challan.model';

@Component({
  selector: 'app-challan-success',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <h1>Payment Successful</h1>
      @if (payment) {
        <div class="card">
          <p><strong>Receipt:</strong> {{ payment.receiptNumber }}</p>
          <p><strong>Txn:</strong> {{ payment.transactionId }}</p>
          <p><strong>Amount:</strong> ₹{{ payment.amount }}</p>
          <button class="btn btn-primary" (click)="openReceipt()">View Receipt</button>
        </div>
      }
      <a routerLink="/challan/history" class="btn btn-outline">Go to History</a>
    </div>
  `,
})
export class ChallanSuccessComponent {
  private router = inject(Router);
  payment = ((this.router.getCurrentNavigation()?.extras?.state ?? window.history.state)?.payment ?? null) as ChallanPaymentResponse | null;

  openReceipt(): void {
    if (!this.payment?.challanId) return;
    this.router.navigate(['/challan/receipt', this.payment.challanId]);
  }
}
