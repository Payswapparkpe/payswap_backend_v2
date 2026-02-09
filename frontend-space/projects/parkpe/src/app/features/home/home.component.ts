import {
  Component,
  HostListener,
  signal,
  afterNextRender,
  ElementRef,
  inject,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

type EcosystemItem = {
  icon: string;
  title: string;
  status: string;
  description: string;
  route?: string;
  href?: string;
};

/**
 * Home Component – ParkPe Landing Page
 * Sections: Hero, Problem Statement, Ecosystem, Featured Product, How It Works,
 * Who It's For, Coming Soon, Why ParkPe, Contact, Footer
 * Uses GSAP for hero and scroll-triggered section animations.
 */
@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent {
  private readonly el = inject(ElementRef);

  currentYear = new Date().getFullYear();
  scrolled = signal(false);
  mobileMenuOpen = signal(false);
  contactForm = {
    name: '',
    mobile: '',
    email: '',
    userType: '',
    message: '',
  };
  contactSubmitStatus: 'idle' | 'success' | 'error' = 'idle';
  contactErrorMessage = '';
  contactSubmitting = false;

  readonly problems = [
    { icon: 'warning', title: 'Vehicles block each other with no safe way to contact owners' },
    { icon: 'phone', title: 'Sharing phone numbers compromises privacy' },
    { icon: 'place', title: 'Urban parking systems are manual and unorganized' },
    { icon: 'storage', title: 'No single platform for parking and vehicle-related services' },
  ];

  /** Ecosystem services – Connect opens external Connect app */
  readonly ecosystem: EcosystemItem[] = [
    { icon: 'qr_code_2', title: 'Connect', status: 'Live', description: 'Secure QR-based vehicle owner contact – create QR, chat & call without sharing numbers', href: 'https://connect.parkpe.in' },
    { icon: 'local_parking', title: 'Smart Parking', status: 'Coming Soon', description: 'Automated parking management and booking' },
    { icon: 'credit_card', title: 'FASTag & Financial Services', status: 'Coming Soon', description: 'Vehicle financial services and payments' },
    { icon: 'bolt', title: 'EV & Mobility Services', status: 'Coming Soon', description: 'Electric vehicle charging and mobility solutions' },
  ];

  readonly featuredProductFeatures = [
    { icon: 'qr_code_2', title: 'Unique QR sticker for each vehicle', description: 'Every vehicle gets a unique scannable QR code' },
    { icon: 'shield', title: 'No phone number sharing', description: 'Complete privacy protection for both parties' },
    { icon: 'lock', title: 'OTP-based verification for both sides', description: 'Secure authentication for every interaction' },
    { icon: 'chat', title: 'Works via mobile app and web browser', description: 'Accessible from any device, anywhere' },
    { icon: 'phone', title: 'Secure chat or call', description: 'Connect without exposing personal numbers' },
    { icon: 'block', title: 'Anti-spam protection', description: 'Built-in safeguards against misuse' },
  ];

  readonly howItWorksSteps = [
    { number: '01', icon: 'person_add_alt_1', title: 'Vehicle owner registers on ParkPe', description: 'Quick and easy registration with mobile verification' },
    { number: '02', icon: 'qr_code_2', title: 'ParkPe issues a unique QR sticker', description: 'Each vehicle receives a unique, secure QR code' },
    { number: '03', icon: 'smartphone', title: 'QR sticker is placed on the vehicle', description: 'Stick it on your vehicle\'s windshield or dashboard' },
    { number: '04', icon: 'smartphone', title: 'Any person scans the QR code', description: 'Use any smartphone camera to scan the code' },
    { number: '05', icon: 'check_circle', title: 'OTP verification is completed', description: 'Both parties verify their identity securely' },
    { number: '06', icon: 'message', title: 'Secure communication established', description: 'Chat or call without revealing phone numbers' },
  ];

  readonly whoItsFor = [
    { icon: 'two_wheeler', title: 'Two-Wheeler Owners', description: 'Bike and scooter owners who park in busy areas' },
    { icon: 'directions_car', title: 'Four-Wheeler Owners', description: 'Car owners looking for secure communication' },
    { icon: 'local_shipping', title: 'Commercial Vehicle Owners', description: 'Logistics and transport companies' },
    { icon: 'apartment', title: 'Parking Operators', description: 'Parking lot and facility managers' },
    { icon: 'business', title: 'Municipal Bodies', description: 'City authorities managing urban parking' },
    { icon: 'groups', title: 'Fleet Owners', description: 'Companies managing multiple vehicles' },
  ];

  readonly comingSoonServices = [
    { icon: 'local_parking', title: 'Smart Parking Automation', description: 'AI-powered parking management and real-time availability' },
    { icon: 'credit_card', title: 'FASTag Services', description: 'Integrated toll payment and vehicle financial services' },
    { icon: 'bolt', title: 'EV Charging', description: 'Electric vehicle charging station network and booking' },
    { icon: 'account_balance_wallet', title: 'Vehicle Financial Services', description: 'Insurance, loans, and vehicle-related financial products' },
    { icon: 'account_balance_wallet', title: 'Digital Wallet & Payments', description: 'Unified payment system for all vehicle services' },
    { icon: 'bar_chart', title: 'Parking Analytics', description: 'Data insights for parking operators and municipalities' },
  ];

  readonly whyParkPeReasons = [
    { icon: 'shield', title: 'Privacy-first design', description: 'Your personal information is never shared. We use end-to-end encryption and OTP verification.' },
    { icon: 'place', title: 'Built for Indian cities', description: 'Designed specifically for the unique challenges of urban parking in India.' },
    { icon: 'check_circle', title: 'Secure and verified users', description: 'Every user is verified with mobile OTP, ensuring authentic interactions only.' },
    { icon: 'smartphone', title: 'App and web-based access', description: 'Works seamlessly on mobile apps and web browsers. No downloads required to scan.' },
    { icon: 'trending_up', title: 'Scalable and future-ready platform', description: 'Built on modern architecture to support growing urban mobility needs.' },
  ];

  /** Full Connect app URL; in-app Connect service is at /connect */
  readonly connectUrl = 'https://connect.parkpe.in';
  readonly parkpeUrl = 'https://parkpe.in';
  readonly payswapUrl = 'https://payswap.in';

  constructor(private router: Router) {
    gsap.registerPlugin(ScrollTrigger);
    afterNextRender(() => this.initAnimations());
  }

  private initAnimations(): void {
    const host = this.el.nativeElement as HTMLElement;
    const heroContent = host.querySelector('.hero-content');
    const heroHeadline = host.querySelector('.hero-headline');
    const heroDesc = host.querySelector('.hero-desc');
    const heroCtas = host.querySelector('.hero-ctas');
    const heroStats = host.querySelector('.hero-stats');
    const sections = host.querySelectorAll('.section-reveal');

    const heroEls = [heroHeadline, heroDesc, heroCtas, heroStats].filter(
      (el): el is Element => el != null
    );
    if (heroEls.length > 0) {
      const tl = gsap.timeline({ defaults: { ease: 'power2.out' } });
      tl.set(heroEls, { opacity: 0, y: 24 })
        .to(heroHeadline, { opacity: 1, y: 0, duration: 0.6 })
        .to(heroDesc, { opacity: 1, y: 0, duration: 0.5 }, '-=0.3')
        .to(heroCtas, { opacity: 1, y: 0, duration: 0.4 }, '-=0.2')
        .to(heroStats, { opacity: 1, y: 0, duration: 0.5 }, '-=0.2');
    }

    const trustBadge = heroContent?.querySelector('.trust-badge');
    if (trustBadge) {
      gsap.from(trustBadge, {
        opacity: 0,
        y: 12,
        duration: 0.5,
        delay: 0.2,
        ease: 'power2.out',
      });
    }

    sections.forEach((section, i) => {
      gsap.from(section, {
        scrollTrigger: {
          trigger: section,
          start: 'top 85%',
          end: 'top 60%',
          toggleActions: 'play none none none',
        },
        opacity: 0,
        y: 40,
        duration: 0.6,
        delay: i * 0.05,
        ease: 'power2.out',
      });
    });
  }

  @HostListener('window:scroll')
  onWindowScroll() {
    this.scrolled.set(window.scrollY > 20);
  }

  toggleMobileMenu() {
    this.mobileMenuOpen.update((v) => !v);
  }

  navigateToLogin() {
    this.router.navigate(['/auth/login']);
  }

  navigateToRegister() {
    this.router.navigate(['/auth/register']);
  }

  openConnect() {
    window.open(this.connectUrl, '_blank', 'noopener,noreferrer');
  }

  openPaySwap() {
    window.open(this.payswapUrl, '_blank', 'noopener,noreferrer');
  }

  submitContact() {
    this.contactSubmitting = true;
    this.contactSubmitStatus = 'idle';
    this.contactErrorMessage = '';
    setTimeout(() => {
      this.contactSubmitStatus = 'success';
      this.contactForm = { name: '', mobile: '', email: '', userType: '', message: '' };
      this.contactSubmitting = false;
      setTimeout(() => (this.contactSubmitStatus = 'idle'), 5000);
    }, 600);
  }
}
