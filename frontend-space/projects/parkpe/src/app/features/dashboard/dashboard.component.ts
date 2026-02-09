import { ChangeDetectorRef, Component, ElementRef, afterNextRender, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../core/constants';
import { AuthService } from '../../core/services/auth.service';
import { ConnectService } from '../connect/services/connect.service';
import { timeout, catchError, of } from 'rxjs';
import type { Transaction } from '../../core/models/payment.model';
import type { ConnectVehicle } from '../connect/services/connect.service';
import gsap from 'gsap';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private readonly el = inject(ElementRef);
  private api = inject(API_BACKEND_TOKEN);
  private authService = inject(AuthService);
  private connectService = inject(ConnectService);
  private cdr = inject(ChangeDetectorRef);

  summary: {
    totalSpendMonth: number;
    pendingChallans: number;
    fastagBalance: number;
    activeBookings: number;
  } = {
    totalSpendMonth: 0,
    pendingChallans: 0,
    fastagBalance: 0,
    activeBookings: 0,
  };

  recentTransactions: Transaction[] = [];

  connectVehicles: ConnectVehicle[] = [];
  connectVehiclesLoading = true;

  /** Quick Actions – Connect goes to /connect (Hub), not landing/product page */
  quickActions = [
    { title: 'Vouchers', description: 'Buy a voucher or view your vouchers and PIN.', icon: 'card_giftcard', route: '/vouchers' },
    { title: 'Pay Bills', description: 'Electricity, water, and more.', icon: 'receipt_long', route: '/bbps' },
    { title: 'FASTag', description: 'Recharge your FASTag.', icon: 'toll', route: '/fastag' },
    { title: 'Challans', description: 'Pay traffic challans.', icon: 'gavel', route: '/challan' },
    { title: 'Book Parking', description: 'Find and reserve parking slots.', icon: 'local_parking', route: '/parking' },
    { title: 'Connect', description: 'Manage vehicles, QR, scan to contact.', icon: 'qr_code_2', route: '/connect' },
    { title: 'Transaction History', description: 'View payments and receipts.', icon: 'history', route: '/payment/history' },
    { title: 'Reports', description: 'Payment, transaction and voucher reports.', icon: 'assessment', route: '/payment/reports' },
  ];

  constructor() {
    afterNextRender(() => this.initAnimations());
  }

  ngOnInit() {
    this.loadDashboardData();
    this.loadRecentTransactions();
    this.loadConnectVehicles();
  }

  private loadConnectVehicles() {
    this.connectVehiclesLoading = true;
    this.connectService
      .getVehicles()
      .pipe(
        timeout(8000),
        catchError(() => of([]))
      )
      .subscribe((list) => {
        this.connectVehicles = list.slice(0, 4);
        this.connectVehiclesLoading = false;
        this.cdr.detectChanges();
      });
  }

  private initAnimations() {
    if (
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return;
    }

    const host = this.el.nativeElement as HTMLElement;
    const hero = host.querySelector('.hero-card');
    const vehiclesSection = host.querySelector('.vehicles-section');
    const summaryCards = Array.from(host.querySelectorAll('.summary-card'));
    const quickWrap = host.querySelector('.quick-actions-wrapper');
    const actionCards = Array.from(host.querySelectorAll('.action-card'));
    const recent = host.querySelector('.recent-card');

    const firstBatch = [hero, vehiclesSection, quickWrap, recent].filter(
      (x): x is Element => x != null
    );

    gsap.set([...firstBatch, ...summaryCards, ...actionCards], { opacity: 0, y: 14 });

    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
    tl.to(firstBatch, { opacity: 1, y: 0, duration: 0.45, stagger: 0.08 })
      .to(
        summaryCards,
        { opacity: 1, y: 0, duration: 0.4, stagger: 0.06 },
        '-=0.20'
      )
      .to(
        actionCards,
        { opacity: 1, y: 0, duration: 0.35, stagger: 0.03 },
        '-=0.22'
      );
  }

  loadRecentTransactions() {
    this.api
      .getTransactionHistory({ limit: 5 })
      .pipe(
        timeout(5000),
        catchError(() => of({ transactions: [], total: 0 }))
      )
      .subscribe((res) => {
        this.recentTransactions = res.transactions.slice(0, 5);
        this.cdr.detectChanges(); // Flush view so toast-triggered CD sees consistent state (e.g. @if at line 97)
      });
  }

  loadDashboardData() {
    const fallback = {
      totalSpendMonth: 0,
      pendingChallans: 0,
      fastagBalance: 0,
      activeBookings: 0,
    };
    this.api
      .getDashboardSummary()
      .pipe(
        timeout(10000),
        catchError(() => of(fallback))
      )
      .subscribe((data) => {
        this.summary = data;
        this.cdr.detectChanges(); // Flush view so toast-triggered CD sees consistent summary
      });
  }

}
