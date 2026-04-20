import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../core/constants';
import type { InboxNotificationItem } from '../../core/api/api-backend.interface';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-notification-inbox',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './notification-inbox.component.html',
  styleUrl: './notification-inbox.component.scss',
})
export class NotificationInboxComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);
  private notify = inject(NotificationService);

  loading = signal(true);
  items = signal<InboxNotificationItem[]>([]);
  total = signal(0);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.getNotificationFeed({ limit: 100, offset: 0 }).subscribe({
      next: (res) => {
        this.items.set(res?.items ?? []);
        this.total.set(res?.total ?? 0);
        this.loading.set(false);
      },
      error: () => {
        this.items.set([]);
        this.total.set(0);
        this.loading.set(false);
      },
    });
  }

  markRead(item: InboxNotificationItem): void {
    if (item.isRead) {
      this.open(item);
      return;
    }
    this.api.markNotificationRead(item.id).subscribe({
      next: () => {
        this.items.update((rows) =>
          rows.map((row) => (row.id === item.id ? { ...row, isRead: true, readAt: new Date().toISOString() } : row))
        );
        this.open(item);
      },
      error: () => this.open(item),
    });
  }

  open(item: InboxNotificationItem): void {
    const deepLink = (item.deepLink || '').trim();
    if (!deepLink) {
      this.notify.showInfo('This notification has no in-app link.');
      return;
    }
    if (deepLink.startsWith('/')) {
      void this.router.navigateByUrl(deepLink);
      return;
    }
    if (/^https?:\/\//i.test(deepLink)) {
      this.notify.showWarning(
        'This link opens outside the app. Use the original message (email/SMS) on your device if needed.'
      );
      return;
    }
    this.notify.showWarning('This link cannot be opened inside the app.');
  }
}
