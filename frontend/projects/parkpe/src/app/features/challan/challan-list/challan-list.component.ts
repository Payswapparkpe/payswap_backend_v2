import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { Challan } from '../../../core/models/challan.model';

@Component({
  selector: 'app-challan-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="feature-title">Your Challans</h1>

      @if (challans.length === 0) {
        <div class="empty-state card">
          <span class="material-icons">receipt_long</span>
          <h3>No Challans Found</h3>
          <p>Search by vehicle number to find pending traffic challans.</p>
          <a routerLink="/challan/search" class="btn btn-primary">Search Challans</a>
        </div>
      } @else {
        <div class="challans-list">
          @for (challan of challans; track challan.id) {
            <div class="challan-card card" [routerLink]="['/challan/detail', challan.id]">
              <div class="challan-header">
                <h3>{{ challan.challanNumber }}</h3>
                <span class="status-badge" [class.pending]="challan.status === 'pending'">
                  {{ challan.status | titlecase }}
                </span>
              </div>
              <p class="challan-offence">{{ challan.offence }}</p>
              <div class="challan-details">
                <span><span class="material-icons">directions_car</span> {{ challan.vehicleNumber }}</span>
                <span><span class="material-icons">location_on</span> {{ challan.location }}</span>
              </div>
              <div class="challan-footer">
                <span class="amount">₹{{ challan.totalAmount }}</span>
                <button class="btn btn-primary btn-sm">Pay Now</button>
              </div>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 800px; margin: 0 auto; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .empty-state {
      text-align: center;
      padding: 4rem 2rem;

      .material-icons { font-size: 80px; color: var(--text-muted); margin-bottom: 1rem; }
      h3 { font-size: 1.5rem; margin-bottom: 0.5rem; }
      p { color: var(--text-secondary); margin-bottom: 1.5rem; }
    }
    .challans-list { display: flex; flex-direction: column; gap: 1rem; }
    .challan-card {
      padding: 1.5rem;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover { box-shadow: var(--shadow-lg); }
    }
    .challan-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;

      h3 { font-size: 1.125rem; font-weight: 600; }
    }
    .status-badge {
      padding: 0.25rem 0.75rem;
      border-radius: var(--radius-full);
      font-size: 0.75rem;
      font-weight: 600;
      background: var(--success);
      color: white;

      &.pending { background: var(--warning); }
    }
    .challan-offence { color: var(--text-secondary); margin-bottom: 1rem; }
    .challan-details {
      display: flex;
      gap: 1.5rem;
      margin-bottom: 1rem;
      font-size: 0.875rem;
      color: var(--text-secondary);

      span { display: flex; align-items: center; gap: 0.25rem; }
      .material-icons { font-size: 16px; }
    }
    .challan-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 1rem;
      border-top: 1px solid var(--border-light);
    }
    .amount { font-size: 1.5rem; font-weight: 700; color: var(--error); }
    .btn-sm { padding: 0.5rem 1.5rem; }
  `],
})
export class ChallanListComponent {
  challans: Challan[] = [];

  constructor(private router: Router) {
    const navigation = this.router.getCurrentNavigation();
    this.challans = navigation?.extras?.state?.['challans'] || [];
  }
}
