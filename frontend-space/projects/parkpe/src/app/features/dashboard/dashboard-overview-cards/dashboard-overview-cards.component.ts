import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface DashboardSummary {
  totalSpendMonth: number;
  pendingChallans: number;
  fastagBalance: number;
  activeBookings: number;
}

@Component({
  selector: 'app-dashboard-overview-cards',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="overview-grid">
      <div class="overview-card glass-card-dense">
        <div class="overview-icon material-icons">account_balance_wallet</div>
        <div class="overview-label-sm">Total Spend</div>
        <div class="overview-value">₹{{ summary().totalSpendMonth }}</div>
      </div>
      <div class="overview-card glass-card-dense">
        <div class="overview-icon material-icons" [class.text-error]="summary().pendingChallans > 0">gavel</div>
        <div class="overview-label-sm">Pending Challans</div>
        <div class="overview-value" [class.text-error]="summary().pendingChallans > 0">{{ summary().pendingChallans }}</div>
      </div>
      <div class="overview-card glass-card-dense">
        <div class="overview-icon material-icons">toll</div>
        <div class="overview-label-sm">FASTag Balance</div>
        <div class="overview-value">₹{{ summary().fastagBalance }}</div>
      </div>
      <div class="overview-card glass-card-dense">
        <div class="overview-icon material-icons">local_parking</div>
        <div class="overview-label-sm">Active Bookings</div>
        <div class="overview-value">{{ summary().activeBookings }}</div>
      </div>
    </div>
  `,
  styles: [],
})
export class DashboardOverviewCardsComponent {
  summary = input.required<DashboardSummary>();
}
