import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { NotificationService } from '../../../core/services/notification.service';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-fastag-confirm',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/fastag/recharge" class="back-link">
        <span class="material-icons">arrow_back</span> Back
      </a>
      <h1 class="feature-title">Confirm Recharge</h1>

      @if (!recharge) {
        <div class="empty-state card">
          <p>No recharge details. <a routerLink="/fastag/recharge">Start recharge</a></p>
        </div>
      } @else {
        <div class="confirm-card card">
          <h2>Recharge Summary</h2>
          <div class="detail-row"><span>Vehicle Number:</span><span>{{ recharge.vehicleNumber }}</span></div>
          <div class="detail-row highlight">
            <span>Recharge Amount:</span><span class="amount">₹{{ recharge.amount }}</span>
          </div>

          <button class="btn btn-primary btn-block" (click)="confirmRecharge()" [disabled]="loading">
            @if (loading) {
              <span class="spinner"></span> Processing...
            } @else {
              Proceed to Payment
            }
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 600px; margin: 0 auto; }
    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      color: var(--primary-600);
      text-decoration: none;
      font-weight: 500;
      margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .empty-state { padding: 2rem; text-align: center; }
    .confirm-card { padding: 2rem; }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light);

      &.highlight {
        background: var(--primary-50);
        padding: 1rem;
        border-radius: var(--radius-md);
        margin: 1rem 0;
        border-bottom: none;
      }
    }
    .amount { font-size: 1.5rem; font-weight: 700; color: var(--primary-700); }
    .btn-block { width: 100%; padding: 1rem; margin-top: 1rem; }
  `],
})
export class FastagConfirmComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);
  private notification = inject(NotificationService);
  private auth = inject(AuthService);

  recharge: { vehicleNumber: string; amount: number } | null = null;
  customer = { name: 'User', email: '', phone: '+919876543210' };
  loading = false;

  ngOnInit() {
    const state = this.router.getCurrentNavigation()?.extras?.state ?? history.state;
    this.recharge = state['recharge'] ?? null;
    if (!this.recharge) {
      this.recharge = null;
      return;
    }
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

  confirmRecharge() {
    if (!this.recharge) return;
    this.loading = true;
    this.api.createRechargeOrder({
      vehicleNumber: this.recharge.vehicleNumber,
      amount: Number(this.recharge.amount),
      customerName: this.customer.name,
      customerEmail: this.customer.email || 'user@example.com',
      customerPhone: this.customer.phone,
    }).subscribe({
      next: () => {
        this.notification.showSuccess('FASTag recharged successfully!');
        this.router.navigate(['/dashboard']);
      },
      error: () => {
        this.loading = false;
        this.notification.showError('Recharge failed');
      },
    });
  }
}
