import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { NotificationService } from '../../../core/services/notification.service';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';
import { MobilityStateStore } from '../../../core/stores/mobility-state.store';

@Component({
  selector: 'app-parking-booking',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, StepIndicatorComponent],
  template: `
    <div class="feature-container">
      <app-step-indicator [steps]="stepLabels" [currentStep]="3" />
      <h1 class="feature-title">Confirm Booking</h1>

      <form [formGroup]="bookingForm" (ngSubmit)="onSubmit()">
        <div class="booking-summary card">
          <h2>Booking Details</h2>
          
          <div class="form-group">
            <label>Vehicle Number</label>
            <input type="text" formControlName="vehicleNumber" class="form-control" placeholder="e.g., KA01AB1234" />
          </div>

          <div class="form-group">
            <label>Vehicle Type</label>
            <select formControlName="vehicleType" class="form-control">
              <option value="two_wheeler">Two Wheeler</option>
              <option value="four_wheeler">Four Wheeler</option>
              <option value="heavy_vehicle">Heavy Vehicle</option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>From</label>
              <input type="datetime-local" formControlName="from" class="form-control" />
            </div>
            <div class="form-group">
              <label>To</label>
              <input type="datetime-local" formControlName="to" class="form-control" />
            </div>
          </div>

          <div class="booking-price">
            <span>Estimated Amount:</span>
            <span class="price">₹150</span>
          </div>
        </div>

        <button type="submit" class="btn btn-primary btn-block" [disabled]="loading">
          @if (loading) {
            <span class="spinner"></span> Processing...
          } @else {
            Proceed to Payment
          }
        </button>
      </form>
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 600px; margin: 0 auto; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; color: var(--text-primary); }
    .booking-summary { padding: 2rem; margin-bottom: 2rem; }
    .form-group { margin-bottom: 1.5rem; }
    .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; color: var(--text-primary); }
    .form-control {
      width: 100%;
      padding: 0.75rem;
      border: 2px solid var(--border-light);
      border-radius: var(--radius-md);
      font-size: 1rem;
    }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .booking-price {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 1rem;
      background: var(--primary-50);
      border-radius: var(--radius-md);
      margin-top: 1.5rem;
      font-size: 1.125rem;
      font-weight: 600;
    }
    .price { font-size: 1.5rem; color: var(--primary-700); }
    .btn-block { width: 100%; padding: 1rem; font-size: 1.125rem; }
  `],
})
export class ParkingBookingComponent implements OnInit {
  readonly stepLabels = ['Location', 'Slot', 'Book'];
  private fb = inject(FormBuilder);
  private api = inject(API_BACKEND_TOKEN);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private notification = inject(NotificationService);
  private stateStore = inject(MobilityStateStore);

  slotId = '';
  bookingForm!: FormGroup;
  loading = false;

  ngOnInit() {
    this.slotId = this.route.snapshot.params['slotId'];
    const now = new Date();
    const later = new Date(now.getTime() + 3 * 60 * 60 * 1000); // 3 hours later

    this.bookingForm = this.fb.group({
      vehicleNumber: ['', Validators.required],
      vehicleType: ['four_wheeler', Validators.required],
      from: [this.formatDateTimeLocal(now), Validators.required],
      to: [this.formatDateTimeLocal(later), Validators.required],
    });
  }

  formatDateTimeLocal(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  }

  onSubmit() {
    if (this.bookingForm.invalid) {
      return;
    }

    this.loading = true;
    const bookingData = {
      ...this.bookingForm.value,
      slotId: this.slotId,
      locationId: 'loc_001', // From slot data
      customerName: 'John Doe', // From auth
      customerEmail: 'john@example.com',
      customerPhone: '+919876543210',
    };

    this.api.createBooking(bookingData).subscribe({
      next: (booking) => {
        this.stateStore.setActiveBooking(booking);
        this.notification.showSuccess('Booking created successfully!');
        this.router.navigate(['/parking/detail', booking.id]);
      },
      error: () => {
        this.loading = false;
        this.notification.showError('Failed to create booking');
      },
    });
  }
}
