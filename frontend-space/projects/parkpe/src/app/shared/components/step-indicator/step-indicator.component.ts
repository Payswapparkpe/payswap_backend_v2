import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

/**
 * Shared step indicator for multi-step flows (BBPS, Parking, etc.).
 * Uses ParkPe brand theme; current step is highlighted.
 */
@Component({
  selector: 'app-step-indicator',
  standalone: true,
  imports: [CommonModule],
  template: `
    <nav class="step-indicator" aria-label="Progress">
      <ol class="steps-list">
        @for (step of steps; track step; let i = $index) {
          <li
            class="step-item"
            [class.current]="i + 1 === currentStep"
            [class.done]="i + 1 < currentStep"
          >
            <span class="step-num" [attr.aria-current]="i + 1 === currentStep ? 'step' : null">
              @if (i + 1 < currentStep) {
                <span class="material-icons">check</span>
              } @else {
                {{ i + 1 }}
              }
            </span>
            <span class="step-label">{{ step }}</span>
            @if (i < steps.length - 1) {
              <span class="step-connector" aria-hidden="true"></span>
            }
          </li>
        }
      </ol>
    </nav>
  `,
  styles: [`
    .step-indicator {
      margin-bottom: 2rem;
    }
    .steps-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 0.5rem;
      align-items: center;
    }
    .step-item {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .step-num {
      width: 2rem;
      height: 2rem;
      border-radius: 50%;
      background: var(--surface-dark);
      color: var(--text-muted);
      font-size: 0.875rem;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: background 0.25s ease, color 0.25s ease;
    }
    .step-item.current .step-num {
      background: var(--primary-500);
      color: var(--text-on-primary);
      box-shadow: var(--shadow-green-md);
    }
    .step-item.done .step-num {
      background: var(--primary-100);
      color: var(--primary-700);
    }
    .step-item.done .step-num .material-icons {
      font-size: 1rem;
    }
    .step-label {
      font-size: 0.875rem;
      color: var(--text-secondary);
      font-weight: 500;
    }
    .step-item.current .step-label {
      color: var(--primary-700);
    }
    .step-connector {
      width: 1.5rem;
      height: 2px;
      background: var(--border-light);
      margin: 0 0.25rem;
    }
    .step-item.done + .step-item .step-connector,
    .step-item.done .step-connector {
      background: var(--primary-300);
    }
    @media (max-width: 640px) {
      .step-label { display: none; }
      .steps-list { gap: 0.25rem; }
      .step-connector { width: 0.75rem; }
    }
  `],
})
export class StepIndicatorComponent {
  @Input() steps: string[] = [];
  @Input() currentStep = 1;
}
