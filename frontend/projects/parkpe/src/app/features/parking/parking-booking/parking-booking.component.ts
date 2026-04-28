import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ParkingSlot, BookingRequest, Booking } from '../../../core/models/parking.model';
import { ParkingService } from '../services/parking.service';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { VoucherListItem } from '../../../core/models/voucher.model';
import { ConnectService } from '../../connect/services/connect.service';

@Component({
  selector: 'app-parking-booking',
  standalone: true,
  imports: [CommonModule, FormsModule, StepIndicatorComponent],
  template: `
    <div class="feature-container">
      <button class="back-link" (click)="goBack()">
        <span class="material-icons">arrow_back</span> Back to Slot Selection
      </button>
      <app-step-indicator [steps]="stepLabels" [currentStep]="3" />
      <header class="feature-header">
        <h1 class="feature-title">Confirm Booking</h1>
      </header>

      @if (!slot) {
        <div class="loading-state"><div class="spinner"></div></div>
      } @else {
        <div class="booking-layout">

          <!-- Booking Form -->
          <div class="form-section">

            <!-- Slot summary -->
            <div class="slot-summary card">
              <div class="slot-badge">{{ slot.code }}</div>
              <div class="slot-meta">
                <span>{{ formatVehicleType(slot.vehicleType!) }}</span>
                <span class="sep">·</span>
                <span>₹{{ slot.rate }}/hr</span>
                @if (slot.features?.includes('covered')) { <span>· Covered</span> }
                @if (slot.features?.includes('ev_charging')) { <span>· EV ⚡</span> }
              </div>
            </div>

            <!-- Vehicle Details -->
            <div class="form-card card">
              <h3 class="form-section-title">Vehicle Details</h3>
              @if (registeredVehicles.length > 0) {
                <div class="form-group">
                  <label>Registered Vehicle</label>
                  <select [(ngModel)]="selectedVehicleId" class="form-input" (ngModelChange)="applySelectedVehicle()">
                    @for (v of registeredVehicles; track v.id) {
                      <option [ngValue]="v.id">{{ v.registrationNumber }} ({{ formatVehicleType(v.vehicleType) }})</option>
                    }
                    <option [ngValue]="'manual'">Enter manually</option>
                  </select>
                </div>
              }
              <div class="form-group">
                <label>Vehicle Number *</label>
                <input type="text" [(ngModel)]="vehicleNumber" placeholder="MH12AB1234"
                  class="form-input" style="text-transform: uppercase"
                  (input)="vehicleNumber = vehicleNumber.toUpperCase()" />
              </div>
              <div class="form-group">
                <label>Vehicle Type *</label>
                <select [(ngModel)]="vehicleType" class="form-input" (ngModelChange)="updateEstimate()">
                  <option value="two_wheeler">Two Wheeler</option>
                  <option value="four_wheeler">Four Wheeler</option>
                  <option value="ev">Electric Vehicle (EV)</option>
                  <option value="heavy_vehicle">Heavy Vehicle</option>
                </select>
              </div>
            </div>

            <!-- Duration -->
            <div class="form-card card">
              <h3 class="form-section-title">Parking Duration</h3>
              <div class="duration-grid">
                @for (opt of durationOptions; track opt.value) {
                  <button class="duration-chip" [class.active]="selectedDuration === opt.value"
                          (click)="setDuration(opt.value)">
                    {{ opt.label }}
                  </button>
                }
              </div>
              <div class="custom-duration" *ngIf="selectedDuration === 0">
                <div class="form-group">
                  <label>From</label>
                  <input type="datetime-local" [(ngModel)]="fromDt" class="form-input" (ngModelChange)="updateEstimate()" />
                </div>
                <div class="form-group">
                  <label>To</label>
                  <input type="datetime-local" [(ngModel)]="toDt" class="form-input" (ngModelChange)="updateEstimate()" />
                </div>
              </div>
              @if (selectedDuration > 0) {
                <div class="time-display">
                  <span class="material-icons">schedule</span>
                  {{ fromDt | date:'dd MMM, h:mm a' }} → {{ toDt | date:'dd MMM, h:mm a' }}
                </div>
              }
            </div>

            <!-- Contact Details -->
            <div class="form-card card">
              <h3 class="form-section-title">Contact Details</h3>
              <div class="form-group">
                <label>Full Name *</label>
                <input type="text" [(ngModel)]="customerName" placeholder="Your name" class="form-input" />
              </div>
              <div class="form-group">
                <label>WhatsApp Number *</label>
                <div class="phone-input">
                  <span class="country-code">+91</span>
                  <input type="tel" [(ngModel)]="customerPhone" placeholder="9876543210"
                    maxlength="10" class="form-input" />
                </div>
                <p class="field-hint">Ticket will be sent on WhatsApp</p>
              </div>
              <div class="form-group">
                <label>Email (optional)</label>
                <input type="email" [(ngModel)]="customerEmail" placeholder="you@email.com" class="form-input" />
              </div>
            </div>
          </div>

          <!-- Payment Summary -->
          <div class="summary-section">
            <div class="payment-card card">
              <h3 class="payment-title">Payment Summary</h3>

              <div class="price-rows">
                <div class="price-row">
                  <span>Duration</span>
                  <span>{{ selectedDuration > 0 ? selectedDuration + 'h' : 'Custom' }}</span>
                </div>
                <div class="price-row">
                  <span>Base Rate</span>
                  <span>₹{{ slot.rate }}/hr</span>
                </div>
                @if (priceEstimate) {
                  <div class="price-row">
                    <span>Grace Period</span>
                    <span>{{ priceEstimate.grace_minutes }} min free</span>
                  </div>
                }
                <div class="price-divider"></div>
                <div class="price-row total">
                  <span>Estimated Total</span>
                  <span class="total-amount">
                    @if (estimateLoading) {
                      <span class="spinner-sm"></span>
                    } @else {
                      ₹{{ estimatedAmount | number:'1.0-2' }}
                    }
                  </span>
                </div>
              </div>

              <!-- Voucher Payment -->
              <div class="payment-method">
                <div class="payment-method-header">
                  <span class="material-icons">account_balance_wallet</span>
                  <div>
                    <div class="payment-method-name">Parkpe Voucher</div>
                    <div class="payment-method-sub">Select one voucher for this booking</div>
                  </div>
                  <span class="material-icons check-icon"
                    [class.checked]="selectedVoucherBalance >= estimatedAmount">
                    {{ selectedVoucherBalance >= estimatedAmount ? 'check_circle' : 'radio_button_unchecked' }}
                  </span>
                </div>
                @if (availableVouchers.length > 0) {
                  <div class="form-group" style="margin-top: 0.625rem;">
                    <label style="font-size: 0.75rem;">Voucher *</label>
                    <select [(ngModel)]="selectedVoucherId" class="form-input" (ngModelChange)="onVoucherChange()">
                      @for (v of availableVouchers; track v.id) {
                        <option [ngValue]="v.id">{{ v.voucherCode }} — ₹{{ v.currentBalance | number:'1.0-2' }}</option>
                      }
                    </select>
                  </div>
                } @else {
                  <div class="voucher-warn">
                    <span class="material-icons">warning</span>
                    No active vouchers found for this account.
                  </div>
                }
                @if (selectedVoucherId && selectedVoucherBalance < estimatedAmount) {
                  <div class="voucher-warn">
                    <span class="material-icons">warning</span>
                    Selected voucher has insufficient balance. Need ₹{{ (estimatedAmount - selectedVoucherBalance) | number:'1.0-2' }} more.
                  </div>
                }
              </div>

              @if (errorMsg) {
                <div class="error-msg">
                  <span class="material-icons">error</span>
                  {{ errorMsg }}
                </div>
              }

              <button class="btn-confirm" [disabled]="!canSubmit() || submitting" (click)="submitBooking()">
                @if (submitting) {
                  <span class="spinner-sm"></span> Processing...
                } @else {
                  Confirm Booking — ₹{{ estimatedAmount | number:'1.0-2' }}
                }
              </button>

              <p class="terms">
                By confirming, you agree to Parkpe's parking terms. Ticket will be sent on WhatsApp.
              </p>
            </div>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 1.5rem; max-width: 1000px; margin: 0 auto; min-height: 100vh; background: var(--background); }
    .back-link { display: inline-flex; align-items: center; gap: 0.5rem; color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem; background: none; border: none; cursor: pointer; font-size: 1rem; padding: 0; }
    .back-link .material-icons { font-size: 20px; }
    .feature-header { margin-bottom: 1.5rem; }
    .feature-title { font-size: 1.75rem; font-weight: 700; color: var(--text-primary); }
    .loading-state { display: flex; justify-content: center; padding: 4rem; }

    .booking-layout { display: grid; grid-template-columns: 1fr 340px; gap: 1.5rem; align-items: start; }
    @media (max-width: 768px) { .booking-layout { grid-template-columns: 1fr; } }

    .slot-summary { display: flex; align-items: center; gap: 1rem; padding: 0.875rem 1.25rem; margin-bottom: 1rem; }
    .slot-badge { font-size: 1.75rem; font-weight: 700; color: var(--primary-600); min-width: 80px; }
    .slot-meta { font-size: 0.85rem; color: var(--text-secondary); display: flex; gap: 0.375rem; flex-wrap: wrap; }
    .sep { color: var(--text-muted); }

    .form-card { padding: 1.25rem; margin-bottom: 1rem; }
    .form-section-title { font-size: 0.95rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1rem; }
    .form-group { margin-bottom: 0.875rem; }
    .form-group label { display: block; font-size: 0.8rem; font-weight: 500; color: var(--text-secondary); margin-bottom: 0.375rem; }
    .form-input { width: 100%; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 0.625rem 0.875rem; font-size: 0.9rem; outline: none; background: var(--surface); color: var(--text-primary); &:focus { border-color: var(--primary-400); } }
    .phone-input { display: flex; align-items: center; gap: 0; border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; &:focus-within { border-color: var(--primary-400); } }
    .country-code { padding: 0.625rem 0.75rem; background: var(--border); font-size: 0.85rem; color: var(--text-secondary); white-space: nowrap; border-right: 1px solid var(--border); }
    .phone-input .form-input { border: none; border-radius: 0; }
    .field-hint { font-size: 0.7rem; color: var(--text-muted); margin-top: 0.25rem; }

    .duration-grid { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.75rem; }
    .duration-chip { padding: 0.375rem 0.875rem; border-radius: var(--radius-full); border: 1px solid var(--border); background: transparent; font-size: 0.8rem; cursor: pointer; color: var(--text-secondary); &.active { background: var(--primary-600); color: white; border-color: var(--primary-600); } }
    .custom-duration { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem; }
    .time-display { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; color: var(--text-secondary); padding: 0.5rem 0.75rem; background: var(--primary-50); border-radius: var(--radius-md); .material-icons { font-size: 16px; color: var(--primary-400); } }

    .payment-card { padding: 1.25rem; position: sticky; top: 1rem; }
    .payment-title { font-size: 1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1rem; }
    .price-rows { margin-bottom: 1rem; }
    .price-row { display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem; }
    .price-divider { border-top: 1px solid var(--border); margin: 0.75rem 0; }
    .price-row.total { color: var(--text-primary); font-weight: 600; font-size: 0.95rem; }
    .total-amount { font-size: 1.25rem; font-weight: 700; color: var(--primary-600); }
    .spinner-sm { width: 16px; height: 16px; border: 2px solid transparent; border-top-color: currentColor; border-radius: 50%; animation: spin 0.6s linear infinite; display: inline-block; vertical-align: middle; }
    @keyframes spin { to { transform: rotate(360deg); } }

    .payment-method { border: 1.5px solid var(--primary-200); border-radius: var(--radius-lg); padding: 0.875rem; margin-bottom: 1rem; background: var(--primary-50); }
    .payment-method-header { display: flex; align-items: center; gap: 0.75rem; }
    .payment-method-header .material-icons { color: var(--primary-600); font-size: 22px; }
    .payment-method-name { font-size: 0.9rem; font-weight: 600; color: var(--text-primary); }
    .payment-method-sub { font-size: 0.75rem; color: var(--text-secondary); }
    .check-icon { margin-left: auto; font-size: 20px; color: var(--text-muted); &.checked { color: var(--success); } }
    .voucher-warn { display: flex; align-items: center; gap: 0.375rem; font-size: 0.75rem; color: #b45309; background: #fef3c7; border-radius: var(--radius-md); padding: 0.5rem 0.75rem; margin-top: 0.5rem; .material-icons { font-size: 16px; } }

    .error-msg { display: flex; align-items: center; gap: 0.375rem; font-size: 0.8rem; color: var(--error); background: #fee2e2; border-radius: var(--radius-md); padding: 0.625rem 0.875rem; margin-bottom: 0.75rem; .material-icons { font-size: 18px; } }

    .btn-confirm { width: 100%; padding: 1rem; background: var(--primary-600); color: white; border: none; border-radius: var(--radius-lg); font-weight: 700; font-size: 0.95rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 0.5rem; &:disabled { opacity: 0.6; cursor: not-allowed; } &:not(:disabled):hover { background: var(--primary-700); } }
    .terms { font-size: 0.7rem; color: var(--text-muted); text-align: center; margin-top: 0.75rem; line-height: 1.4; }
  `],
})
export class ParkingBookingComponent implements OnInit {
  readonly stepLabels = ['Location', 'Slot', 'Book'];

  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private parkingService = inject(ParkingService);
  private api = inject(API_BACKEND_TOKEN);
  private connectService = inject(ConnectService);

