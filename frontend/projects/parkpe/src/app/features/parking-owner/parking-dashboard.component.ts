import { CommonModule, DecimalPipe, TitleCasePipe } from '@angular/common';
import {
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import {
  animate,
  state,
  style,
  transition,
  trigger,
} from '@angular/animations';
import { RouterLink } from '@angular/router';
import { KENDO_BUTTONS } from '@progress/kendo-angular-buttons';
import { KENDO_CHARTS } from '@progress/kendo-angular-charts';
import { KENDO_GAUGES } from '@progress/kendo-angular-gauges';
import { KENDO_INDICATORS } from '@progress/kendo-angular-indicators';
import { KENDO_LISTVIEW } from '@progress/kendo-angular-listview';
import { AuthService } from '../../core/services/auth.service';
import { ParkingService } from '../parking/services/parking.service';

interface LocationSummary {
  id: number;
  name: string;
  address: string;
  city: string;
  role: 'owner' | 'manager' | 'attendant';
  totalSlots: number;
  availableSlots: number;
  occupiedSlots: number;
  reservedSlots: number;
  activeSessions: number;
  todayRevenue: number;
  todayBookings: number;
  occupancyPct: number;
}

export interface ActivityItem {
  id: string;
  type: 'entry' | 'exit' | 'booking' | 'overstay';
  label: string;
  vehicle: string;
  time: string;
  amount?: number;
}

const EASE = 'cubic-bezier(0.4, 0.0, 0.2, 1)';

@Component({
  selector: 'app-parking-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    DecimalPipe,
    TitleCasePipe,
    KENDO_BUTTONS,
    KENDO_CHARTS,
    KENDO_GAUGES,
    KENDO_INDICATORS,
    KENDO_LISTVIEW,
  ],
  templateUrl: './parking-dashboard.component.html',
  styleUrl: './parking-dashboard.component.scss',
  animations: [
    /** Float panel expand / collapse. */
    trigger('floatMenu', [
      state('closed', style({ height: '0px', opacity: 0, pointerEvents: 'none' })),
      state('open', style({ height: '*', opacity: 1, pointerEvents: 'auto' })),
      transition('closed => open', [animate(`300ms ${EASE}`)]),
      transition('open => closed', [animate(`200ms ${EASE}`)]),
    ]),

    /** FAB icon rotation (+45° when menu open). */
    trigger('fabRotate', [
      state('closed', style({ transform: 'rotate(0deg)' })),
      state('open', style({ transform: 'rotate(45deg)' })),
      transition('* <=> *', [animate(`300ms ${EASE}`)]),
    ]),
  ],
})
export class ParkingDashboardComponent implements OnInit, OnDestroy {
  private parkingService = inject(ParkingService);
  private authService = inject(AuthService);
  private host = inject(ElementRef<HTMLElement>);

  today = new Date();

  locations = signal<LocationSummary[]>([]);
  loading = signal(true);
  loadError = signal(false);
  liveActivity = signal<ActivityItem[]>([]);
  floatOpen = signal(false);

  canViewRevenue = false;
  canManageTeam = false;

  revenueTrendPct = signal(12);
  fastTagPct = signal(72);
  deviceOnline = signal(true);

  private revCountupRaf?: number;

  // ── Computed aggregates ──────────────────────────────────────────────────

