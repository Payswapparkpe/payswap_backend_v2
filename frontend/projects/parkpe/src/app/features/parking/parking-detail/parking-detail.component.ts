import { Component, inject, OnInit } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import QRCode from 'qrcode';
import { Booking } from '../../../core/models/parking.model';
import { ParkingService } from '../services/parking.service';

@Component({
  selector: 'app-parking-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  providers: [DatePipe],
  template: `
    <div class="feature-container">
      <a routerLink="/parking/list" class="back-link">
        <span class="material-icons">arrow_back</span>
        Back to Parking
      </a>

      @if (loading) {
        <div class="loading-state"><div class="spinner"></div></div>
      } @else if (!booking) {
        <div class="empty-state">
          <span class="material-icons">error_outline</span>
          <p>Booking not found.</p>
          <a routerLink="/parking/list" class="btn-secondary">Find Parking</a>
        </div>
      } @else {
        <div class="status-banner" [class]="'status-' + booking.status">
          <div class="status-icon-wrap">
            <span class="material-icons status-icon">{{ statusIcon(booking.status) }}</span>
          </div>
          <div class="status-copy">
            <div class="status-title">{{ statusTitle(booking.status) }}</div>
            <div class="status-ref">Booking ID: {{ booking.bookingReference }}</div>
          </div>
          <div class="amount-chip">₹{{ (booking.finalAmount ?? booking.amount) | number:'1.0-2' }}</div>
        </div>

        <div class="content-grid">
          <div class="ticket-card card">
            <div class="card-head">
              <h3>Parking Ticket</h3>
              @if (booking.ticketNumber) {
                <span class="ticket-no">#{{ booking.ticketNumber }}</span>
              }
            </div>

            <div class="qr-section">
              @if (booking.qrImageUrl || generatedQrDataUrl) {
                <img [src]="booking.qrImageUrl || generatedQrDataUrl" class="qr-image" alt="QR Code" />
              } @else {
                <div class="qr-placeholder">
                  <span class="material-icons">qr_code_2</span>
                  <span class="qr-ref">{{ booking.bookingReference }}</span>
                </div>
              }
              <p class="qr-label">Show this QR at entry gate</p>
            </div>

            <div class="quick-facts">
              <div class="fact">
                <span class="fact-label">Slot</span>
                <span class="fact-value">{{ booking.slotCode }}</span>
              </div>
              <div class="fact">
                <span class="fact-label">Vehicle</span>
                <span class="fact-value">{{ booking.vehicleNumber }}</span>
              </div>
              <div class="fact">
                <span class="fact-label">Duration</span>
                <span class="fact-value">{{ formatDuration(booking.duration) }}</span>
              </div>
            </div>
          </div>

          <div class="meta-card card">
            <h3 class="section-title">Booking Details</h3>
            <div class="details-grid">
              <div class="detail-row">
                <span class="detail-label">Location</span>
                <span class="detail-value highlight">{{ booking.locationName }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Vehicle Type</span>
                <span class="detail-value">{{ formatVehicleType(booking.vehicleType) }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">From</span>
                <span class="detail-value">{{ booking.from | date:'dd MMM y, h:mm a' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">To</span>
                <span class="detail-value">{{ booking.to | date:'dd MMM y, h:mm a' }}</span>
              </div>
              @if (booking.actualEntryTime) {
                <div class="detail-row">
                  <span class="detail-label">Actual Entry</span>
                  <span class="detail-value">{{ booking.actualEntryTime | date:'dd MMM y, h:mm a' }}</span>
                </div>
              }
              @if (booking.actualExitTime) {
                <div class="detail-row">
                  <span class="detail-label">Exit</span>
                  <span class="detail-value">{{ booking.actualExitTime | date:'dd MMM y, h:mm a' }}</span>
                </div>
              }
              <div class="detail-row total-row">
                <span class="detail-label">Amount Paid</span>
                <span class="detail-value amount-value">
                  ₹{{ (booking.finalAmount ?? booking.amount) | number:'1.0-2' }}
                  @if (booking.finalAmount && booking.finalAmount !== booking.estimatedAmount) {
                    <span class="overstay-note">estimated ₹{{ booking.estimatedAmount | number:'1.0-2' }}</span>
                  }
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="action-card card">
          <h3 class="section-title">Quick Actions</h3>
          <div class="action-row">
            <button class="action-btn whatsapp" (click)="resendTicket()" [disabled]="resending">
              <span class="material-icons">{{ resending ? 'hourglass_empty' : 'chat' }}</span>
              {{ resending ? 'Sending...' : 'Resend WhatsApp Ticket' }}
            </button>
            @if (booking.ticketPdfUrl) {
              <a [href]="booking.ticketPdfUrl" target="_blank" class="action-btn pdf">
                <span class="material-icons">picture_as_pdf</span>
                Download PDF
              </a>
            }
            @if (canCancel(booking.status)) {
              <button class="action-btn cancel" (click)="cancelBooking()">
                <span class="material-icons">cancel</span>
                Cancel Booking
              </button>
            }
          </div>
        </div>

        @if (resendMsg) {
          <div class="toast" [class.success]="resendSuccess" [class.error]="!resendSuccess">
            <span class="material-icons">{{ resendSuccess ? 'check_circle' : 'error' }}</span>
            {{ resendMsg }}
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 1.25rem; max-width: 980px; margin: 0 auto; min-height: 100vh; background: var(--background); }
    .back-link { display: inline-flex; align-items: center; gap: 0.5rem; color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem; }
    .back-link .material-icons { font-size: 20px; }
    .loading-state, .empty-state { display: flex; flex-direction: column; align-items: center; padding: 4rem 0; gap: 1rem; .material-icons { font-size: 64px; color: var(--text-muted); } p { color: var(--text-secondary); } }
    .btn-secondary { padding: 0.5rem 1.5rem; border-radius: var(--radius-md); border: 1px solid var(--border); background: transparent; text-decoration: none; font-size: 0.875rem; color: var(--text-secondary); }

    .status-banner { display: flex; align-items: center; gap: 1rem; padding: 1rem 1.25rem; border-radius: var(--radius-xl); margin-bottom: 1.25rem;
      &.status-confirmed { background: #eff6ff; border: 1px solid #bfdbfe; }
      &.status-active { background: #f0fdf4; border: 1px solid #bbf7d0; }
      &.status-completed { background: #f9fafb; border: 1px solid #e5e7eb; }
      &.status-cancelled, &.status-expired { background: #fff7ed; border: 1px solid #fed7aa; }
    }
    .status-copy { flex: 1; min-width: 0; }
    .status-icon-wrap { width: 44px; height: 44px; border-radius: 50%; background: white; display: flex; align-items: center; justify-content: center; }
    .status-icon { font-size: 24px; color: var(--primary-600); }
    .status-title { font-weight: 700; font-size: 1rem; color: var(--text-primary); }
    .status-ref { font-size: 0.75rem; color: var(--text-muted); font-family: monospace; margin-top: 0.125rem; }
    .amount-chip { background: white; border: 1px solid var(--border); border-radius: 999px; padding: 0.45rem 0.8rem; font-weight: 700; color: var(--primary-600); }

    .content-grid { display: grid; grid-template-columns: 320px 1fr; gap: 1rem; margin-bottom: 1rem; }
    @media (max-width: 840px) { .content-grid { grid-template-columns: 1fr; } }
    .ticket-card, .meta-card, .action-card { padding: 1rem; }
    .card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
    .card-head h3 { margin: 0; font-size: 1rem; }
    .qr-section { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; margin-bottom: 0.9rem; }
    .qr-label { font-size: 0.8rem; font-weight: 500; color: var(--text-secondary); text-align: center; margin: 0; }
    .qr-image { width: 220px; height: 220px; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 8px; background: white; }
    .qr-placeholder { width: 220px; height: 220px; border: 2px dashed var(--border); border-radius: var(--radius-lg); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.5rem; .material-icons { font-size: 56px; color: var(--text-muted); } }
    @media (max-width: 480px) {
      .qr-image, .qr-placeholder { width: 200px; height: 200px; }
    }
    .qr-ref { font-size: 0.7rem; font-family: monospace; color: var(--text-muted); word-break: break-all; text-align: center; padding: 0 0.5rem; }
    .ticket-no { font-size: 0.75rem; color: var(--text-muted); font-family: monospace; background: var(--surface-2); padding: 0.2rem 0.45rem; border-radius: 999px; }
    .quick-facts { display: grid; gap: 0.55rem; }
    .fact { display: flex; justify-content: space-between; font-size: 0.82rem; padding-bottom: 0.45rem; border-bottom: 1px dashed var(--border); }
    .fact:last-child { border-bottom: none; padding-bottom: 0; }
    .fact-label { color: var(--text-muted); }
    .fact-value { font-weight: 600; color: var(--text-primary); }

    .details-grid { display: grid; gap: 0.625rem; }
    .detail-row { display: flex; justify-content: space-between; align-items: baseline; padding: 0.375rem 0; border-bottom: 1px solid var(--border); &:last-child { border-bottom: none; } }
    .detail-label { font-size: 0.8rem; color: var(--text-muted); }
    .detail-value { font-size: 0.875rem; font-weight: 500; color: var(--text-primary); text-align: right; &.highlight { color: var(--primary-600); font-weight: 600; font-size: 1rem; } }
    .total-row .detail-label { font-weight: 600; font-size: 0.9rem; color: var(--text-primary); }
    .amount-value { font-size: 1.25rem !important; font-weight: 700 !important; color: var(--primary-600) !important; }
    .overstay-note { font-size: 0.7rem; color: var(--text-muted); font-weight: 400; margin-left: 0.25rem; }

    .action-row { display: flex; gap: 0.75rem; flex-wrap: wrap; }
    .action-btn { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.625rem 1.125rem; border-radius: var(--radius-lg); font-size: 0.85rem; font-weight: 600; cursor: pointer; text-decoration: none; border: none; &:disabled { opacity: 0.6; cursor: not-allowed; }
      &.whatsapp { background: #25d366; color: white; }
      &.pdf { background: #ef4444; color: white; }
      &.cancel { background: transparent; color: var(--error); border: 1.5px solid var(--error); }
    }
    .action-btn .material-icons { font-size: 18px; }

    .toast { display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 1rem; border-radius: var(--radius-lg); font-size: 0.85rem; margin-bottom: 1rem; .material-icons { font-size: 18px; } &.success { background: #dcfce7; color: #15803d; } &.error { background: #fee2e2; color: #b91c1c; } }

    .customer-card { padding: 1.25rem; }
    .section-title { font-size: 0.9rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.875rem; }
  `],
})
export class ParkingDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private parkingService = inject(ParkingService);

  booking?: Booking;
  loading = true;
  resending = false;
  resendMsg = '';
  resendSuccess = false;
  generatedQrDataUrl: string | null = null;

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('bookingId') || '';
    this.parkingService.getBooking(id).subscribe({
      next: (b) => {
        this.booking = b;
        this.loading = false;
        this.ensureScannableQr();
      },
      error: () => { this.loading = false; },
    });
  }

  statusIcon(s: string): string {
    const icons: Record<string, string> = {
      confirmed: 'check_circle', active: 'directions_car',
      completed: 'task_alt', cancelled: 'cancel', expired: 'timer_off', pending: 'pending',
    };
    return icons[s] ?? 'info';
  }

  statusTitle(s: string): string {
    const titles: Record<string, string> = {
      confirmed: 'Booking Confirmed', active: 'Vehicle Inside',
      completed: 'Parking Completed', cancelled: 'Booking Cancelled',
      expired: 'Booking Expired', pending: 'Booking Pending',
    };
    return titles[s] ?? s;
  }

  canCancel(s: string): boolean {
    return s === 'confirmed' || s === 'pending';
  }

  formatVehicleType(vt: string): string {
    return (vt || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  formatDuration(minutes: number): string {
    if (!minutes) return '–';
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return h > 0 ? `${h}h ${m > 0 ? m + 'm' : ''}`.trim() : `${m}m`;
  }

  private ensureScannableQr() {
    if (!this.booking || this.booking.qrImageUrl || !this.booking.qrCode) return;
    void QRCode.toDataURL(this.booking.qrCode, {
      width: 360,
      margin: 1,
      errorCorrectionLevel: 'H',
    }).then((url) => {
      this.generatedQrDataUrl = url;
    }).catch(() => {
      this.generatedQrDataUrl = null;
    });
  }

  resendTicket() {
    if (!this.booking) return;
    this.resending = true;
    this.resendMsg = '';
    this.parkingService.resendTicket(this.booking.bookingReference || String(this.booking.id)).subscribe({
      next: (r: any) => {
        this.resending = false;
        this.resendSuccess = true;
        this.resendMsg = r.whatsapp_sent
          ? 'Ticket sent on WhatsApp!'
          : 'Ticket delivery initiated.';
        setTimeout(() => this.resendMsg = '', 5000);
      },
      error: () => {
        this.resending = false;
        this.resendSuccess = false;
        this.resendMsg = 'Failed to resend. Please try again.';
        setTimeout(() => this.resendMsg = '', 5000);
      },
    });
  }

  cancelBooking() {
    if (!this.booking) return;
    if (!confirm('Are you sure you want to cancel this booking?')) return;
    this.parkingService.cancelBooking(this.booking.bookingReference || String(this.booking.id)).subscribe({
      next: () => this.router.navigate(['/parking/list']),
      error: () => alert('Cancellation failed. Please try again.'),
    });
  }
}
