import { CommonModule } from '@angular/common';
import {
  Component,
  ElementRef,
  HostListener,
  ViewChild,
  afterNextRender,
  inject,
  signal,
} from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import gsap from 'gsap';
import { AuthService } from '../../core/services/auth.service';
import { SessionLockService } from '../../core/services/session-lock.service';
import { API_BACKEND_TOKEN } from '../../core/constants';
import { MobilityStateStore } from '../../core/stores/mobility-state.store';

type NavItem = {
  label: string;
  path: string;
  icon: string;
  exact?: boolean;
  comingSoon?: boolean;
};

@Component({
  selector: 'app-app-layout',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app-layout.component.html',
  styleUrl: './app-layout.component.scss',
})
export class AppLayoutComponent {
  private auth = inject(AuthService);
  private sessionLock = inject(SessionLockService);
  private router = inject(Router);
  private api = inject(API_BACKEND_TOKEN);
  private mobilityStore = inject(MobilityStateStore);

  @ViewChild('main', { static: true }) mainRef!: ElementRef<HTMLElement>;
  @ViewChild('drawer') drawerRef?: ElementRef<HTMLElement>;

  scrolled = signal(false);
  drawerOpen = signal(false);
  unreadNotifications = signal(0);
  /** Top-right account dropdown: consumer (profile/settings/lock/logout) or fleet (lock/logout). */
  accountMenu = signal<'closed' | 'consumer' | 'fleet'>('closed');

  @ViewChild('accountMenuRoot') accountMenuRoot?: ElementRef<HTMLElement>;

  get isFleetWorkspace(): boolean {
    const path = this.router.url.split('?')[0];
    // Interest / onboarding lives under /fleet but uses consumer shell (not full fleet ops nav).
    if (path === '/fleet/interest' || path.startsWith('/fleet/interest/')) {
      return false;
    }
    return path.startsWith('/fleet');
  }

  /** Consumer ParkPe services — not shown in the fleet shell. */
  readonly consumerNavItems: NavItem[] = [
    { label: 'Parking', path: '/parking', icon: 'local_parking', comingSoon: true },
    { label: 'Bills (BBPS)', path: '/bbps', icon: 'receipt_long' },
    { label: 'Vouchers', path: '/vouchers', icon: 'card_giftcard' },
    { label: 'FASTag', path: '/fastag', icon: 'toll', comingSoon: true },
    { label: 'Challan', path: '/challan', icon: 'gavel', comingSoon: true },
    { label: 'Payments', path: '/payment/history', icon: 'account_balance_wallet' },
    { label: 'Reports', path: '/payment/reports', icon: 'assessment' },
    { label: 'Connect', path: '/connect', icon: 'qr_code_2' },
  ];

  /** Fleet-only navigation — separate from individual consumer data and routes. */
  readonly fleetNavItems: NavItem[] = [
    { label: 'Control center', path: '/fleet/control-center', icon: 'hub', exact: true },
    { label: 'Vehicles', path: '/fleet/vehicles', icon: 'directions_car' },
    { label: 'Drivers', path: '/fleet/drivers', icon: 'badge' },
    { label: 'Trips', path: '/fleet/trips', icon: 'route' },
    { label: 'Compliance', path: '/fleet/compliance', icon: 'fact_check' },
  ];

  get navItems(): NavItem[] {
    return this.isFleetWorkspace ? this.fleetNavItems : this.consumerNavItems;
  }

  /** Home / logo target: fleet hub vs consumer dashboard. */
  get shellHomePath(): string {
    return this.isFleetWorkspace ? '/fleet/control-center' : '/dashboard';
  }

  goFleetWorkspace(): void {
    if (this.auth.isFleetUser()) {
      void this.router.navigate(['/fleet/control-center']);
      return;
    }
    void this.router.navigate(['/fleet/interest']);
  }

  /** Consumer / personal ParkPe (BBPS, vouchers, etc.) — same login, different shell. */
  goIndividualHome(): void {
    void this.router.navigate(['/dashboard']);
  }

  private prefersReducedMotion(): boolean {
    return (
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
  }

  constructor() {
    // First paint entrance (nice premium feel)
    afterNextRender(() => {
      const el = this.mainRef?.nativeElement;
      if (!el) return;
      if (this.prefersReducedMotion()) return;
      gsap.fromTo(
        el,
        { opacity: 0, y: 10 },
        { opacity: 1, y: 0, duration: 0.45, ease: 'power3.out' }
      );
    });
    this.loadUnreadCount();
  }

  @HostListener('window:scroll')
  onScroll() {
    this.scrolled.set(window.scrollY > 8);
  }

  @HostListener('document:visibilitychange')
  onVisibilityChange(): void {
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      this.mobilityStore.notifySessionResumed();
    }
  }

  @HostListener('document:keydown.escape')
  onEsc() {
    if (this.accountMenu() !== 'closed') {
      this.accountMenu.set('closed');
      return;
    }
    if (this.drawerOpen()) this.closeDrawer();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(ev: MouseEvent) {
    const root = this.accountMenuRoot?.nativeElement;
    if (this.accountMenu() === 'closed' || !root) return;
    if (!root.contains(ev.target as Node)) {
      this.accountMenu.set('closed');
    }
  }

  toggleAccountMenu(ev: Event, kind: 'consumer' | 'fleet') {
    ev.stopPropagation();
    this.accountMenu.update((current) => (current === kind ? 'closed' : kind));
  }

  closeAccountMenu() {
    this.accountMenu.set('closed');
  }

  onPageActivate() {
    this.accountMenu.set('closed');
    // Animate main content on route change (inside the layout)
    const el = this.mainRef?.nativeElement?.querySelector('.app-content') as HTMLElement | null;
    if (!el) return;
    if (this.prefersReducedMotion()) return;
    gsap.fromTo(
      el,
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.35, ease: 'power3.out' }
    );
    this.loadUnreadCount();
  }

  logout() {
    this.auth.logout();
  }

  lockSession() {
    this.sessionLock.lock('manual');
  }

  openNotifications() {
    if (this.isFleetWorkspace) return;
    this.router.navigate(['/notifications']);
  }

  loadUnreadCount() {
    if (this.isFleetWorkspace) {
      this.unreadNotifications.set(0);
      return;
    }
    this.api.getNotificationUnreadCount().subscribe({
      next: (res) => this.unreadNotifications.set(res?.unread ?? 0),
      error: () => this.unreadNotifications.set(0),
    });
  }

  toggleDrawer() {
    if (this.drawerOpen()) {
      this.closeDrawer();
      return;
    }

    this.drawerOpen.set(true);
    if (this.prefersReducedMotion()) return;
    afterNextRender(() => {
      const drawer = this.drawerRef?.nativeElement;
      if (!drawer) return;
      gsap.fromTo(
        drawer,
        { x: 24, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.28, ease: 'power3.out' }
      );
    });
  }

  closeDrawer() {
    const drawer = this.drawerRef?.nativeElement;
    if (!drawer) {
      this.drawerOpen.set(false);
      return;
    }
    if (this.prefersReducedMotion()) {
      this.drawerOpen.set(false);
      return;
    }
    gsap.to(drawer, {
      x: 24,
      opacity: 0,
      duration: 0.2,
      ease: 'power2.in',
      onComplete: () => this.drawerOpen.set(false),
    });
  }
}

