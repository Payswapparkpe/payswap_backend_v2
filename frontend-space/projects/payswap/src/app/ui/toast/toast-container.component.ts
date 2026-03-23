import { CommonModule } from '@angular/common';
import { Component, effect, inject } from '@angular/core';
import gsap from 'gsap';
import { ToastService } from './toast.service';

@Component({
  selector: 'app-toast-container',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="toast-viewport" aria-live="polite" aria-relevant="additions removals">
      @for (t of toastService.toasts(); track t.id) {
        <div
          class="toast"
          [class.success]="t.type === 'success'"
          [class.error]="t.type === 'error'"
          [class.info]="t.type === 'info'"
          [class.warning]="t.type === 'warning'"
          [attr.data-toast-id]="t.id"
          role="status"
        >
          <div class="toast-icon" aria-hidden="true">
            <span class="material-icons">{{ iconFor(t.type) }}</span>
          </div>
          <div class="toast-body">
            <div class="toast-title">{{ t.title || titleFor(t.type) }}</div>
            <div class="toast-msg">{{ t.message }}</div>
          </div>
          <button type="button" class="toast-close" (click)="close(t.id)" aria-label="Close">
            <span class="material-icons">close</span>
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    .toast-viewport {
      position: fixed;
      top: 1rem;
      right: 1rem;
      z-index: 2000;
      width: min(420px, calc(100vw - 2rem));
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      pointer-events: none;
    }

    .toast {
      pointer-events: auto;
      display: grid;
      grid-template-columns: 2.25rem 1fr 2rem;
      gap: 0.75rem;
      align-items: start;
      padding: 0.9rem 0.9rem;
      border-radius: 1rem;
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid rgba(226, 232, 240, 0.9);
      box-shadow: 0 18px 45px rgba(15, 23, 42, 0.12);
      backdrop-filter: blur(12px);
    }

    .toast-icon {
      width: 2.25rem;
      height: 2.25rem;
      border-radius: 0.85rem;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(0, 74, 173, 0.10);
      color: var(--primary-700, #004aad);
    }

    .toast.error .toast-icon {
      background: rgba(239, 68, 68, 0.12);
      color: var(--error, #ef4444);
    }
    .toast.success .toast-icon {
      background: rgba(34, 197, 94, 0.12);
      color: var(--success, #22c55e);
    }
    .toast.warning .toast-icon {
      background: rgba(245, 158, 11, 0.14);
      color: var(--warning, #f59e0b);
    }
    .toast.info .toast-icon {
      background: rgba(59, 130, 246, 0.12);
      color: var(--info, #3b82f6);
    }

    .toast-icon .material-icons { font-size: 1.25rem; }

    .toast-title {
      font-weight: 800;
      color: var(--text-primary, #0f172a);
      letter-spacing: -0.01em;
      line-height: 1.1;
      margin-top: 0.1rem;
    }

    .toast-msg {
      margin-top: 0.25rem;
      font-size: 0.92rem;
      color: var(--text-secondary, #334155);
      line-height: 1.35;
    }

    .toast-close {
      margin-left: auto;
      width: 2rem;
      height: 2rem;
      border: none;
      background: transparent;
      cursor: pointer;
      color: var(--text-muted, #64748b);
      border-radius: 0.75rem;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s, color 0.15s;
    }
    .toast-close:hover {
      background: rgba(15, 23, 42, 0.06);
      color: var(--text-primary, #0f172a);
    }

    @media (max-width: 480px) {
      .toast-viewport { top: 0.75rem; right: 0.75rem; }
    }

    @media (prefers-reduced-motion: reduce) {
      .toast { transition: none; }
    }
  `],
})
export class ToastContainerComponent {
  readonly toastService = inject(ToastService);

  constructor() {
    effect(() => {
      const evt = this.toastService.event();
      if (!evt) return;

      const id = evt.id;
      const kind = evt.kind;
      setTimeout(() => {
        const el = document.querySelector(`[data-toast-id="${id}"]`) as HTMLElement | null;
        if (!el) return;

        if (kind === 'add') {
          gsap.fromTo(
            el,
            { opacity: 0, y: -10, scale: 0.98 },
            { opacity: 1, y: 0, scale: 1, duration: 0.38, ease: 'power3.out' }
          );
          return;
        }

        if (kind === 'request_remove') {
          gsap.to(el, {
            opacity: 0,
            x: 24,
            duration: 0.26,
            ease: 'power2.in',
            onComplete: () => this.toastService.removeNow(id),
          });
        }
      }, 0);
    });
  }

  close(id: string) {
    this.toastService.requestRemove(id);
  }

  iconFor(type: string) {
    switch (type) {
      case 'success':
        return 'check_circle';
      case 'error':
        return 'error';
      case 'warning':
        return 'warning';
      default:
        return 'info';
    }
  }

  titleFor(type: string) {
    switch (type) {
      case 'success':
        return 'Success';
      case 'error':
        return 'Something went wrong';
      case 'warning':
        return 'Heads up';
      default:
        return 'Info';
    }
  }
}

