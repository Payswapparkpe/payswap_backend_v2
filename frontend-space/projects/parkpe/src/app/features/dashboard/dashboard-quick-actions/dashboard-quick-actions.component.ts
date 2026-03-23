import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

export interface QuickAction {
  title: string;
  description: string;
  icon: string;
  route: string;
  comingSoon?: boolean;
}

@Component({
  selector: 'app-dashboard-quick-actions',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="card-section">
      <div class="section-header">
        <h3 class="section-title">Quick Actions</h3>
        <a routerLink="/services" class="link-blue">View all</a>
      </div>
      <p class="quick-actions-subtitle">Jump back into your most used services.</p>
      <div class="quick-actions-grid">
        <a *ngFor="let action of actions()" [routerLink]="action.route" class="action-card glass-card-dense">
          <span class="action-title">{{ action.title }}</span>
          <div class="action-row">
            <span class="material-icons action-icon">{{ action.icon }}</span>
            <span class="action-desc">{{ action.description }}</span>
          </div>
        </a>
      </div>
    </div>
  `,
  styles: [],
})
export class DashboardQuickActionsComponent {
  actions = input.required<QuickAction[]>();
}
