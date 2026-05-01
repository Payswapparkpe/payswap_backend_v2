import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ParkingSlot, ParkingLocation } from '../../../core/models/parking.model';
import { ParkingService } from '../services/parking.service';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';

interface ZoneGroup {
  id: string;
  name: string;
  floor: number;
  type: string;
  available: number;
  total: number;
  slots: ParkingSlot[];
}

@Component({
  selector: 'app-parking-slot-select',
  standalone: true,
  imports: [CommonModule, FormsModule, StepIndicatorComponent, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/parking/list" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Locations
      </a>
      <app-step-indicator [steps]="stepLabels" [currentStep]="2" />

      @if (loading) {
        <div class="loading-state">
          <div class="spinner"></div>
          <p>Loading slot map...</p>
        </div>
      } @else {
        <!-- Location summary -->
        @if (location) {
          <div class="location-summary card">
            <div class="location-info">
              <h2 class="location-name">{{ location.name }}</h2>
              <p class="location-address">
                <span class="material-icons">location_on</span>
                {{ location.address }}, {{ location.city }}
              </p>
            </div>
            <div class="slot-counts">
              <div class="count available">
                <span class="count-num">{{ totalAvailable }}</span>
                <span class="count-label">Available</span>
              </div>
              <div class="count occupied">
                <span class="count-num">{{ totalOccupied }}</span>
                <span class="count-label">Occupied</span>
              </div>
            </div>
          </div>
        }

        <!-- Vehicle Type Filter -->
        <div class="filter-row">
          <span class="filter-label">Vehicle Type:</span>
          <div class="filter-chips">
            @for (vt of vehicleTypes; track vt.value) {
              <button class="filter-chip" [class.active]="selectedVehicleType === vt.value"
                      (click)="filterByVehicleType(vt.value)">
                <span class="material-icons">{{ vt.icon }}</span>
                {{ vt.label }}
              </button>
            }
          </div>
        </div>

        <!-- Legend -->
        <div class="legend">
          <span class="legend-item"><span class="dot available"></span> Available</span>
          <span class="legend-item"><span class="dot occupied"></span> Occupied</span>
          <span class="legend-item"><span class="dot reserved"></span> Reserved</span>
          <span class="legend-item"><span class="dot selected"></span> Selected</span>
        </div>

        <!-- Zone Grids -->
        @for (zone of filteredZones; track zone.id) {
          <div class="zone-section">
            <div class="zone-header">
              <div class="zone-title">
                <span class="zone-name">{{ zone.name }}</span>
                <span class="zone-type-badge">{{ formatZoneType(zone.type) }}</span>
                @if (zone.floor !== 0) {
                  <span class="floor-badge">
                    {{ zone.floor > 0 ? 'Floor ' + zone.floor : 'Basement ' + (zone.floor * -1) }}
                  </span>
                }
              </div>
              <div class="zone-availability">
                <span class="avail-count">{{ zone.available }}/{{ zone.total }} available</span>
                <div class="mini-bar">
                  <div class="mini-bar-fill"
                       [style.width.%]="zone.total ? ((zone.total - zone.available) / zone.total) * 100 : 0"
                       [class.high]="zone.available === 0">
                  </div>
                </div>
              </div>
            </div>

            <div class="slot-grid">
              @for (slot of zone.slots; track slot.id) {
                <button
                  class="slot-cell"
                  [class.available]="slotStatus(slot) === 'available'"
                  [class.occupied]="slotStatus(slot) === 'occupied'"
                  [class.reserved]="slotStatus(slot) === 'reserved'"
                  [class.blocked]="slotStatus(slot) === 'blocked' || slotStatus(slot) === 'maintenance'"
                  [class.selected]="selectedSlot?.id === slot.id"
                  [disabled]="slotStatus(slot) !== 'available'"
                  (click)="selectSlot(slot)"
                  [title]="slotCode(slot) + ' — ' + slotStatus(slot) + ' — ₹' + slot.rate + '/hr'"
                >
                  <span class="slot-code">{{ slotCode(slot) }}</span>
                  @if (slot.features?.includes('ev_charging')) {
                    <span class="slot-ev" title="EV Charging">⚡</span>
                  }
                  @if (slot.features?.includes('covered')) {
                    <span class="slot-covered" title="Covered">⛾</span>
                  }
                </button>
              }
            </div>
          </div>
        }

        <!-- Selected Slot Summary + CTA -->
        @if (selectedSlot) {
          <div class="selected-summary">
            <div class="selected-info">
              <div class="selected-slot-code">{{ slotCode(selectedSlot) }}</div>
              <div class="selected-details">
                <span>{{ formatVehicleType(selectedSlot.vehicleType!) }}</span>
                <span class="sep">·</span>
                <span>₹{{ selectedSlot.rate }}/hr</span>
                @if (selectedSlot.features?.includes('covered')) {
                  <span class="sep">·</span>
                  <span>Covered</span>
                }
              </div>
            </div>
            <button class="btn-primary proceed-btn" (click)="proceedToBooking()">
              Book this Slot →
            </button>
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 1.5rem; max-width: 1000px; margin: 0 auto; min-height: 100vh; background: var(--background); }
    .back-link { display: inline-flex; align-items: center; gap: 0.5rem; color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem; }
    .back-link .material-icons { font-size: 20px; }

    .loading-state { display: flex; flex-direction: column; align-items: center; padding: 4rem 0; gap: 1rem; }

    .location-summary {
      display: flex; justify-content: space-between; align-items: center;
      padding: 1rem 1.25rem; margin-bottom: 1.25rem;
    }
    .location-name { font-size: 1.1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.25rem; }
    .location-address { display: flex; align-items: center; gap: 0.25rem; font-size: 0.8rem; color: var(--text-secondary); }
    .location-address .material-icons { font-size: 14px; }
    .slot-counts { display: flex; gap: 1.5rem; }
    .count { text-align: center; }
    .count-num { display: block; font-size: 1.5rem; font-weight: 700; }
    .count-label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
    .count.available .count-num { color: var(--success); }
    .count.occupied .count-num { color: var(--error); }

    .filter-row { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem; flex-wrap: wrap; }
    .filter-label { font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); }
    .filter-chips { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .filter-chip {
      display: flex; align-items: center; gap: 0.375rem;
      padding: 0.375rem 0.875rem; border-radius: var(--radius-full);
      border: 1px solid var(--border); background: transparent;
      font-size: 0.8rem; cursor: pointer; color: var(--text-secondary);
      .material-icons { font-size: 16px; }
      &.active { background: var(--primary-600); color: white; border-color: var(--primary-600); }
    }

    .legend { display: flex; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
    .legend-item { display: flex; align-items: center; gap: 0.375rem; font-size: 0.75rem; color: var(--text-secondary); }
    .dot { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
    .dot.available { background: #dcfce7; border: 1.5px solid #16a34a; }
    .dot.occupied { background: #fee2e2; border: 1.5px solid #dc2626; }
    .dot.reserved { background: #fef3c7; border: 1.5px solid #d97706; }
    .dot.selected { background: var(--primary-600); border: 1.5px solid var(--primary-700); }

    .zone-section { margin-bottom: 1.75rem; }
    .zone-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem; }
    .zone-title { display: flex; align-items: center; gap: 0.5rem; }
    .zone-name { font-size: 0.95rem; font-weight: 600; color: var(--text-primary); }
    .zone-type-badge { font-size: 0.7rem; background: var(--primary-50); color: var(--primary-700); padding: 0.15rem 0.5rem; border-radius: 99px; font-weight: 500; }
    .floor-badge { font-size: 0.7rem; background: var(--border); color: var(--text-secondary); padding: 0.15rem 0.5rem; border-radius: 99px; }
    .zone-availability { display: flex; align-items: center; gap: 0.5rem; }
    .avail-count { font-size: 0.8rem; color: var(--text-secondary); }
    .mini-bar { width: 60px; height: 5px; background: #e5e7eb; border-radius: 99px; overflow: hidden; }
    .mini-bar-fill { height: 100%; background: #22c55e; border-radius: 99px; &.high { background: #ef4444; } }

    .slot-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
      gap: 6px;
    }

    .slot-cell {
      aspect-ratio: 1;
      border-radius: 8px;
      border: 1.5px solid transparent;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 1px; cursor: pointer; transition: all 0.15s; font-size: 0.7rem;
      &.available { background: #dcfce7; border-color: #16a34a; color: #15803d; cursor: pointer; }
      &.available:hover { background: #bbf7d0; transform: scale(1.05); }
      &.occupied { background: #fee2e2; border-color: #dc2626; color: #b91c1c; cursor: not-allowed; }
      &.reserved { background: #fef3c7; border-color: #d97706; color: #b45309; cursor: not-allowed; }
      &.blocked { background: #f3f4f6; border-color: #d1d5db; color: #9ca3af; cursor: not-allowed; }
      &.selected { background: var(--primary-600) !important; border-color: var(--primary-700) !important; color: white !important; transform: scale(1.05); }
      &:disabled { cursor: not-allowed; }
    }
    .slot-code { font-weight: 600; font-size: 0.7rem; line-height: 1; }
    .slot-ev, .slot-covered { font-size: 0.65rem; line-height: 1; }

    .selected-summary {
      position: sticky; bottom: 1rem; left: 0; right: 0;
      background: white; border: 1.5px solid var(--primary-200);
      border-radius: var(--radius-xl); padding: 1rem 1.25rem;
      display: flex; justify-content: space-between; align-items: center;
      box-shadow: 0 -4px 24px rgba(0,74,173,0.12); margin-top: 1.5rem;
      gap: 1rem;
    }
    .selected-slot-code { font-size: 1.5rem; font-weight: 700; color: var(--primary-600); margin-bottom: 0.125rem; }
    .selected-details { font-size: 0.8rem; color: var(--text-secondary); display: flex; gap: 0.375rem; }
    .sep { color: var(--text-muted); }
    .proceed-btn { white-space: nowrap; }
    .btn-primary {
      padding: 0.75rem 1.5rem; background: var(--primary-600); color: white;
      border: none; border-radius: var(--radius-lg); font-weight: 600;
      font-size: 0.9rem; cursor: pointer;
      &:hover { background: var(--primary-700); }
    }
  `],
})
export class ParkingSlotSelectComponent implements OnInit {
  readonly stepLabels = ['Location', 'Slot', 'Book'];

  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private parkingService = inject(ParkingService);

  locationId = '';
  location?: ParkingLocation;
  zones: ZoneGroup[] = [];
  filteredZones: ZoneGroup[] = [];
  loading = true;
  selectedSlot?: ParkingSlot;
  selectedVehicleType = 'all';

  totalAvailable = 0;
  totalOccupied = 0;

  vehicleTypes = [
    { value: 'all', label: 'All', icon: 'grid_view' },
    { value: 'two_wheeler', label: '2W', icon: 'two_wheeler' },
    { value: 'four_wheeler', label: '4W', icon: 'directions_car' },
    { value: 'ev', label: 'EV', icon: 'electric_car' },
  ];

  ngOnInit() {
    this.locationId = this.route.snapshot.paramMap.get('locationId') || '';
    this.loadSlots();
    this.loadLocation();
  }

  loadLocation() {
    this.parkingService.getLocations().subscribe({
      next: (locs) => {
        this.location = locs.find((l) => l.id === this.locationId);
      },
    });
  }

  loadSlots() {
    const vt = this.selectedVehicleType === 'all' ? undefined : this.selectedVehicleType;
    this.parkingService.getSlots(this.locationId, vt).subscribe({
      next: (slots) => {
        this.buildZones(slots);
        this.totalAvailable = slots.filter((s) => this.slotStatus(s) === 'available').length;
        this.totalOccupied = slots.filter((s) => this.slotStatus(s) === 'occupied').length;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  buildZones(slots: (ParkingSlot & { zoneId?: string; zoneName?: string; floorLevel?: number; zoneType?: string })[]) {
    const zoneMap = new Map<string, ZoneGroup>();
    for (const s of slots) {
      const zid = (s as any).zoneId ?? 'default';
      if (!zoneMap.has(zid)) {
        zoneMap.set(zid, {
          id: zid,
          name: (s as any).zoneName ?? 'Parking',
          floor: (s as any).floorLevel ?? 0,
          type: (s as any).zoneType ?? '4W',
          available: 0, total: 0,
          slots: [],
        });
      }
      const z = zoneMap.get(zid)!;
      z.slots.push(s);
      z.total++;
      if (this.slotStatus(s) === 'available') z.available++;
    }
    this.zones = [...zoneMap.values()].sort((a, b) => a.floor - b.floor || a.name.localeCompare(b.name));
    this.filteredZones = this.zones;
  }

  filterByVehicleType(vt: string) {
    this.selectedVehicleType = vt;
    this.selectedSlot = undefined;
    if (vt === 'all') {
      this.filteredZones = this.zones;
    } else {
      this.filteredZones = this.zones.map((z) => ({
        ...z,
        slots: z.slots.filter((s) => s.vehicleType === vt),
      })).filter((z) => z.slots.length > 0);
    }
  }

  selectSlot(slot: ParkingSlot) {
    if (this.slotStatus(slot) !== 'available') return;
    this.selectedSlot = this.selectedSlot?.id === slot.id ? undefined : slot;
  }

  proceedToBooking() {
    if (!this.selectedSlot) return;
    this.router.navigate(['/parking/booking', this.selectedSlot.id], {
      state: { slot: this.selectedSlot, locationId: this.locationId },
    });
  }

  formatVehicleType(vt: string): string {
    return vt.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  formatZoneType(type: string): string {
    const map: Record<string, string> = {
      '2W': 'Two Wheeler', '4W': 'Four Wheeler', EV: 'EV', VIP: 'VIP',
      HANDICAP: 'Handicap', HEAVY: 'Heavy Vehicle',
    };
    return map[type] ?? type;
  }

  slotStatus(slot: ParkingSlot): string {
    if (slot.status) return slot.status;
    return slot.available ? 'available' : 'occupied';
  }

  slotCode(slot: ParkingSlot): string {
    return slot.slot_code || slot.code;
  }
}
