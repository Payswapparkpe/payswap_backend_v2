import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterOutlet } from '@angular/router';
import { ConnectThreadsListComponent } from '../connect-threads-list/connect-threads-list.component';

@Component({
  selector: 'app-connect-chats-shell',
  standalone: true,
  imports: [CommonModule, RouterOutlet, ConnectThreadsListComponent],
  template: `
    <div class="connect-chats-shell">
      <div class="service-layout">
        <aside class="service-col-left">
          <app-connect-threads-list [embedded]="true" />
        </aside>
        <main class="service-col-right">
          @if (hasChildRoute()) {
            <router-outlet />
          } @else {
            <div class="service-placeholder">
              <p class="service-placeholder-title">Select a chat</p>
              <p class="service-placeholder-hint">Choose a thread from the list to view and send messages, or scan a vehicle QR to start a new conversation.</p>
            </div>
          }
        </main>
      </div>
    </div>
  `,
  styles: [`
    .connect-chats-shell { padding: 1rem; max-width: 1400px; margin: 0 auto; }
  `],
})
export class ConnectChatsShellComponent {
  private router = inject(Router);

  hasChildRoute(): boolean {
    const u = this.router.url;
    return u.includes('/connect/chats/') && !u.replace(/\/$/, '').endsWith('/connect/chats');
  }
}
