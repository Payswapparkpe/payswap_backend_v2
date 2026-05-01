import {
  AfterViewInit,
  Component,
  ElementRef,
  inject,
  NgZone,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ParkingLocation } from '../../../core/models/parking.model';
import { ParkingService } from '../services/parking.service';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';

declare const mappls: any;

@Component({
  selector: 'app-parking-list',
  standalone: true,
  imports: [CommonModule, FormsModule, StepIndicatorComponent, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <app-step-indicator [steps]="stepLabels" [currentStep]="1" />
      <header class="feature-header">
        <h1 class="feature-title">Find Parking</h1>
        <p class="feature-subtitle">Book parking near you — pay with Parkpe Voucher</p>
      </header>

      <!-- Search Bar -->
      <div class="search-bar">
        <span class="material-icons search-icon">search</span>
        <input
          type="text"
          [(ngModel)]="searchQuery"
          (ngModelChange)="onSearchChange()"
          placeholder="Search by city or location name..."
          class="search-input"
        />
        <button class="location-btn" (click)="useMyLocation()" title="Use my location">
          <span class="material-icons">my_location</span>
        </button>
      </div>

      <!-- View Toggle -->
      <div class="view-toggle">
        <button [class.active]="viewMode === 'list'" (click)="viewMode = 'list'">
          <span class="material-icons">view_list</span> List
        </button>
        <button [class.active]="viewMode === 'map'" (click)="viewMode = 'map'; initMap()">
          <span class="material-icons">map</span> Map
        </button>
      </div>

      @if (loading) {
        <div class="loading-state">
          <div class="spinner"></div>
          <p>Finding parking locations...</p>
        </div>
      } @else {

        <!-- Map View -->
        @if (viewMode === 'map') {
          <div #mapContainer id="parking-map" class="map-container"></div>
        }

        <!-- List View -->
        @if (viewMode === 'list') {
          @if (filteredLocations.length === 0) {
            <div class="empty-state">
              <span class="material-icons">local_parking</span>
              <p>No parking locations found</p>
              <button class="btn-secondary" (click)="loadLocations()">Refresh</button>
            </div>
          } @else {
            <div class="results-header">
              <span class="results-count">{{ filteredLocations.length }} locations found</span>
              @if (userLat) {
                <span class="nearby-label">
                  <span class="material-icons">near_me</span> Sorted by distance
                </span>
              }
            </div>
            <div class="locations-grid">
              @for (location of filteredLocations; track location.id) {
                <div class="location-card card" (click)="selectLocation(location.id)">
                  <div class="location-header">
                    <div class="location-name-wrap">
                      <h3 class="location-name">{{ location.name }}</h3>
                      @if (location.distanceKm != null) {
                        <span class="distance-badge">{{ location.distanceKm | number:'1.1-1' }} km</span>
                      }
                    </div>
                    <span class="availability-badge" [class.available]="location.availableSlots > 0"
                          [class.full]="location.availableSlots === 0">
                      {{ location.availableSlots > 0 ? location.availableSlots + ' free' : 'Full' }}
                    </span>
                  </div>

                  <p class="location-address">
                    <span class="material-icons">location_on</span>
                    {{ location.address }}, {{ location.city }}
                  </p>

                  <!-- Occupancy bar -->
                  <div class="occupancy-bar-wrap">
                    <div class="occupancy-bar">
                      <div class="occupancy-fill"
                           [style.width.%]="getOccupancyPct(location)"
                           [class.high]="getOccupancyPct(location) > 80"
                           [class.medium]="getOccupancyPct(location) > 50 && getOccupancyPct(location) <= 80">
                      </div>
                    </div>
                    <span class="occupancy-label">{{ getOccupancyPct(location) }}% full</span>
                  </div>

                  <div class="location-details">
                    <div class="detail-item">
                      <span class="material-icons">directions_car</span>
                      <span>{{ location.slotsCount }} slots</span>
                    </div>
                    @if (location.openingHours && location.openingHours['247']) {
                      <div class="detail-item">
                        <span class="material-icons">schedule</span>
                        <span>24×7</span>
                      </div>
                    } @else if (location.openingHours?.open) {
                      <div class="detail-item">
                        <span class="material-icons">schedule</span>
                        <span>{{ location.openingHours?.open }} – {{ location.openingHours?.close }}</span>
                      </div>
                    }
                  </div>

                  <div class="location-rate">
                    <span class="rate-label">From</span>
                    <span class="rate-amount">
                      ₹{{ (location.rates[0]?.amount ?? 0) | number:'1.0-0' }}/hr
                    </span>
                  </div>

                  @if (location.amenities && location.amenities.length > 0) {
                    <div class="amenities">
                      @for (amenity of location.amenities.slice(0, 4); track amenity) {
                        <span class="amenity-tag">{{ formatAmenity(amenity) }}</span>
                      }
                    </div>
                  }

                  <div class="card-footer">
                    <span class="book-cta">Book Now →</span>
                  </div>
                </div>
              }
            </div>
          }
        }
      }
    </div>
  `,
  styles: [`
    .feature-container {
      padding: 1.5rem;
      max-width: 1200px;
      margin: 0 auto;
      min-height: 100vh;
      background: var(--background);
    }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .feature-header { margin-bottom: 1.5rem; }
    .feature-title { font-size: 1.75rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.25rem; }
    .feature-subtitle { font-size: 0.9rem; color: var(--text-secondary); }

    .search-bar {
      display: flex; align-items: center; gap: 0.75rem;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius-xl); padding: 0.75rem 1rem; margin-bottom: 1rem;
    }
    .search-icon { color: var(--text-muted); font-size: 20px; }
    .search-input { flex: 1; border: none; background: transparent; outline: none; font-size: 0.9rem; color: var(--text-primary); }
    .location-btn { background: none; border: none; cursor: pointer; color: var(--primary-600); padding: 0.25rem; }
    .location-btn .material-icons { font-size: 22px; }

    .view-toggle {
      display: flex; gap: 0.5rem; margin-bottom: 1.5rem;
      button {
        display: flex; align-items: center; gap: 0.5rem;
        padding: 0.5rem 1rem; border-radius: var(--radius-md);
        border: 1px solid var(--border); background: transparent;
        font-size: 0.85rem; cursor: pointer; color: var(--text-secondary);
        .material-icons { font-size: 18px; }
        &.active { background: var(--primary-600); color: white; border-color: var(--primary-600); }
      }
    }

    .map-container {
      width: 100%; height: 400px; border-radius: var(--radius-xl);
      border: 1px solid var(--border); margin-bottom: 1.5rem; overflow: hidden;
    }

    .results-header {
      display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;
    }
    .results-count { font-size: 0.85rem; color: var(--text-secondary); font-weight: 500; }
    .nearby-label { display: flex; align-items: center; gap: 0.25rem; font-size: 0.8rem; color: var(--primary-600); }
    .nearby-label .material-icons { font-size: 16px; }

    .loading-state, .empty-state {
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 4rem 0; gap: 1rem;
      .material-icons { font-size: 64px; color: var(--text-muted); }
      p { color: var(--text-secondary); }
    }
    .btn-secondary {
      padding: 0.5rem 1.5rem; border-radius: var(--radius-md);
      border: 1px solid var(--border); background: transparent; cursor: pointer;
      font-size: 0.875rem; color: var(--text-secondary);
    }

    .locations-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 1.25rem;
    }

    .location-card {
      cursor: pointer; transition: all 0.2s ease; padding: 1.25rem;
      &:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }
    }

    .location-header {
      display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;
    }
    .location-name-wrap { flex: 1; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
    .location-name { font-size: 1.1rem; font-weight: 600; color: var(--text-primary); }
    .distance-badge { font-size: 0.7rem; background: var(--primary-50); color: var(--primary-700); padding: 0.15rem 0.5rem; border-radius: 99px; font-weight: 500; }
    .availability-badge {
      background: var(--error); color: white; padding: 0.2rem 0.6rem;
      border-radius: var(--radius-full); font-size: 0.7rem; font-weight: 600; white-space: nowrap;
      &.available { background: var(--success); }
      &.full { background: var(--text-muted); }
    }

    .location-address {
      display: flex; align-items: center; gap: 0.25rem;
      color: var(--text-secondary); font-size: 0.8rem; margin-bottom: 0.75rem;
      .material-icons { font-size: 16px; color: var(--primary-400); }
    }

    .occupancy-bar-wrap {
      display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;
    }
    .occupancy-bar { flex: 1; background: var(--border); border-radius: 99px; height: 6px; overflow: hidden; }
    .occupancy-fill { height: 100%; background: var(--success); border-radius: 99px; transition: width 0.3s;
      &.medium { background: #f59e0b; }
      &.high { background: var(--error); }
    }
    .occupancy-label { font-size: 0.7rem; color: var(--text-muted); white-space: nowrap; }

    .location-details { display: flex; gap: 1rem; margin-bottom: 0.75rem; }
    .detail-item {
      display: flex; align-items: center; gap: 0.25rem;
      font-size: 0.8rem; color: var(--text-secondary);
      .material-icons { font-size: 16px; }
    }

    .location-rate { display: flex; align-items: baseline; gap: 0.375rem; margin-bottom: 0.75rem; }
    .rate-label { font-size: 0.8rem; color: var(--text-secondary); }
    .rate-amount { font-size: 1.25rem; font-weight: 700; color: var(--primary-600); }

    .amenities { display: flex; flex-wrap: wrap; gap: 0.375rem; margin-bottom: 0.75rem; }
    .amenity-tag {
      background: var(--primary-50); color: var(--primary-700);
      padding: 0.2rem 0.6rem; border-radius: var(--radius-md); font-size: 0.7rem; font-weight: 500;
    }

    .card-footer {
      border-top: 1px solid var(--border); padding-top: 0.75rem; margin-top: 0.25rem;
    }
    .book-cta { font-size: 0.875rem; font-weight: 600; color: var(--primary-600); }
  `],
})
export class ParkingListComponent implements OnInit, AfterViewInit, OnDestroy {
  readonly stepLabels = ['Location', 'Slot', 'Book'];

  private parkingService = inject(ParkingService);
  private router = inject(Router);
  private ngZone = inject(NgZone);

  @ViewChild('mapContainer') mapContainerRef?: ElementRef;

  locations: ParkingLocation[] = [];
  filteredLocations: ParkingLocation[] = [];
  loading = true;
  viewMode: 'list' | 'map' = 'list';
  searchQuery = '';
  userLat?: number;
  userLng?: number;
  private mapInstance: any = null;
  private mapScriptLoaded = false;

  ngOnInit() {
    this.tryGetUserLocation();
    // Keep initial load async to avoid Angular dev-mode NG0100
    // when geolocation callback updates state very quickly.
    setTimeout(() => this.loadLocations(), 0);
  }

  ngAfterViewInit() {}

  ngOnDestroy() {
    this.mapInstance = null;
  }

  loadLocations() {
    this.loading = true;
    const params = this.userLat != null
      ? { lat: this.userLat, lng: this.userLng!, radius_km: 10 }
      : undefined;

    this.parkingService.getLocations(params).subscribe({
      next: (data) => {
        // If geo-filter returns empty (user far from seeded/demo locations),
        // fallback to full list so UI never looks broken.
        if (params && (!data || data.length === 0)) {
          this.parkingService.getLocations().subscribe({
            next: (allData) => {
              this.locations = allData;
              this.filteredLocations = allData;
              this.loading = false;
              if (this.viewMode === 'map') this.initMap();
            },
            error: () => {
              this.loading = false;
            },
          });
          return;
        }

        this.locations = data;
        this.filteredLocations = data;
        this.loading = false;
        if (this.viewMode === 'map') this.initMap();
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  tryGetUserLocation() {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition((pos) => {
        this.ngZone.run(() => {
          this.userLat = pos.coords.latitude;
          this.userLng = pos.coords.longitude;
          // Defer refresh to next macrotask to keep template checks stable.
          setTimeout(() => this.loadLocations(), 0);
        });
      });
    }
  }

  useMyLocation() {
    this.tryGetUserLocation();
  }

  onSearchChange() {
    const q = this.searchQuery.toLowerCase().trim();
    if (!q) {
      this.filteredLocations = this.locations;
      return;
    }
    this.filteredLocations = this.locations.filter(
      (l) =>
        l.name.toLowerCase().includes(q) ||
        l.city.toLowerCase().includes(q) ||
        l.address.toLowerCase().includes(q)
    );
  }

  selectLocation(locationId: string) {
    this.router.navigate(['/parking/slot', locationId]);
  }

  getOccupancyPct(loc: ParkingLocation): number {
    if (!loc.slotsCount) return 0;
    const occupied = loc.slotsCount - loc.availableSlots;
    return Math.round((occupied / loc.slotsCount) * 100);
  }

  formatAmenity(a: string): string {
    return a.replace(/_/g, ' ');
  }

  initMap() {
    if (typeof mappls === 'undefined') {
      this.loadMapScript();
      return;
    }
    this.renderMap();
  }

  private loadMapScript() {
    if (this.mapScriptLoaded) return;
    this.mapScriptLoaded = true;
    const script = document.createElement('script');
    // MapmyIndia SDK — key configured via environment
    script.src = `https://apis.mappls.com/advancedmaps/v1/mappls-js/mappls.js?v=3.0`;
    script.onload = () => this.ngZone.run(() => this.renderMap());
    document.head.appendChild(script);
  }

  private renderMap() {
    const container = this.mapContainerRef?.nativeElement;
    if (!container || typeof mappls === 'undefined') return;

    const center = this.userLat
      ? { lat: this.userLat, lng: this.userLng! }
      : { lat: 28.6139, lng: 77.2090 };

    this.mapInstance = new mappls.Map('parking-map', {
      center: [center.lat, center.lng],
      zoom: 13,
    });

    this.filteredLocations.forEach((loc) => {
      if (!loc.coordinates?.latitude) return;
      const color = loc.availableSlots > 0 ? '#16a34a' : '#dc2626';
      const marker = new mappls.Marker({
        map: this.mapInstance,
        position: { lat: +loc.coordinates.latitude, lng: +loc.coordinates.longitude },
        popupHtml: `<b>${loc.name}</b><br>${loc.availableSlots} slots free<br>₹${loc.rates[0]?.amount ?? '?'}/hr`,
        fitbounds: false,
      });
      marker.addListener('click', () => {
        this.ngZone.run(() => this.selectLocation(loc.id));
      });
    });
  }
}
