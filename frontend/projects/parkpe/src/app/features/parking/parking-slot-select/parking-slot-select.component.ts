import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { ParkingSlot } from '../../../core/models/parking.model';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';

@Component({
  selector: 'app-parking-slot-select',
  standalone: true,
  imports: [CommonModule, StepIndicatorComponent],
  template: `
    <div class="feature-container">
      <app-step-indicator [steps]="stepLabels" [currentStep]="2" />
      <button class="btn btn-outline back-btn" (click)="goBack()">
        <span class="material-icons">arrow_back</span> Back to Locations
      </button>

      <header class="feature-header">
        <h1 class="feature-title">Select Parking Slot</h1>
      </header>

      @if (loading) {
        <div class="loading-state">
          <div class="spinner"></div>
          <p>Loading available slots...</p>
        </div>
      } @else {
        <div class="slots-grid">
          @for (slot of slots; track slot.id) {
            <div
              class="slot-card card"
              [class.unavailable]="!slot.available"
              [class.selectable]="slot.available"
              (click)="slot.available && selectSlot(slot)"
            >
              <div class="slot-header">
                <h3 class="slot-code">{{ slot.code }}</h3>
                <span class="slot-status" [class.available]="slot.available">
                  {{ slot.available ? 'Available' : 'Occupied' }}
                </span>
              </div>
              <div class="slot-details">
                <p class="slot-type">{{ slot.vehicleType | titlecase }}</p>
                <p class="slot-rate">₹{{ slot.rate }}/hr</p>
              </div>
              @if (slot.features && slot.features.length > 0) {
                <div class="slot-features">
                  @for (feature of slot.features; track feature) {
                    <span class="feature-tag">
                      @if (feature === 'ev_charging') {
                        <span class="material-icons">ev_station</span>
                      } @else if (feature === 'covered') {
                        <span class="material-icons">garage</span>
                      }
                      {{ feature | titlecase }}
                    </span>
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
    .feature-container { padding: 2rem; max-width: 1200px; margin: 0 auto; }
    .back-btn { margin-bottom: 1rem; display: inline-flex; align-items: center; gap: 0.5rem; }
    .feature-header { margin-bottom: 2rem; }
    .feature-title { font-size: 2rem; font-weight: 700; color: var(--text-primary); }
    
    .slots-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 1rem;
    }

    .slot-card {
      padding: 1.5rem;
      transition: all 0.3s ease;

      &.selectable {
        cursor: pointer;

        &:hover {
          transform: translateY(-2px);
          box-shadow: var(--shadow-green-md);
        }
      }

      &.unavailable {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }

    .slot-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }

    .slot-code {
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--primary-600);
    }

    .slot-status {
      padding: 0.25rem 0.75rem;
      border-radius: var(--radius-full);
      font-size: 0.75rem;
      font-weight: 600;
      background: var(--error);
      color: white;

      &.available {
        background: var(--success);
      }
    }

    .slot-details {
      margin-bottom: 1rem;
    }

    .slot-type {
      font-size: 0.875rem;
      color: var(--text-secondary);
      margin-bottom: 0.5rem;
    }

    .slot-rate {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text-primary);
    }

    .slot-features {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .feature-tag {
      display: flex;
      align-items: center;
      gap: 0.25rem;
      background: var(--primary-50);
      color: var(--primary-700);
      padding: 0.25rem 0.5rem;
      border-radius: var(--radius-sm);
      font-size: 0.75rem;

      .material-icons {
        font-size: 14px;
      }
    }
  `],
})
export class ParkingSlotSelectComponent implements OnInit {
  readonly stepLabels = ['Location', 'Slot', 'Book'];
  private api = inject(API_BACKEND_TOKEN);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  locationId = '';
  slots: ParkingSlot[] = [];
  loading = true;

  ngOnInit() {
    this.locationId = this.route.snapshot.params['locationId'];
    this.loadSlots();
  }

  loadSlots() {
    this.api.getSlots(this.locationId).subscribe({
      next: (data) => {
        this.slots = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  selectSlot(slot: ParkingSlot) {
    this.router.navigate(['/parking/booking', slot.id]);
  }

  goBack() {
    this.router.navigate(['/parking/list']);
  }
}
