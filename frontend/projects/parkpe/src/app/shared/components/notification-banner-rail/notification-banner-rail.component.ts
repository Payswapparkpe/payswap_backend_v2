import { CommonModule } from '@angular/common';
import { Component, OnChanges, OnInit, SimpleChanges, inject, input, signal } from '@angular/core';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import type { NotificationBannerItem } from '../../../core/api/api-backend.interface';

@Component({
  selector: 'app-notification-banner-rail',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './notification-banner-rail.component.html',
  styleUrl: './notification-banner-rail.component.scss',
})
export class NotificationBannerRailComponent implements OnInit, OnChanges {
  private api = inject(API_BACKEND_TOKEN);

  slot = input('service_inline');
  screen = input('');
  service = input('');
  emptyTitle = input('Promotions & updates');
  emptySubtitle = input('No active banner campaigns right now.');

  items = signal<NotificationBannerItem[]>([]);

  ngOnInit(): void {
    this.load();
  }

  ngOnChanges(_changes: SimpleChanges): void {
    this.load();
  }

  private load(): void {
    this.api
      .getNotificationBanners({
        slot: this.slot(),
        screen: this.screen(),
        service: this.service(),
      })
      .subscribe({
        next: (res) => this.items.set(res?.banners ?? []),
        error: () => this.items.set([]),
      });
  }
}
