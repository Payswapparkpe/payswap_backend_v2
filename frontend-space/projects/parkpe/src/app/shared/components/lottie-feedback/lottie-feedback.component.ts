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
    <div class="lottie-feedback" [class.success]="type === 'success'" [class.error]="type === 'error'">
      <div class="feedback-icon">
        <span class="material-icons">{{ type === 'success' ? 'check_circle' : 'error' }}</span>
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
    @keyframes scaleIn {
      from { transform: scale(0.5); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
  `],
})
export class LottieFeedbackComponent {
  @Input() type: 'success' | 'error' = 'success';
  @Input() message = '';
}