  readonly totalSlots = computed(() =>
    this.locations().reduce((s, l) => s + l.totalSlots, 0),
  );
  readonly totalOccupied = computed(() =>
    this.locations().reduce((s, l) => s + l.occupiedSlots, 0),
  );
  readonly totalAvailable = computed(() =>
    this.locations().reduce((s, l) => s + l.availableSlots, 0),
  );
  readonly totalRevenue = computed(() =>
    this.locations().reduce((s, l) => s + l.todayRevenue, 0),
  );
  readonly totalSessions = computed(() =>
    this.locations().reduce((s, l) => s + l.activeSessions, 0),
  );
  readonly aggregateOccupancyPct = computed(() => {
    const t = this.totalSlots();
    return t > 0 ? Math.round((this.totalOccupied() / t) * 100) : 0;
  });
  readonly overstayCount = computed(() =>
    this.liveActivity().filter((a) => a.type === 'overstay').length,
  );
  readonly showRevenueTrend = computed(() => this.totalRevenue() > 0);
  readonly gaugeColor = computed(() => {
    const p = this.aggregateOccupancyPct();
    if (p > 80) return '#e11d48';
    if (p > 50) return '#f59e0b';
    return '#004aad';
  });
  readonly fastagSeries = computed(() => [
    { category: 'FASTag', value: this.fastTagPct(), color: '#7c3aed' },
    { category: 'Manual', value: 100 - this.fastTagPct(), color: '#e2e8f0' },
  ]);
  readonly sparklinePoints = computed(() => {
    const rev = this.totalRevenue();
    if (rev <= 0) return '4,20 16,20 28,20 40,20 52,20 64,20 76,20 88,20';
    const base = Math.max(rev * 0.65, 1000);
    return Array.from({ length: 8 }, (_, i) => {
      const v = base + (rev - base) * (i / 7) + (i % 3) * (rev * 0.02);
      const x = 4 + (i / 7) * 88;
      const y = 36 - Math.min(32, (v / Math.max(rev, 1)) * 28);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  });

  // ── Lifecycle ────────────────────────────────────────────────────────────

  ngOnInit(): void {
    const role = this.authService.getParkingRole();
    this.canViewRevenue = role === 'owner' || role === 'manager';
    this.canManageTeam = role === 'owner';
    this.loadDashboard();
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.revCountupRaf ?? 0);
  }

  // ── Data ─────────────────────────────────────────────────────────────────

  loadDashboard(): void {
    this.loading.set(true);
    this.loadError.set(false);
    this.parkingService.getOwnerLocations().subscribe({
      next: (data: unknown) => {
        const raw = data as { locations?: unknown[] } | unknown[];
        const locs: unknown[] = Array.isArray(raw)
          ? raw
          : (raw as { locations?: unknown[] })?.locations ?? [];
        const mapped = locs.map((loc) =>
          this.mapLocation(loc as Record<string, unknown>),
        );
        this.locations.set(mapped);
        this.loading.set(false);

        if (mapped.length) {
          const seed = mapped.reduce((acc, l) => acc + l.id, 0);
          this.fastTagPct.set(58 + (seed % 30));
          this.deviceOnline.set(true);
          this.seedDemoFeedIfEmpty();
        } else {
          this.liveActivity.set([]);
        }
        setTimeout(() => this.afterDataPaint(), 80);
      },
      error: () => {
        this.loading.set(false);
        this.loadError.set(true);
        this.locations.set([]);
      },
    });
  }

  refresh(): void {
    this.loadDashboard();
  }

  // ── Interactions ─────────────────────────────────────────────────────────

  toggleFloat(): void {
    this.floatOpen.update((v) => !v);
  }

  gateAction(gate: 1 | 2): void {
    // Placeholder — wire to IoT / backend when available
    void gate;
  }

  // ── DOM animations (gauge, countup, bars) ────────────────────────────────

  private afterDataPaint(): void {
    this.animateRevenueCountUp();
  }

  private animateRevenueCountUp(): void {
    cancelAnimationFrame(this.revCountupRaf ?? 0);
    const el = this.host.nativeElement.querySelector(
      '[data-rev-counter]',
    ) as HTMLElement | null;
    if (!el) return;
    const target = this.totalRevenue();
    const duration = 1300;
    const startTime = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      el.textContent = `₹${Math.round(eased * target).toLocaleString('en-IN')}`;
      if (progress < 1) this.revCountupRaf = requestAnimationFrame(tick);
    };
    this.revCountupRaf = requestAnimationFrame(tick);
  }

  // ── Seed data ────────────────────────────────────────────────────────────

  private seedDemoFeedIfEmpty(): void {
    if (this.liveActivity().length) return;
    const t = Date.now();
    this.liveActivity.set([
      {
        id: `demo-${t}-1`,
        type: 'entry',
        label: 'Entry — Main gate',
        vehicle: 'MH 12 AB 1234',
        time: this.fmtTime(t - 180_000),
      },
      {
        id: `demo-${t}-2`,
        type: 'exit',
        label: 'Exit — FASTag lane',
        vehicle: 'DL 8C 9011',
        time: this.fmtTime(t - 120_000),
        amount: 120,
      },
      {
        id: `demo-${t}-3`,
        type: 'entry',
        label: 'Entry — Manual',
        vehicle: 'KA 01 MN 4455',
        time: this.fmtTime(t - 60_000),
      },
      {
        id: `demo-${t}-4`,
        type: 'booking',
        label: 'Pre-booked arrival',
        vehicle: 'TS 09 XY 7788',
        time: this.fmtTime(t - 30_000),
      },
      {
        id: `demo-${t}-5`,
        type: 'overstay',
        label: 'Overstay — action required',
        vehicle: 'GJ 05 A 1122',
        time: this.fmtTime(t - 10_000),
      },
    ]);
  }

  private fmtTime(ts: number): string {
    return new Date(ts).toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  private mapLocation(loc: Record<string, unknown>): LocationSummary {
    const reported = Number(loc['total_slots'] ?? loc['totalSlots'] ?? 0);
    const avail = Number(loc['available_slots'] ?? loc['availableSlots'] ?? 0);
    const occ = Number(loc['occupied_slots'] ?? loc['occupiedSlots'] ?? 0);
    const res = Number(loc['reserved_slots'] ?? loc['reservedSlots'] ?? 0);
    // API sometimes sends total_slots=0 while parts sum correctly
    const total = Math.max(reported, occ + avail + res);
    const pct = total > 0 ? Math.round((occ / total) * 100) : 0;
    const roleRaw = String(loc['role'] ?? 'attendant');
    const role: 'owner' | 'manager' | 'attendant' =
      roleRaw === 'owner' || roleRaw === 'manager' || roleRaw === 'attendant'
        ? roleRaw
        : 'attendant';
    return {
      id: Number(loc['id']),
      name: String(loc['name'] ?? ''),
      address: String(loc['address'] ?? ''),
      city: String(loc['city'] ?? ''),
      role,
      totalSlots: total,
      availableSlots: avail,
      occupiedSlots: occ,
      reservedSlots: res,
      activeSessions: Number(loc['active_sessions'] ?? loc['activeSessions'] ?? 0),
      todayRevenue: Number(loc['today_revenue'] ?? loc['todayRevenue'] ?? 0),
      todayBookings: Number(loc['today_bookings'] ?? loc['todayBookings'] ?? 0),
      occupancyPct: pct,
    };
  }
}
