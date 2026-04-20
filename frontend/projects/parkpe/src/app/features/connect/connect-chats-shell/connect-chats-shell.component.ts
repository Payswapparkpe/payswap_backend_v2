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
    .connect-chats-shell {
      padding: 0.75rem 1rem 1rem;
      max-width: 1400px;
      margin: 0 auto;
      box-sizing: border-box;
    }
    /* Let chat fill the right column (global .service-col-right uses align-self: start). */
    .connect-chats-shell .service-layout {
      align-items: stretch;
    }
    @media (min-width: 768px) {
      .connect-chats-shell .service-layout {
        min-height: min(90vh, 880px);
      }
    }
    .connect-chats-shell .service-col-left {
      align-self: stretch;
    }
    .connect-chats-shell .service-col-right {
      align-self: stretch;
      display: flex;
      flex-direction: column;
      min-height: 0;
      min-width: 0;
    }
    .connect-chats-shell .service-col-right app-connect-thread-chat {
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
    }
  `],
})
export class ConnectChatsShellComponent {
  private router = inject(Router);

  hasChildRoute(): boolean {
    const u = this.router.url;
    return u.includes('/connect/chats/') && !u.replace(/\/$/, '').endsWith('/connect/chats');
  }
}
