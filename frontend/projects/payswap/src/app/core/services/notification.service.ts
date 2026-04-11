import { Injectable, inject } from '@angular/core';
import { ToastService } from '../../ui/toast/toast.service';

/**
 * Notification Service
 * Displays user notifications
 * TODO: Integrate with MatSnackBar when Material is installed
 */
@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private toast = inject(ToastService);

  showSuccess(message: string, duration = 3000): void {
    this.toast.success(message, { durationMs: duration, title: 'Success' });
  }

  showError(message: string, duration = 5000): void {
    this.toast.error(message, { durationMs: duration, title: 'Error' });
  }

  showInfo(message: string, duration = 3000): void {
    this.toast.info(message, { durationMs: duration, title: 'Info' });
  }

  showWarning(message: string, duration = 4000): void {
    this.toast.warning(message, { durationMs: duration, title: 'Warning' });
  }
}
