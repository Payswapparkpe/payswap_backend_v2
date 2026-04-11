import { Component, inject, input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ConnectService, ConnectThreadDto } from '../services/connect.service';

@Component({
  selector: 'app-connect-threads-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-threads-list.component.html',
  styleUrl: './connect-threads-list.component.scss',
})
export class ConnectThreadsListComponent implements OnInit {
  private connect = inject(ConnectService);
  /** When true, used inside chats shell (no back link, fits in left column). */
  embedded = input<boolean>(false);
  threads = signal<ConnectThreadDto[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  ngOnInit() {
    this.load();
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
}
