import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { NotificationService } from '../../../core/services/notification.service';
import { AuthService } from '../../../core/services/auth.service';
import { Challan } from '../../../core/models/challan.model';

@Component({
  selector: 'app-challan-pay',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/challan" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Challan
      </a>
      <h1 class="feature-title">Pay Challan</h1>

      @if (loading && !challan) {
        <div class="loading-state"><div class="spinner"></div></div>
      } @else if (challan) {
        <div class="payment-card card">
          <h2>Payment Summary</h2>
          <div class="detail-row"><span>Challan Number:</span><span>{{ challan.challanNumber }}</span></div>
          <div class="detail-row"><span>Vehicle:</span><span>{{ challan.vehicleNumber }}</span></div>
          <div class="detail-row"><span>Offence:</span><span>{{ challan.offence }}</span></div>
          <div class="detail-row highlight">
            <span>Amount to Pay:</span><span class="amount">₹{{ challan.totalAmount }}</span>
          </div>

          <button class="btn btn-primary btn-block" (click)="initiatePayment()" [disabled]="paying">
            @if (paying) {
              <span class="spinner"></span> Processing...
            } @else {
              Proceed to Payment
            }
          </button>
        </div>
      } @else {
        <div class="empty-state card">
          <p>Challan not found. <a routerLink="/challan">Back to list</a></p>
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 600px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .loading-state { display: flex; justify-content: center; padding: 3rem; }
    .empty-state { padding: 2rem; text-align: center; }
    .payment-card { padding: 2rem; }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light);

      &.highlight {
        background: var(--error, #ffebee);
        padding: 1rem;
        border-radius: var(--radius-md);
        margin: 1rem 0;
        border-bottom: none;
      }
    }
    .amount { font-size: 1.5rem; font-weight: 700; color: var(--error); }
    .btn-block { width: 100%; padding: 1rem; margin-top: 1rem; }
  `],
})
export class ChallanPayComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private notification = inject(NotificationService);
  private auth = inject(AuthService);

  challanId = '';
  challan: Challan | null = null;
  customer = { name: 'User', email: '', phone: '+919876543210' };
  loading = true;
  paying = false;

  private apiErrorMessage(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      const detail = (err.error?.detail ?? err.error?.message ?? '').toString().trim();
      if (detail) return detail;
    }
    return 'Payment failed';
  }

  ngOnInit() {
    this.challanId = this.route.snapshot.params['id'];
    this.api.getChallan(this.challanId).subscribe({
      next: (c) => {
        this.challan = c;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
    this.auth.getProfile().subscribe({
      next: (user) => {
        this.customer = {
          name: user.name ?? 'User',
          email: user.email ?? '',
          phone: user.phone ?? this.customer.phone,
        };
      },
    });
  }

  initiatePayment() {
    if (!this.challan) return;
    this.router.navigate(['/challan/pay', this.challanId, 'methods']);
  }
}
