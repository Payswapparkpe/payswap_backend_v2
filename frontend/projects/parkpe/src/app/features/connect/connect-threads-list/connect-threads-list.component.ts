import { Component, inject, input, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { ConnectService, ConnectThreadDto } from '../services/connect.service';
import { Subscription, merge, interval, fromEvent } from 'rxjs';
import { filter } from 'rxjs/operators';

@Component({
  selector: 'app-connect-threads-list',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './connect-threads-list.component.html',
  styleUrl: './connect-threads-list.component.scss',
})
export class ConnectThreadsListComponent implements OnInit, OnDestroy {
  private connect = inject(ConnectService);
  private refreshSub: Subscription | null = null;
  /** When true, used inside chats shell (no back link, fits in left column). */
  embedded = input<boolean>(false);
  threads = signal<ConnectThreadDto[]>([]);
  search = signal('');
  includeArchived = signal(false);
  filterUnreadOnly = signal(false);
  loading = signal(true);
  error = signal<string | null>(null);

  ngOnInit() {
    this.load();
    this.refreshSub = merge(
      interval(12000),
      fromEvent(document, 'visibilitychange').pipe(filter(() => document.visibilityState === 'visible')),
    ).subscribe(() => this.refreshThreadsQuietly());
  }

  ngOnDestroy() {
    this.refreshSub?.unsubscribe();
  }

  /** Refresh inbox in the background so unread badges update while another thread is open. */
  private refreshThreadsQuietly() {
    this.connect.getThreads().subscribe({
      next: (list) => this.threads.set(list),
      error: () => {},
    });
  }

  load() {
    this.loading.set(true);
    this.error.set(null);
    this.connect.getThreads().subscribe({
      next: (list) => {
        this.threads.set(list);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to load chats');
        this.loading.set(false);
      },
    });
  }

  onSearchInput(e: Event) {
    this.search.set((e.target as HTMLInputElement)?.value ?? '');
  }

  toggleArchived() {
    this.includeArchived.update((v) => !v);
  }

  toggleUnreadOnly() {
    this.filterUnreadOnly.update((v) => !v);
  }

  visibleThreads() {
    const q = this.search().trim().toLowerCase();
    return this.threads().filter((t) => {
      if (!this.includeArchived() && t.archived) return false;
      if (this.filterUnreadOnly() && !(t.unread_count && t.unread_count > 0)) return false;
      if (!q) return true;
      return (
        t.registration_number_masked.toLowerCase().includes(q) ||
        (t.peer_display_name || t.owner_display_name || '').toLowerCase().includes(q) ||
        (t.last_message_preview || '').toLowerCase().includes(q)
      );
    }).sort((a, b) => {
      const pinDiff = Number(Boolean(b.pinned)) - Number(Boolean(a.pinned));
      if (pinDiff !== 0) return pinDiff;
      const unreadDiff = (b.unread_count || 0) - (a.unread_count || 0);
      if (unreadDiff !== 0) return unreadDiff;
      const aTs = new Date(a.last_message_created_at || '').getTime() || 0;
      const bTs = new Date(b.last_message_created_at || '').getTime() || 0;
      return bTs - aTs;
    });
  }

  threadInitial(t: ConnectThreadDto): string {
    const name = (t.peer_display_name || t.owner_display_name || '').trim().replace(/\*+$/, '');
    const reg = (t.registration_number_masked || '').trim();
    const s = name || reg;
    if (!s) return '?';
    return s.charAt(0).toUpperCase();
  }

  toggleThreadSetting(thread: ConnectThreadDto, setting: 'pinned' | 'muted' | 'archived', event: Event) {
    event.preventDefault();
    event.stopPropagation();
    (event.target as HTMLElement).closest('details')?.removeAttribute('open');
    const nextVal = !Boolean(thread[setting]);
    this.connect.updateThreadSettings(thread.id, { [setting]: nextVal }).subscribe({
      next: (updated) => {
        this.threads.update((list) => list.map((t) => (t.id === thread.id ? { ...t, ...updated } : t)));
      },
      error: () => {},
    });
  }
}
