import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { ParkingLocation } from '../../../core/models/parking.model';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';

@Component({
  selector: 'app-parking-list',
  standalone: true,
  imports: [CommonModule, StepIndicatorComponent, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <app-step-indicator [steps]="stepLabels" [currentStep]="1" />
      <header class="feature-header">
        <h1 class="feature-title">Parking Locations</h1>
        <p class="feature-subtitle">Find and book parking near you</p>
      </header>

      @if (loading) {
        <div class="loading-state">
          <div class="spinner"></div>
          <p>Loading parking locations...</p>
        </div>
      } @else if (locations.length === 0) {
        <div class="empty-state">
          <span class="material-icons">local_parking</span>
          <p>No parking locations available</p>
        </div>
      } @else {
        <div class="locations-grid">
          @for (location of locations; track location.id) {
            <div class="location-card card" (click)="selectLocation(location.id)">
              <div class="location-header">
                <h3 class="location-name">{{ location.name }}</h3>
                <span class="availability-badge" [class.available]="location.availableSlots > 0">
                  {{ location.availableSlots }} available
                </span>
              </div>
              <p class="location-address">
                <span class="material-icons">location_on</span>
                {{ location.address }}, {{ location.city }}
              </p>
              <div class="location-details">
                <div class="detail-item">
                  <span class="material-icons">directions_car</span>
                  <span>{{ location.slotsCount }} slots</span>
                </div>
                <div class="detail-item">
                  <span class="material-icons">schedule</span>
                  <span>24/7</span>
                </div>
              </div>
              <div class="location-rate">
                <span class="rate-label">Starting from</span>
                <span class="rate-amount">₹{{ location.rates[0]?.amount }}/hr</span>
              </div>
              @if (location.amenities && location.amenities.length > 0) {
                <div class="amenities">
                  @for (amenity of location.amenities.slice(0, 3); track amenity) {
                    <span class="amenity-tag">{{ amenity }}</span>
                  }
                </div>
              }
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container {
      padding: 2rem;
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

    .feature-header {
      margin-bottom: 2rem;
    }

    .feature-title {
      font-size: 2rem;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 0.5rem;
    }

    .feature-subtitle {
      font-size: 1rem;
      color: var(--text-secondary);
    }

    .loading-state, .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 4rem 0;
      gap: 1rem;

      .material-icons {
        font-size: 64px;
        color: var(--text-muted);
      }
    }

    .locations-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.5rem;
    }

    .location-card {
      cursor: pointer;
      transition: all 0.3s ease;
      padding: 1.5rem;

      &:hover {
        transform: translateY(-4px);
        box-shadow: var(--shadow-green-lg);
      }
    }

    .location-header {
      display: flex;
      justify-content: space-between;
      align-items: start;
      margin-bottom: 1rem;
    }

    .location-name {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text-primary);
      flex: 1;
    }

    .availability-badge {
      background: var(--error);
      color: white;
      padding: 0.25rem 0.75rem;
      border-radius: var(--radius-full);
      font-size: 0.75rem;
      font-weight: 600;

      &.available {
        background: var(--success);
      }
    }

    .location-address {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      color: var(--text-secondary);
      font-size: 0.875rem;
      margin-bottom: 1rem;

      .material-icons {
        font-size: 18px;
      }
    }

    .location-details {
      display: flex;
      gap: 1.5rem;
      margin-bottom: 1rem;
    }

    .detail-item {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.875rem;
      color: var(--text-secondary);

      .material-icons {
        font-size: 18px;
      }
    }

    .location-rate {
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }

    .rate-label {
      font-size: 0.875rem;
      color: var(--text-secondary);
    }

    .rate-amount {
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--primary-600);
    }

    .amenities {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .amenity-tag {
      background: var(--primary-50);
      color: var(--primary-700);
      padding: 0.25rem 0.75rem;
      border-radius: var(--radius-md);
      font-size: 0.75rem;
      font-weight: 500;
    }
  `],
})
export class ParkingListComponent implements OnInit {
  readonly stepLabels = ['Location', 'Slot', 'Book'];
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);

  locations: ParkingLocation[] = [];
  loading = true;

  ngOnInit() {
    this.api.getLocations().subscribe({
      next: (data) => {
        this.locations = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  selectLocation(locationId: string) {
    this.router.navigate(['/parking/slot', locationId]);
  }
}