  slot?: ParkingSlot;
  locationId = '';

  vehicleNumber = '';
  vehicleType = 'four_wheeler';
  customerName = '';
  customerPhone = '';
  customerEmail = '';

  fromDt = '';
  toDt = '';
  selectedDuration = 2;
  estimatedAmount = 0;
  estimateLoading = false;
  priceEstimate: any = null;
  voucherBalance = 0;
  maxSingleVoucherBalance = 0;
  availableVouchers: VoucherListItem[] = [];
  selectedVoucherId?: number;
  selectedVoucherBalance = 0;
  submitting = false;
  errorMsg = '';
  registeredVehicles: Array<{
    id: number;
    registrationNumber: string;
    vehicleType: string;
    isPrimary?: boolean;
  }> = [];
  selectedVehicleId: number | 'manual' = 'manual';

  durationOptions = [
    { value: 1, label: '1 hr' },
    { value: 2, label: '2 hrs' },
    { value: 4, label: '4 hrs' },
    { value: 8, label: '8 hrs' },
    { value: 24, label: '1 day' },
    { value: 0, label: 'Custom' },
  ];

  ngOnInit() {
    const state = history.state as { slot?: ParkingSlot; locationId?: string };
    this.slot = state?.slot;
    this.locationId = state?.locationId || this.route.snapshot.paramMap.get('slotId') || '';

    if (this.slot) {
      this.vehicleType = this.slot.vehicleType || 'four_wheeler';
    }

    this.setDuration(2);
    this.loadVoucherBalance();
    this.loadRegisteredVehicles();
    this.prefillUserDetails();
  }

