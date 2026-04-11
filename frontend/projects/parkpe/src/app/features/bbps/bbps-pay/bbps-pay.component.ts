import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { NotificationService } from '../../../core/services/notification.service';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';

@Component({
  selector: 'app-bbps-pay',
  standalone: true,
  imports: [CommonModule, StepIndicatorComponent],
  template: `
    <div class="feature-container">
      <app-step-indicator [steps]="stepLabels" [currentStep]="4" />
      <h1 class="feature-title">Payment</h1>
      <div class="payment-summary card">
        <h2>Bill Payment Summary</h2>
        <div class="summary-row"><span>Amount:</span><span class="amount">₹1,250</span></div>
        <button class="btn btn-primary btn-block" (click)="initiatePayment()">
          Pay Now
        </button>
      </div>
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 600px; margin: 0 auto; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .payment-summary { padding: 2rem; }
    .summary-row {
      display: flex;
      justify-content: space-between;
      padding: 1rem;
      background: var(--primary-50);
      border-radius: var(--radius-md);
      margin-bottom: 1.5rem;
    }
    .amount { font-size: 1.75rem; font-weight: 700; color: var(--primary-700); }
    .btn-block { width: 100%; padding: 1rem; }
  `],
})
export class BBPSPayComponent {
  readonly stepLabels = ['Category', 'Operator', 'Fetch Bill', 'Pay'];
  private paymentService = inject(PaymentGatewayService);
  private router = inject(Router);
  private notification = inject(NotificationService);

  initiatePayment() {
    this.notification.showInfo('Redirecting to payment gateway...');
    // TODO: Implement actual payment flow
    setTimeout(() => {
      this.router.navigate(['/payment/status'], { 
        queryParams: { status: 'success' } 
      });
    }, 1000);
  }
}
