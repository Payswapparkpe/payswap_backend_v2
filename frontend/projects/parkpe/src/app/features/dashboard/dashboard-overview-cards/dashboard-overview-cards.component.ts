import { Component, input, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

export interface DashboardSummary {
  totalSpendMonth: number;
  pendingChallans: number;
  fastagBalance: number;
  activeBookings: number;
}

@Component({
  selector: 'app-dashboard-overview-cards',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="overview-grid">
      <a routerLink="/payment/history" class="overview-card glass-card-dense overview-card--link">
        <div class="overview-icon material-icons">account_balance_wallet</div>
        <div class="overview-label-sm">Total Spend</div>
        <div class="overview-value">₹{{ summary().totalSpendMonth | number:'1.0-0' }}</div>
        <div class="overview-trend">This month</div>
      </a>

      <a routerLink="/challan" class="overview-card glass-card-dense overview-card--link"
        [class.overview-card--urgent]="summary().pendingChallans > 0">
        <div class="overview-icon material-icons"
          [class.overview-icon--urgent]="summary().pendingChallans > 0">gavel</div>
        <div class="overview-label-sm">Pending Challans</div>
        <div class="overview-value"
          [class.overview-value--urgent]="summary().pendingChallans > 0">
          {{ summary().pendingChallans }}
        </div>
        @if (summary().pendingChallans > 0) {
          <div class="overview-trend overview-trend--urgent">Action needed</div>
        } @else {
          <div class="overview-trend overview-trend--ok">All clear</div>
        }
      </a>

      <a routerLink="/fastag" class="overview-card glass-card-dense overview-card--link"
        [class.overview-card--urgent]="summary().fastagBalance <= 0"
        [class.overview-card--warn]="summary().fastagBalance > 0 && summary().fastagBalance < 200">
        <div class="overview-icon material-icons"
          [class.overview-icon--urgent]="summary().fastagBalance <= 0"
          [class.overview-icon--warn]="summary().fastagBalance > 0 && summary().fastagBalance < 200">toll</div>
        <div class="overview-label-sm">FASTag Balance</div>
        <div class="overview-value"
          [class.overview-value--urgent]="summary().fastagBalance <= 0"
          [class.overview-value--warn]="summary().fastagBalance > 0 && summary().fastagBalance < 200">
          ₹{{ summary().fastagBalance | number:'1.0-0' }}
        </div>
        @if (summary().fastagBalance <= 0) {
          <div class="overview-trend overview-trend--urgent">Recharge now</div>
        } @else if (summary().fastagBalance < 200) {
          <div class="overview-trend overview-trend--warn">Low balance</div>
        } @else {
          <div class="overview-trend overview-trend--ok">Sufficient</div>
        }
      </a>

      <a routerLink="/parking" class="overview-card glass-card-dense overview-card--link">
        <div class="overview-icon material-icons">local_parking</div>
        <div class="overview-label-sm">Active Bookings</div>
        <div class="overview-value">{{ summary().activeBookings }}</div>
        <div class="overview-trend">
          {{ summary().activeBookings > 0 ? 'In progress' : 'None' }}
        </div>
      </a>
    </div>
  `,
  styles: [`
    .overview-card--link {
      text-decoration: none;
      color: inherit;
      cursor: pointer;
      transition: box-shadow 0.18s, border-color 0.18s, transform 0.15s, background 0.18s;
    }
    .overview-card--link:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 14px rgba(0,0,0,0.08) !important;
      border-color: var(--primary-200, #c7d2fe) !important;
    }
    .overview-card--link:focus {
      outline: 2px solid var(--primary-500);
      outline-offset: 2px;
    }
    .overview-card--urgent {
      background: #fef2f2 !important;
      border-color: #fecaca !important;
    }
    .overview-card--warn {
      background: #fffbeb !important;
      border-color: #fde68a !important;
    }
    .overview-icon--urgent { color: #dc2626 !important; }
    .overview-icon--warn  { color: #d97706 !important; }
    .overview-value--urgent { color: #b91c1c !important; }
    .overview-value--warn   { color: #b45309 !important; }
    .overview-trend {
      font-size: 0.65rem;
      color: var(--text-muted);
      margin-top: 0.15rem;
      line-height: 1.2;
      font-weight: 500;
    }
    .overview-trend--ok     { color: #15803d; }
    .overview-trend--warn   { color: #b45309; }
    .overview-trend--urgent { color: #b91c1c; font-weight: 700; }
  `],
})
export class DashboardOverviewCardsComponent {
  summary = input.required<DashboardSummary>();
}
