import { Injectable, signal } from '@angular/core';
import { Toast, ToastOptions, ToastType } from './toast.model';

type ToastEvent =
  | { kind: 'add'; id: string }
  | { kind: 'request_remove'; id: string }
  | null;

function makeId(): string {
  // Short, readable id for DOM hooks
  return `t_${Math.random().toString(36).slice(2, 9)}_${Date.now().toString(36)}`;
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  private readonly _toasts = signal<Toast[]>([]);
  readonly toasts = this._toasts.asReadonly();

  private readonly _event = signal<ToastEvent>(null);
  readonly event = this._event.asReadonly();

  success(message: string, options?: ToastOptions) {
    return this.show('success', message, options);
  }

  error(message: string, options?: ToastOptions) {
    return this.show('error', message, { durationMs: 5000, ...options });
  }

  info(message: string, options?: ToastOptions) {
    return this.show('info', message, options);
  }

  warning(message: string, options?: ToastOptions) {
    return this.show('warning', message, { durationMs: 4500, ...options });
  }

  show(type: ToastType, message: string, options?: ToastOptions): string {
    const id = makeId();
    const toast: Toast = {
      id,
      type,
      message,
      title: options?.title,
      durationMs: Math.max(0, options?.durationMs ?? 3200),
      createdAt: Date.now(),
    };

    // Defer signal updates to next tick to avoid NG0100 (expression changed after check)
    window.setTimeout(() => {
      this._toasts.update((list) => {
        const next = [toast, ...list];
        return next.slice(0, 5);
      });
      this._event.set({ kind: 'add', id });

      if (toast.durationMs > 0) {
        window.setTimeout(() => this.requestRemove(id), toast.durationMs);
      }
    }, 0);

    return id;
  }

  requestRemove(id: string) {
    window.setTimeout(() => this._event.set({ kind: 'request_remove', id }), 0);
  }

  /** Called after exit animation completes. */
  removeNow(id: string) {
    window.setTimeout(
      () => this._toasts.update((list) => list.filter((t) => t.id !== id)),
      0
    );
  }

  clearAll() {
    window.setTimeout(() => {
      this._toasts.set([]);
      this._event.set(null);
    }, 0);
  }
}

