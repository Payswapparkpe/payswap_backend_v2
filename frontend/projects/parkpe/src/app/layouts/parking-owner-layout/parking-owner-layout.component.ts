import { CommonModule } from '@angular/common';
import { Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

export type HubNavIcon =
  | 'dashboard'
  | 'verify'
  | 'locations'
  | 'bookings'
  | 'revenue'
  | 'team';

@Component({
  selector: 'app-parking-owner-layout',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './parking-owner-layout.component.html',
  styleUrl: './parking-owner-layout.component.scss',
})
export class ParkingOwnerLayoutComponent {
  private auth = inject(AuthService);

  user = computed(() => this.auth.userSignal());
  role = computed(() => this.auth.getParkingRole(this.user()) ?? 'attendant');
  name = computed(() => this.user()?.name || 'Parking Operator');

  navItems = computed(() => {
    const role = this.role();
    const base: { label: string; path: string; icon: HubNavIcon }[] = [
      { label: 'Dashboard', path: '/hub/parking/dashboard', icon: 'dashboard' },
      { label: 'Verify Gate', path: '/hub/parking/verify', icon: 'verify' },
      { label: 'Locations', path: '/hub/parking/locations', icon: 'locations' },
      { label: 'Bookings', path: '/hub/parking/bookings', icon: 'bookings' },
    ];
    if (role === 'owner' || role === 'manager') {
      base.push({ label: 'Revenue', path: '/hub/parking/revenue', icon: 'revenue' });
    }
    if (role === 'owner') {
      base.push({ label: 'Team', path: '/hub/parking/team', icon: 'team' });
    }
    return base;
  });

  logout(): void {
    this.auth.parkingLogout();
  }
}