  loadRegisteredVehicles() {
    // Customer registered vehicles come from Connect module, not Fleet module.
    this.connectService.getVehicles().subscribe({
      next: (resp: any) => {
        const items = resp?.results ?? [];
        this.registeredVehicles = items.map((v: any) => ({
          id: v.id,
          registrationNumber: v.registrationNumber || v.registration_number || '',
          vehicleType: this.normalizeVehicleType(v.vehicleType || v.vehicle_type),
          isPrimary: !!(v.isPrimary || v.is_primary),
        })).filter((v: any) => !!v.registrationNumber);

        if (this.registeredVehicles.length > 0) {
          const preferred =
            this.registeredVehicles.find((v) => v.isPrimary) || this.registeredVehicles[0];
          this.selectedVehicleId = preferred.id;
          this.applySelectedVehicle();
        }
      },
    });
  }

  prefillUserDetails() {
    this.api.getProfile().subscribe({
      next: (profile: any) => {
        this.customerName = profile?.name || profile?.full_name || '';
        this.customerPhone = (profile?.phone || '').replace(/^\+91/, '').replace(/\D/g, '');
        this.customerEmail = profile?.email || '';
      },
    });
  }

  loadVoucherBalance() {
    this.api.getVouchers({ page: 1, limit: 200 }).subscribe({
      next: (data: { vouchers: VoucherListItem[] }) => {
        const vouchers = data?.vouchers ?? [];
        const active = vouchers.filter(
          (v) => (v.currentBalance ?? 0) > 0 && ['ACTIVE', 'PARTIALLY_REDEEMED'].includes((v.status || '').toUpperCase())
        );
        this.availableVouchers = active;
        // Product rule: do not show total/summed voucher balance.
        this.voucherBalance = 0;
        this.maxSingleVoucherBalance = 0;
        if (active.length > 0) {
          this.ensureVoucherSelection();
        } else {
          this.selectedVoucherId = undefined;
          this.selectedVoucherBalance = 0;
        }
      },
      error: () => {
        this.availableVouchers = [];
        this.selectedVoucherId = undefined;
        this.selectedVoucherBalance = 0;
      },
    });
  }

