import { Component, inject, computed } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-dashboard-welcome-banner',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="welcome-banner">
      <div class="welcome-banner-inner">
        <div class="welcome-text">
          <div class="welcome-label">{{ greeting() }}</div>
          <h1 class="welcome-headline">Your vehicle services, simplified</h1>
          <p class="welcome-subtitle">Recharge FASTag, pay challans, book parking and manage bills — all in one place.</p>
        </div>
        <div class="welcome-actions">
          <button routerLink="/parking" class="btn-pill btn-white">Book Parking</button>
          <button routerLink="/connect" class="btn-pill" style="background: rgba(255,255,255,0.2); color: #fff; border: 1px solid rgba(255,255,255,0.4);">ParkPe Connect</button>
        </div>
      </div>
    </div>
  `,
  styles: [],
})
export class DashboardWelcomeBannerComponent {
  private auth = inject(AuthService);

  firstName = computed(() => {
    const user = this.auth.userSignal();
    if (!user?.name) return '';
    return user.name.split(' ')[0];
  });

  greeting = computed(() => {
    const hour = new Date().getHours();
    const name = this.firstName();
    const suffix = name ? `, ${name}` : '';
    if (hour < 12) return `Good morning${suffix} 👋`;
    if (hour < 17) return `Good afternoon${suffix} 👋`;
    return `Good evening${suffix} 👋`;
  });
}
