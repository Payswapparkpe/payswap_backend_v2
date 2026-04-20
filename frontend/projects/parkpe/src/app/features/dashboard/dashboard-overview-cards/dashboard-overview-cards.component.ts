import { Component, input } from '@angular/core';
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

      @if (!challansComingSoon()) {
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
      } @else {
        <span class="overview-card glass-card-dense overview-card--soon" tabindex="0"
          [attr.aria-label]="'Pending Challans – coming soon. Count ' + summary().pendingChallans">
          <div class="overview-icon material-icons"
            [class.overview-icon--urgent]="summary().pendingChallans > 0">gavel</div>
          <div class="overview-label-sm">
            Pending Challans
            <span class="overview-soon-badge">Soon</span>
          </div>
          <div class="overview-value"
            [class.overview-value--urgent]="summary().pendingChallans > 0">
            {{ summary().pendingChallans }}
          </div>
          @if (summary().pendingChallans > 0) {
            <div class="overview-trend overview-trend--urgent">Action needed</div>
          } @else {
            <div class="overview-trend overview-trend--ok">All clear</div>
          }
        </span>
      }

      @if (!fastagComingSoon()) {
        <a routerLink="/fastag" class="overview-card glass-card-dense overview-card--link"
          [class.overview-card--urgent]="summary().fastagBalance <= 0"
          [class.overview-card--warn]="summary().fastagBalance > 0 && summary().fastagBalance < 200">
          <div class="overview-icon material-icons"
            [class.overview-icon--urgent]="summary().fastagBalance <= 0"
            [class.overview-icon--warn]="summary().fastagBalance > 0 && summary().fastagBalance < 200">toll</div>
          <div class="overview-label-sm">Wallet FASTag</div>
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
      } @else {
        <span class="overview-card glass-card-dense overview-card--soon" tabindex="0"
          [attr.aria-label]="'Wallet FASTag – coming soon. Balance ₹' + (summary().fastagBalance | number:'1.0-0')">
          <div class="overview-icon material-icons"
            [class.overview-icon--urgent]="summary().fastagBalance <= 0"
            [class.overview-icon--warn]="summary().fastagBalance > 0 && summary().fastagBalance < 200">toll</div>
          <div class="overview-label-sm">
            Wallet FASTag
            <span class="overview-soon-badge">Soon</span>
          </div>
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
        </span>
      }

      @if (!parkingComingSoon()) {
        <a routerLink="/parking" class="overview-card glass-card-dense overview-card--link">
          <div class="overview-icon material-icons">local_parking</div>
          <div class="overview-label-sm">Active Bookings</div>
          <div class="overview-value">{{ summary().activeBookings }}</div>
          <div class="overview-trend">
            {{ summary().activeBookings > 0 ? 'In progress' : 'None' }}
          </div>
        </a>
      } @else {
        <span class="overview-card glass-card-dense overview-card--soon" tabindex="0"
          [attr.aria-label]="'Active Bookings – coming soon. Count ' + summary().activeBookings">
          <div class="overview-icon material-icons">local_parking</div>
          <div class="overview-label-sm">
            Active Bookings
            <span class="overview-soon-badge">Soon</span>
          </div>
          <div class="overview-value">{{ summary().activeBookings }}</div>
          <div class="overview-trend">
            {{ summary().activeBookings > 0 ? 'In progress' : 'None' }}
          </div>
        </span>
      }
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
    .overview-card--soon {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      cursor: default;
      opacity: 0.82;
      box-sizing: border-box;
    }
    .overview-card--soon:focus {
      outline: 2px solid var(--primary-300, #a5b4fc);
      outline-offset: 2px;
    }
    .overview-soon-badge {
      display: inline-flex;
      align-items: center;
      margin-left: 0.35rem;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      font-size: 0.58rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      background: rgba(100, 116, 139, 0.14);
      color: #64748b;
      vertical-align: middle;
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

  /** Keep aligned with dashboard Quick Actions (FASTag, Challan, Book Parking). */
  challansComingSoon = input(true);
  fastagComingSoon = input(true);
  parkingComingSoon = input(true);
}
