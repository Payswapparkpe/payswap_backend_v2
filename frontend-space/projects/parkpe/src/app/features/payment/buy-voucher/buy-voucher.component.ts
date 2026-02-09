import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { AuthService } from '../../../core/services/auth.service';
import { GatewayConfig, PaymentGateway } from '../../../core/models/payment.model';

@Component({
  selector: 'app-buy-voucher',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="feature-title">Buy Voucher</h1>
      <p class="feature-desc">Add balance to your voucher. Use it to pay bills (e.g. BBPS) without Card/UPI.</p>

      <form [formGroup]="form" (ngSubmit)="submit()" class="buy-voucher-form">
        <div class="form-group">
          <label>Amount (₹)</label>
          <input type="number" class="form-control" formControlName="amount" placeholder="e.g. 500" min="1" step="1" />
          @if (form.get('amount')?.invalid && form.get('amount')?.touched) {
            <span class="error">Enter a valid amount (min ₹1)</span>
          }
        </div>
        <div class="form-group">
          <label>Payment gateway</label>
          @if (loadingGateways()) {
            <p>Loading gateways...</p>
          } @else {
            <div class="gateways-list">
              @for (g of gateways(); track g.name) {
                <label class="gateway-option">
                  <input type="radio" formControlName="gateway" [value]="g.name" />
                  <span>{{ g.displayName }}</span>
                </label>
              }
            </div>
            @if (gateways().length === 0) {
              <p class="hint">{{ needsLogin() ? 'Please log in to add voucher balance.' : 'No gateway enabled. Ask admin to enable Cashfree for voucher purchase.' }}</p>
            }
          }
        </div>
        <button type="submit" class="btn btn-primary btn-block" [disabled]="form.invalid || processing() || gateways().length === 0">
          @if (processing()) {
            <span class="spinner"></span> Processing...
          } @else {
            Pay ₹{{ form.get('amount')?.value || 0 }} &amp; Add to Voucher
          }
        </button>
      </form>
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 520px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; }
    .feature-desc { color: var(--text-secondary); margin-bottom: 2rem; }
    .buy-voucher-form .form-group { margin-bottom: 1.5rem; }
    .buy-voucher-form label { display: block; font-weight: 600; margin-bottom: 0.5rem; }
    .form-control { width: 100%; padding: 0.75rem; border: 1px solid var(--border-light); border-radius: 8px; }
    .error { color: var(--error-600); font-size: 0.875rem; }
    .gateways-list { display: flex; flex-direction: column; gap: 0.5rem; }
    .gateway-option { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }
    .gateway-option input { margin: 0; }
    .hint { color: var(--text-secondary); font-size: 0.875rem; }
    .btn-block { width: 100%; padding: 1rem; margin-top: 0.5rem; }
  `],
})
export class BuyVoucherComponent implements OnInit {
  private paymentService = inject(PaymentGatewayService);
  private authService = inject(AuthService);
  private fb = inject(FormBuilder);
  private router = inject(Router);

  form: FormGroup = this.fb.group({
    amount: [500, [Validators.required, Validators.min(1)]],
    gateway: [null as PaymentGateway | null, Validators.required],
  });
  gateways = signal<GatewayConfig[]>([]);
  loadingGateways = signal(true);
  processing = signal(false);
  /** True when user is not logged in (no token), so we skip gateways API and show login hint. */
  needsLogin = signal(false);

  ngOnInit() {
    if (!this.authService.getToken()) {
      this.needsLogin.set(true);
      this.loadingGateways.set(false);
      return;
    }
    this.paymentService.getAvailableGateways().subscribe({
      next: (list) => {
        this.gateways.set(list ?? []);
        if (list?.length) {
          this.form.patchValue({ gateway: list[0].name });
        }
        this.loadingGateways.set(false);
      },
      error: () => {
        this.loadingGateways.set(false);
      },
    });
  }

  submit() {
    if (this.form.invalid || this.processing()) return;
    const amount = Number(this.form.get('amount')?.value);
    const gateway = this.form.get('gateway')?.value as PaymentGateway;
    this.processing.set(true);
    const request = {
      amount,
      currency: 'INR',
      orderId: '',
      orderDescription: 'Voucher purchase',
      transactionType: 'other' as const,
      customer: { name: 'Customer', email: '', phone: '' },
    };
    this.paymentService.initiatePayment(gateway, request).subscribe({
      next: (res) => {
        this.processing.set(false);
        const balance = res?.['balance'] ?? res?.['metadata']?.['balance'] ?? '';
        this.router.navigate(['/payment/status'], {
          queryParams: { status: 'success', balance: balance || undefined },
        });
      },
      error: () => {
        this.processing.set(false);
      },
    });
  }
}
