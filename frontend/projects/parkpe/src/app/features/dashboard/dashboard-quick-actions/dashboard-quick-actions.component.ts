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
        <a routerLink="/services" class="link-blue">View All</a>
      </div>
      <p class="quick-actions-subtitle">Your most-used services, in one place.</p>
      <div class="quick-actions-grid">
        @for (action of actions(); track action.route) {
          @if (action.comingSoon) {
            <span class="action-card action-card--soon glass-card-dense" [attr.aria-label]="action.title + ' – coming soon'" tabindex="0">
              <span class="action-title">
                {{ action.title }}
                <span class="action-soon-badge">Soon</span>
              </span>
              <div class="action-row">
                <span class="material-icons action-icon action-icon--muted" aria-hidden="true">{{ action.icon }}</span>
                <span class="action-desc">{{ action.description }}</span>
              </div>
            </span>
          } @else {
            <a [routerLink]="action.route" class="action-card glass-card-dense">
              <span class="action-title">{{ action.title }}</span>
              <div class="action-row">
                <span class="material-icons action-icon" aria-hidden="true">{{ action.icon }}</span>
                <span class="action-desc">{{ action.description }}</span>
              </div>
            </a>
          }
        }
      </div>
    </div>
  `,
  styles: [`
    .action-card--soon {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      justify-content: flex-start;
      gap: 0.5rem;
      padding: 0.75rem 1rem;
      height: 96px;
      min-height: 96px;
      border-radius: 12px;
      background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%) !important;
      border: 1px solid rgba(203, 213, 225, 0.85) !important;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85);
      box-sizing: border-box;
      overflow: hidden;
      cursor: default;
      opacity: 0.72;
    }
    .action-soon-badge {
      display: inline-flex;
      align-items: center;
      margin-left: 0.4rem;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      font-size: 0.6rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      background: rgba(100, 116, 139, 0.12);
      color: #64748b;
      vertical-align: middle;
      line-height: 1.4;
    }
    .action-icon--muted {
      color: #94a3b8 !important;
    }
  `],
})
export class DashboardQuickActionsComponent {
  actions = input.required<QuickAction[]>();
}
