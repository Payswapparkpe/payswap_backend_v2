import { CommonModule } from '@angular/common';
import { Component, ElementRef, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ParkingService } from '../parking/services/parking.service';

interface KpiSet {
  total: number;
  today: number;
  avgDay: number;
  peak: number;
}

interface DailyPoint {
  label: string;
  value: number;
}

interface LocRow {
  name: string;
  amount: number;
}

@Component({
  selector: 'app-parking-revenue',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './parking-revenue.component.html',
  styleUrl: './parking-revenue.component.scss',
})
export class ParkingRevenueComponent implements OnInit {
  private parking = inject(ParkingService);
  private host = inject(ElementRef<HTMLElement>);

  locationId = signal('');
  days = signal(30);
  periodChips: { days: number; label: string }[] = [
    { days: 7, label: '7d' },
    { days: 30, label: '30d' },
    { days: 90, label: '90d' },
  ];
  locations = signal<{ id: number; name: string }[]>([]);
  rawSummary = signal<unknown>(null);
  loading = signal(false);
  error = signal('');
  kpis = signal<KpiSet>({ total: 0, today: 0, avgDay: 0, peak: 0 });
  daily = signal<DailyPoint[]>([]);
  locBreakdown = signal<LocRow[]>([]);

  ngOnInit(): void {
    this.parking.getOwnerLocations().subscribe({
      next: (res: { locations?: { id: number; name: string }[] }) => {
        const locs = res?.locations ?? [];
        this.locations.set(locs.map((l) => ({ id: l.id, name: l.name ?? `Loc ${l.id}` })));
        const first = locs[0];
        if (first) {
          this.locationId.set(String(first.id));
          this.load();
        }
      },
    });
  }

  setDays(d: number): void {
    this.days.set(d);
    this.load();
  }

  load(): void {
    const lid = this.locationId();
    if (!lid) return;
    this.loading.set(true);
    this.error.set('');
    this.parking.getOwnerRevenue(lid, this.days()).subscribe({
      next: (res) => {
        this.loading.set(false);
        this.rawSummary.set(res);
        this.parseSummary(res);
        setTimeout(() => {
          this.animateKpis();
          this.animateBars();
        }, 0);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(err?.error?.detail || 'Failed to load revenue');
      },
    });
  }

  onLocationChange(id: string): void {
    this.locationId.set(id);
    this.load();
  }

  private parseSummary(res: unknown): void {
    const o = (res && typeof res === 'object' ? res : {}) as Record<string, unknown>;
    const n = (v: unknown) => (v == null ? 0 : Number(v)) || 0;

    const total = n(o['total_revenue'] ?? o['total'] ?? o['revenue']);
    const today = n(o['today_revenue'] ?? o['today']);
    const days = this.days() || 30;
    const avgDay = days > 0 ? total / days : 0;
    const peak = n(o['peak_day_revenue'] ?? o['peak']);

    let dailyPts: DailyPoint[] = [];
    const byDay = o['by_day'] ?? o['daily'] ?? o['series'];
    if (Array.isArray(byDay) && byDay.length) {
      dailyPts = byDay.map((row: unknown, i: number) => {
        const r = row as Record<string, unknown>;
        const label = String(r['date'] ?? r['day'] ?? r['label'] ?? i + 1);
        const value = n(r['amount'] ?? r['revenue'] ?? r['value']);
        return { label, value };
      });
    } else {
      const segments = Math.min(days, 14);
      for (let i = 0; i < segments; i++) {
        const v = Math.max(0, Math.round((total / segments) * (0.6 + Math.sin(i) * 0.4)));
        dailyPts.push({ label: `D${i + 1}`, value: v });
      }
    }

    let locRows: LocRow[] = [];
    const byLoc = o['by_location'] ?? o['locations'];
    if (Array.isArray(byLoc)) {
      locRows = byLoc.map((row: unknown) => {
        const r = row as Record<string, unknown>;
        return {
          name: String(r['name'] ?? r['location_name'] ?? 'Location'),
          amount: n(r['amount'] ?? r['revenue']),
        };
      });
    } else if (total > 0) {
      locRows = [{ name: 'This location', amount: total }];
    }

    this.kpis.set({
      total: total || today,
      today: today || Math.round(total / Math.max(days, 1)),
      avgDay: avgDay || 0,
      peak: peak || Math.max(...dailyPts.map((d) => d.value), 0),
    });
    this.daily.set(dailyPts);
    this.locBreakdown.set(locRows);
  }

  maxDaily(): number {
    const pts = this.daily();
    if (!pts.length) return 1;
    return Math.max(...pts.map((p) => p.value), 1);
  }

  private animateKpis(): void {
    const els = Array.from(this.host.nativeElement.querySelectorAll('[data-kpi-val]')) as HTMLElement[];
    const k = this.kpis();
    const targets = [k.total, k.today, k.avgDay, k.peak];
    els.forEach((node: HTMLElement, i: number) => {
      const target = targets[i] ?? 0;
      const duration = 1100;
      const start = performance.now();
      const tick = (now: number) => {
        const p = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - p, 3);
        node.textContent = `₹${Math.round(eased * target).toLocaleString('en-IN')}`;
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }

  private animateBars(): void {
    const bars = Array.from(this.host.nativeElement.querySelectorAll('[data-rev-bar]')) as HTMLElement[];
    bars.forEach((el: HTMLElement, i: number) => {
      el.style.transform = 'scaleY(0)';
      el.style.transformOrigin = 'bottom';
      el.style.transition = 'none';
      requestAnimationFrame(() => {
        setTimeout(() => {
          el.style.transition = 'transform 400ms cubic-bezier(0.4,0,0.2,1)';
          el.style.transform = 'scaleY(1)';
        }, i * 40);
      });
    });
  }
}
