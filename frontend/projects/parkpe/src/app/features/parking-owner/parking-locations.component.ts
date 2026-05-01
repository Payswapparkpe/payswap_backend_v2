import { CommonModule } from '@angular/common';
import { Component, computed, ElementRef, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ParkingService } from '../parking/services/parking.service';
import { ParkingSlot } from '../../core/models/parking.model';

type SlotFilter = 'all' | 'free' | 'occupied' | 'reserved';

@Component({
  selector: 'app-parking-locations',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './parking-locations.component.html',
  styleUrl: './parking-locations.component.scss',
})
export class ParkingLocationsComponent implements OnInit {
  private parking = inject(ParkingService);
  private host = inject(ElementRef<HTMLElement>);

  locations = signal<{ id: string; name: string }[]>([]);
  selectedLocationId = signal('');
  slots = signal<ParkingSlot[]>([]);
  filter = signal<SlotFilter>('all');
  loading = signal(false);
  error = signal('');
  hoverSlot = signal<ParkingSlot | null>(null);

  readonly slotCounts = computed(() => {
    const list = this.slots();
    let free = 0,
      occ = 0,
      res = 0;
    for (const s of list) {
      const k = this.kind(s);
      if (k === 'free') free++;
      else if (k === 'occupied') occ++;
      else if (k === 'reserved') res++;
    }
    return { free, occupied: occ, reserved: res, total: list.length };
  });

  readonly filteredSlots = computed(() => {
    const f = this.filter();
    if (f === 'all') return this.slots();
    return this.slots().filter((s) => this.kind(s) === f);
  });

  readonly chipFilters: { id: SlotFilter; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'free', label: 'Free' },
    { id: 'occupied', label: 'Occupied' },
    { id: 'reserved', label: 'Reserved' },
  ];

  ngOnInit(): void {
    this.parking.getOwnerLocations().subscribe({
      next: (res: { locations?: { id: number; name: string }[] }) => {
        const locs = res?.locations ?? [];
        this.locations.set(locs.map((l) => ({ id: String(l.id), name: l.name ?? `Location ${l.id}` })));
        const first = locs[0];
        if (first) {
          this.selectedLocationId.set(String(first.id));
          this.loadSlots();
        }
      },
    });
  }

  setLocation(id: string): void {
    this.selectedLocationId.set(id);
    this.loadSlots();
  }

  setFilter(f: SlotFilter): void {
    this.filter.set(f);
  }

  kind(s: ParkingSlot): SlotFilter {
    const st = (s.status || '').toLowerCase();
    if (st.includes('reserv')) return 'reserved';
    if (st.includes('occup') || st.includes('full')) return 'occupied';
    if (s.available === true || st === 'available' || !st) return 'free';
    return 'occupied';
  }

  slotClasses(s: ParkingSlot): string {
    const k = this.kind(s);
    if (k === 'free')
      return 'bg-emerald-50 ring-emerald-200 text-emerald-900 hover:bg-emerald-100';
    if (k === 'reserved')
      return 'bg-amber-50 ring-amber-200 text-amber-900 hover:bg-amber-100';
    return 'bg-rose-50 ring-rose-200 text-rose-900 hover:bg-rose-100';
  }

  loadSlots(): void {
    const id = this.selectedLocationId();
    if (!id) return;
    this.loading.set(true);
    this.error.set('');
    this.parking.getLocationSlots(id).subscribe({
      next: (rows) => {
        this.loading.set(false);
        this.slots.set(rows || []);
        setTimeout(() => this.staggerSlots(), 0);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(err?.error?.detail || 'Failed to load slots');
      },
    });
  }

  onSlotEnter(ev: Event, s: ParkingSlot): void {
    this.hoverSlot.set(s);
    (ev.currentTarget as HTMLElement).style.transform = 'scale(1.06)';
  }

  onSlotLeave(ev: Event): void {
    this.hoverSlot.set(null);
    (ev.currentTarget as HTMLElement).style.transform = 'scale(1)';
  }

  code(s: ParkingSlot): string {
    return s.code || s.slot_code || '—';
  }

  private staggerSlots(): void {
    const root = this.host.nativeElement;
    const cells = Array.from(root.querySelectorAll('[data-slot-cell]')) as HTMLElement[];
    cells.forEach((el: HTMLElement, i: number) => {
      el.style.opacity = '0';
      el.style.transform = 'scale(0.92)';
      el.style.transition = `opacity 250ms ease ${i * 15}ms, transform 250ms ease ${i * 15}ms`;
      requestAnimationFrame(() => {
        el.style.opacity = '1';
        el.style.transform = 'scale(1)';
      });
    });
  }
}
