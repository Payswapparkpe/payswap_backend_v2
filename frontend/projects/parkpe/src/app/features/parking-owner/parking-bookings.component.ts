import { CommonModule } from '@angular/common';
import { Component, computed, ElementRef, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ParkingService } from '../parking/services/parking.service';

@Component({
  selector: 'app-parking-bookings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './parking-bookings.component.html',
  styleUrl: './parking-bookings.component.scss',
})
export class ParkingBookingsComponent implements OnInit {
  private parking = inject(ParkingService);
  private host = inject(ElementRef<HTMLElement>);

  locations = signal<{ id: number; name: string }[]>([]);
  locationId = signal('');
  date = signal('');
  statusFilter = signal<string>('all');
  bookings = signal<Record<string, unknown>[]>([]);
  loading = signal(false);
  error = signal('');
  actionBusy = signal<string | null>(null);

  readonly filteredBookings = computed(() => {
    const f = this.statusFilter();
    const list = this.bookings();
    if (f === 'all') return list;
    return list.filter((b) => String(b['status'] ?? '').toLowerCase() === f.toLowerCase());
  });

  readonly summaryCounts = computed(() => {
    const list = this.bookings();
    const lower = (s: unknown) => String(s ?? '').toLowerCase();
    return {
      total: list.length,
      confirmed: list.filter((b) => lower(b['status']).includes('confirm')).length,
      active: list.filter((b) => lower(b['status']).includes('active')).length,
      completed: list.filter((b) => lower(b['status']).includes('complet')).length,
      cancelled: list.filter((b) => lower(b['status']).includes('cancel')).length,
    };
  });

  readonly chipFilters: { id: string; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'confirmed', label: 'Confirmed' },
    { id: 'active', label: 'Active' },
    { id: 'completed', label: 'Completed' },
    { id: 'cancelled', label: 'Cancelled' },
  ];

  ngOnInit(): void {
    this.parking.getOwnerLocations().subscribe({
      next: (res: { locations?: { id: number; name: string }[] }) => {
        const locs = res?.locations ?? [];
        this.locations.set(locs.map((l) => ({ id: l.id, name: l.name ?? `Location ${l.id}` })));
        const first = locs[0];
        if (first) {
          this.locationId.set(String(first.id));
          this.load();
        }
      },
    });
  }

  load(): void {
    const lid = this.locationId();
    if (!lid) return;
    this.loading.set(true);
    this.error.set('');
    this.parking
      .getOwnerBookings(lid, this.date() || undefined, undefined)
      .subscribe({
        next: (res: { bookings?: Record<string, unknown>[] }) => {
          this.loading.set(false);
          this.bookings.set(res?.bookings ?? []);
          setTimeout(() => this.staggerCards(), 0);
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail || 'Failed to load bookings');
        },
      });
  }

  setChip(id: string): void {
    this.statusFilter.set(id);
  }

  bookingRef(b: Record<string, unknown>): string {
    return String(b['bookingReference'] ?? b['booking_reference'] ?? '—');
  }

  vehicle(b: Record<string, unknown>): string {
    return String(b['vehicleNumber'] ?? b['vehicle_number'] ?? '—');
  }

  statusLabel(b: Record<string, unknown>): string {
    return String(b['status'] ?? '—');
  }

  amount(b: Record<string, unknown>): number | null {
    const v = b['amount'];
    if (v == null) return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  slotCode(b: Record<string, unknown>): string {
    return String(b['slotCode'] ?? b['slot_code'] ?? '—');
  }

  verifyEntry(b: Record<string, unknown>): void {
    const ref = this.bookingRef(b);
    if (!ref || ref === '—') return;
    this.actionBusy.set(ref);
    this.parking.recordEntry(ref).subscribe({
      next: () => this.actionBusy.set(null),
      error: () => this.actionBusy.set(null),
    });
  }

  verifyExit(b: Record<string, unknown>): void {
    const ref = this.bookingRef(b);
    if (!ref || ref === '—') return;
    this.actionBusy.set(ref);
    this.parking.recordExit(ref).subscribe({
      next: () => this.actionBusy.set(null),
      error: () => this.actionBusy.set(null),
    });
  }

  statusBadgeClass(b: Record<string, unknown>): string {
    const s = this.statusLabel(b).toLowerCase();
    if (s.includes('cancel')) return 'bg-rose-50 text-rose-700 ring-rose-100';
    if (s.includes('complet')) return 'bg-slate-100 text-slate-700 ring-slate-200';
    if (s.includes('active')) return 'bg-emerald-50 text-emerald-700 ring-emerald-100';
    if (s.includes('confirm')) return 'bg-indigo-50 text-indigo-700 ring-indigo-100';
    return 'bg-amber-50 text-amber-800 ring-amber-100';
  }

  private staggerCards(): void {
    const root = this.host.nativeElement;
    const cards = Array.from(root.querySelectorAll('[data-booking-card]')) as HTMLElement[];
    cards.forEach((el: HTMLElement, i: number) => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(12px)';
      el.style.transition = 'none';
      requestAnimationFrame(() => {
        setTimeout(() => {
          el.style.transition = 'opacity 300ms ease, transform 300ms ease';
          el.style.opacity = '1';
          el.style.transform = 'translateY(0)';
        }, i * 50);
      });
    });
  }
}
