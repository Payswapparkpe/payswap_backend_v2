import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

/**
 * Shared success/error feedback with animated icon.
 * Set lottieUrl to an asset path to use Lottie animation instead.
 */
@Component({
  selector: 'app-lottie-feedback',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="lottie-feedback" [class.success]="type === 'success'" [class.error]="type === 'error'" [class.pending]="type === 'pending'">
      <div class="feedback-icon">
        <span class="material-icons">{{ iconName }}</span>
      </div>
      @if (message) {
        <p class="feedback-message">{{ message }}</p>
      }
    </div>
  `,
  styles: [`
    .lottie-feedback {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
      text-align: center;
    }
    .feedback-icon {
      width: 120px;
      height: 120px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .feedback-icon .material-icons {
      font-size: 80px;
      animation: scaleIn 0.4s ease-out;
    }
    .lottie-feedback.success .feedback-icon .material-icons {
      color: var(--success);
    }
    .lottie-feedback.error .feedback-icon .material-icons {
      color: var(--error);
    }
    .lottie-feedback.pending .feedback-icon .material-icons {
      color: var(--warning, #ed6c02);
    }
    .feedback-message {
      margin-top: 1rem;
      font-size: 1.125rem;
      font-weight: 500;
      color: var(--text-primary);
      max-width: 320px;
    }
    .lottie-feedback.error .feedback-message {
      color: var(--error);
    }
    .lottie-feedback.pending .feedback-message {
      color: var(--text-secondary);
    }
    @keyframes scaleIn {
      from { transform: scale(0.5); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
  `],
})
export class LottieFeedbackComponent {
  @Input() type: 'success' | 'error' | 'pending' = 'success';
  @Input() message = '';

  get iconName(): string {
    switch (this.type) {
      case 'success': return 'check_circle';
      case 'error': return 'error';
      case 'pending': return 'schedule';
      default: return 'check_circle';
    }
  }
}
