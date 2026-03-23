import { Component, OnDestroy, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { Booking } from '../../../core/models/parking.model';
import { MobilityStateStore } from '../../../core/stores/mobility-state.store';
import { RealtimeStatusService } from '../../../core/services/realtime-status.service';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-parking-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      @if (loading) {
        <div class="loading-state">
          <div class="spinner"></div>
        </div>
      } @else if (booking) {
        <div class="booking-success">
          <div class="success-icon">
            <span class="material-icons">check_circle</span>
          </div>
          <h1 class="success-title">Booking Confirmed!</h1>
          <p class="booking-reference">Ref: {{ booking.bookingReference }}</p>
          @if (fromSnapshot) {
            <p class="snapshot-note">
              Showing last saved booking snapshot @if (snapshotTs) { · {{ snapshotTs | date:'short' }} }
            </p>
          }
        </div>

        <div class="booking-details card">
          <h2>Booking Details</h2>
          
          <div class="detail-row">
            <span class="label">Location:</span>
            <span class="value">{{ booking.locationName }}</span>
          </div>
          
          <div class="detail-row">
            <span class="label">Slot:</span>
            <span class="value">{{ booking.slotCode }}</span>
          </div>
          
          <div class="detail-row">
            <span class="label">Vehicle:</span>
            <span class="value">{{ booking.vehicleNumber }}</span>
          </div>
          
          <div class="detail-row">
            <span class="label">From:</span>
            <span class="value">{{ booking.from | date:'short' }}</span>
          </div>
          
          <div class="detail-row">
            <span class="label">To:</span>
            <span class="value">{{ booking.to | date:'short' }}</span>
          </div>
          
          <div class="detail-row highlight">
            <span class="label">Amount Paid:</span>
            <span class="value price">₹{{ booking.amount }}</span>
          </div>
          
          @if (booking.qrCode) {
            <div class="qr-section">
              <h3>Entry QR Code</h3>
              <img [src]="booking.qrCode" alt="Booking QR Code" class="qr-image" />
              <p class="qr-hint">Show this at the entry gate</p>
            </div>
          }
        </div>

        <div class="actions">
          <button class="btn btn-primary" routerLink="/dashboard">
            Back to Dashboard
          </button>
          <button class="btn btn-outline" routerLink="/parking/list">
            Book Another
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 600px; margin: 0 auto; }
    .booking-success {
      text-align: center;
      margin-bottom: 2rem;
    }
    .success-icon .material-icons {
      font-size: 80px;
      color: var(--success);
      animation: scaleIn 0.5s ease;
    }
    .success-title {
      font-size: 2rem;
      font-weight: 700;
      color: var(--text-primary);
      margin: 1rem 0 0.5rem;
    }
    .booking-reference {
      font-size: 1rem;
      color: var(--text-secondary);
      font-family: monospace;
    }
    .snapshot-note {
      margin: 0.35rem 0 0;
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .booking-details { padding: 2rem; margin-bottom: 2rem; }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light);

      &.highlight {
        background: var(--primary-50);
        padding: 1rem;
        border-radius: var(--radius-md);
        margin-top: 1rem;
        border-bottom: none;
      }
    }
    .label { font-weight: 500; color: var(--text-secondary); }
    .value { font-weight: 600; color: var(--text-primary); }
    .price { font-size: 1.5rem; color: var(--primary-700); }
    .qr-section {
      text-align: center;
      margin-top: 2rem;
      padding-top: 2rem;
      border-top: 2px dashed var(--border-default);
    }
    .qr-image {
      width: 200px;
      height: 200px;
      margin: 1rem auto;
      border: 4px solid var(--primary-500);
      border-radius: var(--radius-md);
    }
    .qr-hint { color: var(--text-secondary); font-size: 0.875rem; }
    .actions {
      display: flex;
      gap: 1rem;
      justify-content: center;
    }
  `],
})
export class ParkingDetailComponent implements OnInit, OnDestroy {
  private api = inject(API_BACKEND_TOKEN);
  private route = inject(ActivatedRoute);
  private store = inject(MobilityStateStore);
  private realtime = inject(RealtimeStatusService);
  private realtimeSub: Subscription | null = null;

  bookingId = '';
  booking: Booking | null = null;
  loading = true;
  fromSnapshot = false;
  snapshotTs: number | null = null;

  ngOnInit() {
    this.bookingId = this.route.snapshot.params['bookingId'];
    const snapshot = this.store.activeBooking();
    if (snapshot && snapshot.id === this.bookingId) {
      this.booking = snapshot;
      this.loading = false;
      this.fromSnapshot = true;
      this.snapshotTs = this.store.activeBookingTs();
    }
    this.loadBooking();
  }

  loadBooking() {
    this.api.getBooking(this.bookingId).subscribe({
      next: (data) => {
        this.booking = data;
        this.store.setActiveBooking(data);
        this.loading = false;
        this.fromSnapshot = false;
        this.watchRealtimeIfPending();
      },
      error: () => {
        const snapshot = this.store.activeBooking();
        if (snapshot && snapshot.id === this.bookingId) {
          this.booking = snapshot;
          this.fromSnapshot = true;
          this.snapshotTs = this.store.activeBookingTs();
        }
        this.loading = false;
      },
    });
  }

  ngOnDestroy(): void {
    this.realtimeSub?.unsubscribe();
  }

  private watchRealtimeIfPending(): void {
    if (!this.booking || this.booking.status !== 'pending') return;
    this.realtimeSub?.unsubscribe();
    this.realtimeSub = this.realtime.watchBooking(this.booking.id, 60_000).subscribe((fresh) => {
      if (!fresh) return;
      this.booking = fresh;
      this.store.setActiveBooking(fresh);
    });
  }
}