  setDuration(hours: number) {
    this.selectedDuration = hours;
    if (hours > 0) {
      const now = new Date();
      const end = new Date(now.getTime() + hours * 60 * 60 * 1000);
      this.fromDt = this.toDatetimeLocal(now);
      this.toDt = this.toDatetimeLocal(end);
    }
    this.updateEstimate();
  }

  toDatetimeLocal(d: Date): string {
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  updateEstimate() {
    if (!this.slot || !this.locationId || !this.fromDt || !this.toDt) return;
    const from = new Date(this.fromDt);
    const to = new Date(this.toDt);
    const durationHours = Math.max(0.25, (to.getTime() - from.getTime()) / 3600000);

    this.estimateLoading = true;
    this.parkingService.getRateEstimate(this.locationId, this.vehicleType, durationHours).subscribe({
      next: (est) => {
        this.priceEstimate = est;
        this.estimatedAmount = est?.amount ?? 0;
        this.ensureVoucherSelection();
        this.estimateLoading = false;
      },
      error: () => {
        this.estimatedAmount = (this.slot?.rate ?? 0) * (this.selectedDuration || 1);
        this.ensureVoucherSelection();
        this.estimateLoading = false;
      },
    });
  }

  canSubmit(): boolean {
    const phoneDigits = this.customerPhone.replace(/\D/g, '');
    return !!(
      this.vehicleNumber.trim() &&
      this.customerName.trim() &&
      phoneDigits.length === 10 &&
      this.fromDt &&
      this.toDt &&
      !!this.selectedVoucherId &&
      this.selectedVoucherBalance >= this.estimatedAmount
    );
  }

  onVoucherChange() {
    const selected = this.availableVouchers.find((v) => v.id === this.selectedVoucherId);
    this.selectedVoucherBalance = selected?.currentBalance ?? 0;
  }

  private ensureVoucherSelection() {
    if (!this.availableVouchers.length) {
      this.selectedVoucherId = undefined;
      this.selectedVoucherBalance = 0;
      return;
    }

    const selected = this.availableVouchers.find((v) => v.id === this.selectedVoucherId);
    if (selected) {
      this.selectedVoucherBalance = selected.currentBalance ?? 0;
      if (this.selectedVoucherBalance >= this.estimatedAmount) return;
    }

    // Auto-pick a voucher that can pay this booking; else pick highest balance.
    const sufficient = this.availableVouchers.find((v) => (v.currentBalance ?? 0) >= this.estimatedAmount);
    const fallback = this.availableVouchers.reduce((best, cur) =>
      (cur.currentBalance ?? 0) > (best.currentBalance ?? 0) ? cur : best
    );
    const pick = sufficient || fallback;
    this.selectedVoucherId = pick.id;
    this.selectedVoucherBalance = pick.currentBalance ?? 0;
  }

  applySelectedVehicle() {
    if (this.selectedVehicleId === 'manual') return;
    const selected = this.registeredVehicles.find((v) => v.id === this.selectedVehicleId);
    if (!selected) return;
    this.vehicleNumber = selected.registrationNumber.toUpperCase();
    this.vehicleType = selected.vehicleType || this.vehicleType;
    this.updateEstimate();
  }

  private normalizeVehicleType(vt: string): string {
    const key = (vt || '').toLowerCase();
    if (['2w', 'two_wheeler', 'bike', 'scooter'].includes(key)) return 'two_wheeler';
    if (['ev', 'electric', 'electric_car'].includes(key)) return 'ev';
    if (['heavy', 'heavy_vehicle', 'truck'].includes(key)) return 'heavy_vehicle';
    return 'four_wheeler';
  }

  goBack() {
    this.router.navigate(['/parking/slot', this.locationId]);
  }

  submitBooking() {
    if (!this.canSubmit() || !this.slot) return;
    this.submitting = true;
    this.errorMsg = '';

    const payload: BookingRequest = {
      locationId: this.locationId,
      slotId: this.slot.id,
      vehicleNumber: this.vehicleNumber,
      vehicleType: this.vehicleType,
      from: new Date(this.fromDt).toISOString(),
      to: new Date(this.toDt).toISOString(),
      customerName: this.customerName,
      customerPhone: '+91' + this.customerPhone,
      customerEmail: this.customerEmail,
    };
    // Optional hint for backend routing; backend may ignore if not implemented.
    (payload as any).voucherId = this.selectedVoucherId;

    this.parkingService.createBooking(payload).subscribe({
      next: (booking: Booking) => {
        this.submitting = false;
        this.router.navigate(['/parking/detail', booking.bookingReference || booking.id]);
      },
      error: (err: any) => {
        this.submitting = false;
        this.errorMsg =
          err?.error?.detail || err?.error?.message || 'Booking failed. Please try again.';
      },
    });
  }

  formatVehicleType(vt: string): string {
    return vt.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
}
