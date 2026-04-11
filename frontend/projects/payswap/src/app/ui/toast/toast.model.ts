export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastOptions {
  title?: string;
  durationMs?: number;
}

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  title?: string;
  durationMs: number;
  createdAt: number;
}

