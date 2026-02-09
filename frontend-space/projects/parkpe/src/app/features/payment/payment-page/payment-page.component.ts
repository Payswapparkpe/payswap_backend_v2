import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { GatewayConfig, PaymentGateway } from '../../../core/models/payment.model';

@Component({
  selector: 'app-payment-page',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="feature-title">Select Payment Method</h1>

      <div class="payment-summary card">
        <h2>Payment Summary</h2>
        <div class="summary-row"><span>Amount:</span><span class="amount">₹500</span></div>
        <div class="summary-row"><span>Description:</span><span>Parking Payment</span></div>
      </div>

      <div class="gateways-section">
        <h3 class="section-subtitle">Choose Payment Gateway</h3>
        @if (loading) {
          <div class="spinner"></div>
        } @else {
          <div class="gateways-list">
            @for (gateway of gateways; track gateway.name) {
              <div
                class="gateway-card card"
                [class.selected]="selectedGateway === gateway.name"
                (click)="selectGateway(gateway.name)"
              >
                <div class="gateway-info">
                  <h4>{{ gateway.displayName }}</h4>
                  <p>{{ gateway.description }}</p>
                </div>
                @if (selectedGateway === gateway.name) {
                  <span class="material-icons check">check_circle</span>
                }
              </div>
            }
          </div>
        }
      </div>

      <button 
        class="btn btn-primary btn-block" 
        [disabled]="!selectedGateway || processing"
        (click)="processPayment()"
      >
        @if (processing) {
          <span class="spinner"></span> Processing...
        } @else {
          Pay ₹500
        }
      </button>
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 700px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .payment-summary { padding: 2rem; margin-bottom: 2rem; }
    .summary-row {
      display: flex;
      justify-content: space-between;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light);
    }
    .amount { font-size: 1.75rem; font-weight: 700; color: var(--primary-700); }
    .section-subtitle { font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem; }
    .gateways-list { display: flex; flex-direction: column; gap: 1rem; margin-bottom: 2rem; }
    .gateway-card {
      padding: 1.5rem;
      cursor: pointer;
      border: 2px solid transparent;
      transition: all 0.2s ease;
      display: flex;
      justify-content: space-between;
      align-items: center;

      &:hover {
        border-color: var(--primary-300);
      }

      &.selected {
        border-color: var(--primary-500);
        background: var(--primary-50);
      }

      h4 { font-size: 1.125rem; font-weight: 600; margin-bottom: 0.25rem; }
      p { font-size: 0.875rem; color: var(--text-secondary); }

      .check { color: var(--primary-600); font-size: 28px; }
    }
    .btn-block { width: 100%; padding: 1rem; font-size: 1.125rem; }
  `],
})
export class PaymentPageComponent implements OnInit {
  private paymentService = inject(PaymentGatewayService);
  private router = inject(Router);

  gateways: GatewayConfig[] = [];
  selectedGateway: PaymentGateway | null = null;
  loading = true;
  processing = false;

  ngOnInit() {
    this.paymentService.getAvailableGateways().subscribe({
      next: (data) => {
        this.gateways = data;
        this.loading = false;
      },
    });
  }

  selectGateway(gateway: PaymentGateway) {
    this.selectedGateway = gateway;
  }

  processPayment() {
    if (!this.selectedGateway) return;

    this.processing = true;
    // TODO: Implement actual payment initiation
    setTimeout(() => {
      this.router.navigate(['/payment/status'], { queryParams: { status: 'success' } });
    }, 1500);
  }
}
