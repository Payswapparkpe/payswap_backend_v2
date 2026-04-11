import { ChangeDetectorRef, Component, ElementRef, afterNextRender, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../core/constants';
import { AuthService } from '../../core/services/auth.service';
import { ConnectService } from '../connect/services/connect.service';
import { timeout, catchError, of } from 'rxjs';
import type { Transaction } from 'shared';
import type { ConnectVehicle, VehicleRCData } from '../connect/services/connect.service';
import { getVehicleTypeLabel } from '../connect/data/vehicle-types-data';
import gsap from 'gsap';

export interface DashboardAlert {
  type: 'expiry' | 'low_balance' | 'info';
  title: string;
  message: string;
  actionLabel?: string;
  actionRoute?: string;
  level: 'critical' | 'warning' | 'info';
}
import { BaseChartDirective } from 'ng2-charts';
import { DashboardWelcomeBannerComponent } from './dashboard-welcome-banner/dashboard-welcome-banner.component';
import { DashboardOverviewCardsComponent } from './dashboard-overview-cards/dashboard-overview-cards.component';
import { DashboardQuickActionsComponent } from './dashboard-quick-actions/dashboard-quick-actions.component';
import { DashboardRecentTransactionsComponent } from './dashboard-recent-transactions/dashboard-recent-transactions.component';
import { ConnectVehicleCardComponent } from '../connect/connect-vehicle-card/connect-vehicle-card.component';
import { MobilityStateStore } from '../../core/stores/mobility-state.store';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    BaseChartDirective,
    DashboardWelcomeBannerComponent,
    DashboardOverviewCardsComponent,
    DashboardQuickActionsComponent,
    DashboardRecentTransactionsComponent,
    ConnectVehicleCardComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private readonly el = inject(ElementRef);
  private api = inject(API_BACKEND_TOKEN);
  private authService = inject(AuthService);
  private connectService = inject(ConnectService);
  private cdr = inject(ChangeDetectorRef);
  private stateStore = inject(MobilityStateStore);

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
  alerts: DashboardAlert[] = [];

  // Spending Chart Data
  public spendingChartData: any = {
    labels: [],
    datasets: [
      {
        label: 'My Spending',
        data: [],
        borderColor: '#4f46e5',
        backgroundColor: 'rgba(79, 70, 229, 0.1)',
        fill: true,
        tension: 0.4
      }
    ]
  };

  public spendingChartOptions: any = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false }
    },
    scales: {
      x: { grid: { display: false } },
      y: { display: false }
    }
  };
  hasSpendingData = false;

  connectVehicles: ConnectVehicle[] = [];
  connectVehiclesLoading = true;
  connectVehiclesError: string | null = null;
  /** When set, vehicle card expands to show info panel; View more details goes to this id */
  expandedVehicleId: number | null = null;

  /** Index of vehicle shown in the dashboard card; cycle with prev/next arrows. */
  displayedVehicleIndex = 0;

  /** Vehicle currently shown on the card (for carousel). */
  get displayedVehicle(): ConnectVehicle | null {
    if (!this.connectVehicles.length) return null;
    const idx = Math.max(0, Math.min(this.displayedVehicleIndex, this.connectVehicles.length - 1));
    return this.connectVehicles[idx] ?? null;
  }

  /** Max 3 vehicles on dashboard; rest are managed via View All. */
  get dashboardVehicles(): ConnectVehicle[] {
    return this.connectVehicles.slice(0, 3);
  }

  /** Placeholder: per-vehicle connect notification count (new messages/calls). When backend adds connect_unread_count, use it. */
  getVehicleConnectNotificationCount(v: ConnectVehicle): number {
    return (v as ConnectVehicle & { connect_unread_count?: number }).connect_unread_count ?? 0;
  }

  prevVehicle(): void {
    if (this.connectVehicles.length <= 1) return;
    this.displayedVehicleIndex =
      this.displayedVehicleIndex <= 0 ? this.connectVehicles.length - 1 : this.displayedVehicleIndex - 1;
    this.cdr.markForCheck();
  }

  nextVehicle(): void {
    if (this.connectVehicles.length <= 1) return;
    this.displayedVehicleIndex =
      this.displayedVehicleIndex >= this.connectVehicles.length - 1 ? 0 : this.displayedVehicleIndex + 1;
    this.cdr.markForCheck();
  }

  /** Quick Actions – matches reference UI (Buy Voucher, Pay Bills, etc.) */
  quickActions = [
    { title: 'Buy Voucher', description: 'Use Voucher to load your fastag and Connect Recharge.', icon: 'card_giftcard', route: '/vouchers' },
    { title: 'Pay Bills', description: 'Electricity, water & more.', icon: 'receipt_long', route: '/bbps' },
    { title: 'FASTag', description: 'Recharge your FASTag.', icon: 'toll', route: '/fastag', comingSoon: true },
    { title: 'Challans', description: 'Pay traffic challans.', icon: 'gavel', route: '/challan', comingSoon: true },
    { title: 'Book Parking', description: 'Find and reserve parking.', icon: 'local_parking', route: '/parking', comingSoon: true },
    { title: 'Connect', description: 'Manage vehicles & QR.', icon: 'qr_code_2', route: '/connect' },
    { title: 'Transaction History', description: 'View payments & receipts.', icon: 'history', route: '/payment/history' },
    { title: 'Reports', description: 'Payment & voucher reports.', icon: 'assessment', route: '/payment/reports' },
  ];

  constructor() {
    afterNextRender(() => this.initAnimations());
  }

  ngOnInit() {
    this.summary = this.stateStore.dashboardSummary();
    this.connectVehicles = this.stateStore.connectVehicles();
    if (this.connectVehicles.length) {
      const primaryIdx = this.connectVehicles.findIndex((v) => v.is_primary);
      this.displayedVehicleIndex = primaryIdx >= 0 ? primaryIdx : 0;
      this.connectVehiclesLoading = false;
    }
    this.loadDashboardData();
    this.loadRecentTransactions();
    this.loadSpendingTrends();
    this.loadConnectVehicles();
  }

  setExpandedVehicle(id: number | null) {
    this.expandedVehicleId = id;
    this.cdr.markForCheck();
  }

  getExpandedVehicle(): ConnectVehicle | null {
    if (this.expandedVehicleId == null) return null;
    return this.connectVehicles.find((v) => v.id === this.expandedVehicleId) ?? null;
  }

  /** Build display rows for vehicle card from RC data (label + value). */
  getVehicleRcCardRows(rc: VehicleRCData | undefined): { label: string; value: string }[] {
    if (!rc) return [];
    const r = rc;
    const str = (v: unknown) => (v == null || v === '' ? '—' : String(v));
    const rows: { label: string; value: string }[] = [];
    rows.push({ label: 'Chassis', value: str(r.chassis) });
    rows.push({ label: 'Vehicle Category', value: str(r.vehicle_category) });
    rows.push({ label: 'Engine', value: str(r.engine) });
    rows.push({
      label: 'Usage',
      value: r.is_commercial === true ? 'Commercial' : 'Private',
    });
    rows.push({ label: 'Model', value: str(r.model) });
    rows.push({ label: 'Owner', value: str(r.owner) });
    rows.push({ label: 'PUC Upto', value: str(r.pucc_upto) });
    rows.push({ label: 'Cubic Capacity', value: str(r.vehicle_cubic_capacity) });
    rows.push({ label: 'Manufacturer', value: str(r.vehicle_manufacturer_name) });
    const insCompany = str(r.vehicle_insurance_company_name);
    const insUpto = str(r.vehicle_insurance_upto);
    rows.push({
      label: 'Insurance',
      value: insCompany && insCompany !== '—' ? `${insCompany}${insUpto !== '—' ? ` · Upto ${insUpto}` : ''}` : insUpto !== '—' ? `Upto ${insUpto}` : '—',
    });
    return rows;
  }

  getVehicleTypeLabel(typeId: string): string {
    return getVehicleTypeLabel(typeId);
  }

  /** Material icon name by vehicle type for card display. */
  getVehicleTypeIcon(typeId: string): string {
    if (typeId === 'two_wheeler') return 'two_wheeler';
    if (typeId === 'four_wheeler') return 'directions_car';
    if (typeId === 'commercial' || typeId === 'three_wheeler') return 'local_shipping';
    return 'directions_car';
  }

  /** Short RC rows for dashboard card only: Owner, Vehicle category, PUC Upto, Insurance. */
  getVehicleRcCardRowsShort(rc: VehicleRCData | undefined): { label: string; value: string }[] {
    if (!rc) return [];
    const r = rc;
    const str = (v: unknown) => (v == null || v === '' ? '—' : String(v));
    const rows: { label: string; value: string }[] = [];
    rows.push({ label: 'Owner', value: str(r.owner) });
    rows.push({ label: 'Vehicle Category', value: str(r.vehicle_category) });
    rows.push({ label: 'PUC Upto', value: str(r.pucc_upto) });
    const insCompany = str(r.vehicle_insurance_company_name);
    const insUpto = str(r.vehicle_insurance_upto);
    rows.push({
      label: 'Insurance',
      value: insCompany && insCompany !== '—' ? `${insCompany}${insUpto !== '—' ? ` · Upto ${insUpto}` : ''}` : insUpto !== '—' ? `Upto ${insUpto}` : '—',
    });
    return rows;
  }

  /**
   * Parse date string (YYYY-MM-DD or DD-MM-YYYY) to Date; return null if invalid.
   * Prioritizes strict format matching over guessing.
   */
  private parseDate(s: string): Date | null {
    if (!s || s === '—' || typeof s !== 'string') return null;
    const t = s.trim();

    // Try standard ISO date (YYYY-MM-DD)
    if (/^\d{4}-\d{2}-\d{2}$/.test(t)) {
      const d = new Date(t);
      return isNaN(d.getTime()) ? null : d;
    }

    // Try Indian format (DD-MM-YYYY or DD/MM/YYYY)
    const match = t.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    if (match) {
      const d = parseInt(match[1], 10);
      const m = parseInt(match[2], 10) - 1; // Month is 0-indexed
      const y = parseInt(match[3], 10);
      const date = new Date(y, m, d);
      // Validate that date components match (avoids 31-02-2024 becoming 02-03-2024)
      if (date.getFullYear() === y && date.getMonth() === m && date.getDate() === d) {
        return date;
      }
    }

    return null;
  }

  /** True if dateStr is valid and >= today (start of day). */
  isDateActive(dateStr: string): boolean {
    const d = this.parseDate(dateStr);
    if (!d) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    d.setHours(0, 0, 0, 0);
    return d.getTime() >= today.getTime();
  }

  /** Dashboard card: Owner + PUC (with active/expired) + Insurance (with active/expired). */
  getVehicleRcCardRowsForDashboard(rc: VehicleRCData | undefined): { label: string; value: string; status?: 'active' | 'expired' }[] {
    if (!rc) return [];
    const r = rc;
    const str = (v: unknown) => (v == null || v === '' ? '—' : String(v));
    const rows: { label: string; value: string; status?: 'active' | 'expired' }[] = [];
    rows.push({ label: 'Owner', value: str(r.owner) });
    const puccUpto = str(r.pucc_upto);
    const pucActive = puccUpto !== '—' ? this.isDateActive(puccUpto) : null;
    rows.push({
      label: 'PUC',
      value: puccUpto !== '—' ? `Upto ${puccUpto}` : '—',
      status: pucActive === null ? undefined : pucActive ? 'active' : 'expired',
    });
    const insUpto = str(r.vehicle_insurance_upto);
    const insCompany = str(r.vehicle_insurance_company_name);
    const insActive = insUpto !== '—' ? this.isDateActive(insUpto) : null;
    const insDisplay =
      insCompany && insCompany !== '—'
        ? insUpto !== '—'
          ? `${insCompany} · Upto ${insUpto}`
          : insCompany
        : insUpto !== '—'
          ? `Upto ${insUpto}`
          : '—';
    rows.push({
      label: 'Insurance',
      value: insDisplay,
      status: insActive === null ? undefined : insActive ? 'active' : 'expired',
    });
    return rows;
  }

  loadConnectVehicles() {
    this.connectVehiclesLoading = true;
    this.connectVehiclesError = null;
    this.connectService
      .getVehicles()
      .pipe(
        timeout(10000),
        catchError((err) => {
          const status = err?.status ?? err?.error?.status;
          const message =
            status === 401
              ? 'Session expired. Please log in again.'
              : err?.message?.includes('timeout')
                ? 'Request timed out. Please try again.'
                : 'Could not load vehicles. Please try again.';
          this.connectVehiclesError = message;
          return of({ results: [], meta: { user_type: 'individual', vehicle_count: 0, max_vehicles: 4, can_add_more: true } });
        })
      )
      .subscribe((res) => {
        this.connectVehicles = res?.results ?? [];
        this.stateStore.setConnectVehicles(this.connectVehicles);
        const primaryIdx = this.connectVehicles.findIndex((v) => v.is_primary);
        this.displayedVehicleIndex = primaryIdx >= 0 ? primaryIdx : 0;
        this.connectVehiclesLoading = false;
        this.cdr.detectChanges();
      });
  }

  /**
   * Generates status pills for a vehicle card (FASTag, PUC, Insurance)
   */
  getVehicleStatusPills(vehicle: ConnectVehicle): { label: string, status: 'ok' | 'warning' | 'critical' | 'info', icon: string }[] {
    const pills: { label: string, status: 'ok' | 'warning' | 'critical' | 'info', icon: string }[] = [];
    // Production Ready: No dummy data. Real checks only.

    // Check if vehicle is 2-wheeler to skip FASTag
    const type = (vehicle.vehicle_type || '').toLowerCase();
    const isTwoWheeler = type.includes('two') || type.includes('bike') || type.includes('scooter') || type.includes('motorcycle');

    // 1. FASTag Check
    if (!isTwoWheeler) {
      // In production: check wallet balance.
      // For now, consistent with "no dummy data", we only show if we have a critical status from backend (which we don't yet).
    }

    // 2. Insurance Check
    if (vehicle.rc_data?.vehicle_insurance_upto && vehicle.rc_data.vehicle_insurance_upto !== '—') {
      const expiry = this.parseDate(vehicle.rc_data.vehicle_insurance_upto);
      if (expiry) {
        const daysLeft = Math.ceil((expiry.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
        if (daysLeft < 0) {
          pills.push({ label: 'Ins. Expired', status: 'critical', icon: 'health_and_safety' });
        } else if (daysLeft <= 30) {
          pills.push({ label: 'Ins. Expiring', status: 'warning', icon: 'health_and_safety' });
        }
      }
    } else {
      // Production: If RC data is missing or empty, prompt to add insurance
      pills.push({ label: 'Add Insurance', status: 'warning', icon: 'add_moderator' });
    }

    // 3. PUC Check
    if (vehicle.rc_data?.pucc_upto && vehicle.rc_data.pucc_upto !== '—') {
      const expiry = this.parseDate(vehicle.rc_data.pucc_upto);
      if (expiry && expiry.getTime() < Date.now()) {
        pills.push({ label: 'PUC Expired', status: 'critical', icon: 'air' });
      }
    } else {
      // Production: prompt to check PUC if unknown
      pills.push({ label: 'Check PUC', status: 'info', icon: 'air' });
    }

    return pills;
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
    const vehiclesWrap = host.querySelector('.vehicles-primary-wrap');
    const analyticsSection = host.querySelector('.analytics-section');
    const sidebar = host.querySelector('.dashboard-sidebar');
    const cards = Array.from(host.querySelectorAll('.vehicle-card, .vehicle-card-carousel-item'));

    const sections = [vehiclesWrap, analyticsSection, sidebar].filter((x): x is Element => x != null);
    const validCards = cards.filter((x): x is Element => x != null);
    const targets = [...sections, ...validCards];
    if (targets.length === 0) return;

    gsap.set(targets, { opacity: 0, y: 14 });

    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
    if (sections.length > 0) {
      tl.to(sections, { opacity: 1, y: 0, duration: 0.45, stagger: 0.08 });
    }
    if (validCards.length > 0) {
      tl.to(validCards, { opacity: 1, y: 0, duration: 0.35, stagger: 0.04 }, '-=0.25');
    }
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

  private loadSpendingTrends() {
    this.api
      .getTransactionHistory({ limit: 250, status: 'success' })
      .pipe(
        timeout(7000),
        catchError(() => of({ transactions: [], total: 0 }))
      )
      .subscribe((res) => {
        const txns = Array.isArray(res?.transactions) ? res.transactions : [];
        const { labels, values, hasData } = this.buildSixMonthSpendingSeries(txns);
        this.hasSpendingData = hasData;
        this.spendingChartData = {
          ...this.spendingChartData,
          labels,
          datasets: [
            {
              ...this.spendingChartData.datasets[0],
              data: values,
            },
          ],
        };
        this.cdr.detectChanges();
      });
  }

  private buildSixMonthSpendingSeries(txns: Transaction[]): { labels: string[]; values: number[]; hasData: boolean } {
    const now = new Date();
    const monthKeys: string[] = [];
    const labels: string[] = [];
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      monthKeys.push(this.toMonthKey(d));
      labels.push(d.toLocaleString('en-IN', { month: 'short' }));
    }

    const monthTotals = new Map<string, number>(monthKeys.map((k) => [k, 0]));
    for (const txn of txns) {
      const rawTs = txn?.created_at || txn?.timestamp;
      const dt = rawTs ? new Date(rawTs) : null;
      if (!dt || Number.isNaN(dt.getTime())) continue;
      const key = this.toMonthKey(dt);
      if (!monthTotals.has(key)) continue;

      // Spending chart should show outflow. If direction is explicit credit, skip.
      if (txn.transactionTypeDirection === 'credit') continue;

      const amt = Number(txn.amount);
      if (!Number.isFinite(amt) || amt <= 0) continue;
      monthTotals.set(key, (monthTotals.get(key) ?? 0) + amt);
    }

    const values = monthKeys.map((k) => Number((monthTotals.get(k) ?? 0).toFixed(2)));
    const hasData = values.some((v) => v > 0);
    return { labels, values, hasData };
  }

  private toMonthKey(d: Date): string {
    const m = String(d.getMonth() + 1).padStart(2, '0');
    return `${d.getFullYear()}-${m}`;
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
        this.stateStore.setDashboardSummary(data);
        this.cdr.detectChanges(); // Flush view so toast-triggered CD sees consistent summary
      });
  }

}
