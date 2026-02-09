import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-empty-state',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="empty-state">
      <span class="material-icons">{{ icon }}</span>
      <h3>{{ title }}</h3>
      @if (message) {
        <p>{{ message }}</p>
      }
      @if (actionText) {
        <button class="btn btn-primary" (click)="onAction()">{{ actionText }}</button>
      }
    </div>
  `,
  styles: [`
    .empty-state {
      text-align: center;
      padding: 4rem 2rem;

      .material-icons {
        font-size: 80px;
        color: var(--text-muted);
        margin-bottom: 1rem;
      }

      h3 {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.5rem;
      }

      p {
        color: var(--text-secondary);
        margin-bottom: 1.5rem;
      }
    }
  `],
})
export class EmptyStateComponent {
  @Input() icon = 'inbox';
  @Input() title = 'No data available';
  @Input() message = '';
  @Input() actionText = '';
  @Input() onAction = () => {};
}
