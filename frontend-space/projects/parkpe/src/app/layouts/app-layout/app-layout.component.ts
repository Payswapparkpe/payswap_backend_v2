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

type NavItem = {
  label: string;
  path: string;
  icon: string;
  exact?: boolean;
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
  private router = inject(Router);

  @ViewChild('main', { static: true }) mainRef!: ElementRef<HTMLElement>;
  @ViewChild('drawer') drawerRef?: ElementRef<HTMLElement>;

  scrolled = signal(false);
  drawerOpen = signal(false);

  readonly navItems: NavItem[] = [
    { label: 'Parking', path: '/parking', icon: 'local_parking' },
    { label: 'Bills (BBPS)', path: '/bbps', icon: 'receipt_long' },
    { label: 'Vouchers', path: '/vouchers', icon: 'card_giftcard' },
    { label: 'FASTag', path: '/fastag', icon: 'toll' },
    { label: 'Challan', path: '/challan', icon: 'gavel' },
    { label: 'Payments', path: '/payment/history', icon: 'account_balance_wallet' },
    { label: 'Reports', path: '/payment/reports', icon: 'assessment' },
    { label: 'Connect', path: '/connect', icon: 'qr_code_2' },
  ];

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
  }

  @HostListener('window:scroll')
  onScroll() {
    this.scrolled.set(window.scrollY > 8);
  }

  @HostListener('document:keydown.escape')
  onEsc() {
    if (this.drawerOpen()) this.closeDrawer();
  }

  onPageActivate() {
    // Animate main content on route change (inside the layout)
    const el = this.mainRef?.nativeElement?.querySelector('.app-content') as HTMLElement | null;
    if (!el) return;
    if (this.prefersReducedMotion()) return;
    gsap.fromTo(
      el,
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.35, ease: 'power3.out' }
    );
  }

  logout() {
    this.auth.logout();
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

