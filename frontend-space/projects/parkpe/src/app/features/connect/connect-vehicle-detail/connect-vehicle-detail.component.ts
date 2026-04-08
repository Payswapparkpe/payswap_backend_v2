import { Component, inject, OnDestroy, OnInit, signal, computed, effect } from '@angular/core';
import QRCode from 'qrcode';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ConnectService, ConnectVehicle, VehicleQRResponse } from '../services/connect.service';
import { VoucherService } from '../../voucher/services/voucher.service';
import { getVehicleTypeLabel } from '../data/vehicle-types-data';
import type { VehicleRCData } from '../services/connect.service';
import type { VoucherListItem } from '../../../core/models/voucher.model';
import { MobilityStateStore } from '../../../core/stores/mobility-state.store';

/** Convert snake_case key to Title Case label (e.g. reg_no -> Reg no) */
function rcKeyToLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Normalise array from API (can be string[] or string[][] or mixed) to a single readable string. */
function formatRcArray(val: unknown): string {
  if (val == null) return '—';
  if (!Array.isArray(val)) return String(val);
  const parts: string[] = [];
  for (const item of val) {
    if (Array.isArray(item)) {
      parts.push(item.map((x) => (x != null ? String(x) : '')).join(' ').trim());
    } else if (item != null && item !== '') {
      parts.push(String(item));
    }
  }
  return parts.filter(Boolean).join(', ') || '—';
}

/** Check if object looks like Cashfree split address (district, state, city, pincode, etc.). */
function isAddressLike(obj: Record<string, unknown>): boolean {
  const keys = Object.keys(obj);
  return keys.some((k) =>
    ['district', 'state', 'city', 'pincode', 'country', 'address_line'].includes(k)
  );
}

/** Format address-like object as readable lines instead of raw JSON. */
function formatAddressObject(obj: Record<string, unknown>): string {
  const order = ['address_line', 'district', 'city', 'state', 'pincode', 'country'];
  const lines: string[] = [];
  const seen = new Set<string>();
  for (const key of order) {
    const val = obj[key];
    if (val === undefined) continue;
    const label = rcKeyToLabel(key);
    const str = Array.isArray(val)
      ? formatRcArray(val)
      : typeof val === 'object' && val !== null
        ? formatRcArray((val as unknown[])?.flat?.() ?? [val])
        : String(val ?? '—');
    if (str && str !== '—') {
      lines.push(`${label}: ${str}`);
      seen.add(key);
    }
  }
  for (const key of Object.keys(obj).sort()) {
    if (seen.has(key)) continue;
    const val = obj[key];
    const label = rcKeyToLabel(key);
    const str =
      typeof val === 'object' && val !== null
        ? Array.isArray(val)
          ? formatRcArray(val)
          : JSON.stringify(val)
        : String(val ?? '—');
    if (str && str !== '—') lines.push(`${label}: ${str}`);
  }
  return lines.join('\n') || '—';
}

/** Flatten RC object into display rows; address-like objects formatted readably. */
export function getRcDisplayEntries(rc: VehicleRCData): { label: string; value: string }[] {
  const entries: { label: string; value: string }[] = [];
  for (const key of Object.keys(rc).sort()) {
    const val = (rc as Record<string, unknown>)[key];
    const label = rcKeyToLabel(key);
    if (val === null || val === undefined) {
      entries.push({ label, value: '—' });
    } else if (typeof val === 'object' && !Array.isArray(val)) {
      const obj = val as Record<string, unknown>;
      const value = isAddressLike(obj)
        ? formatAddressObject(obj)
        : JSON.stringify(val, null, 2);
      entries.push({ label, value });
    } else if (Array.isArray(val)) {
      entries.push({ label, value: formatRcArray(val) });
    } else {
      entries.push({ label, value: String(val) });
    }
  }
  return entries;
}

/** Group RC entries into cards: Vehicle, Registration, Insurance, Owner & address, Other. */
const RC_CARD_GROUPS: { keys: string[]; title: string }[] = [
  { title: 'Vehicle', keys: ['vehicle_manufacturer_name', 'model', 'type', 'vehicle_colour', 'chassis', 'engine'] },
  { title: 'Registration', keys: ['reg_no', 'reg_authority', 'reg_date', 'rc_status', 'rc_expiry_date', 'status'] },
  { title: 'Insurance', keys: ['vehicle_insurance_company_name', 'vehicle_insurance_upto'] },
  { title: 'Owner & address', keys: ['owner', 'address', 'address_line', 'district', 'city', 'state', 'pincode', 'country'] },
];

export function getRcCardGroups(rc: VehicleRCData): { title: string; rows: { label: string; value: string }[] }[] {
  const entries = getRcDisplayEntries(rc);
  const labelToEntry = new Map(entries.map((e) => [e.label, e]));
  const used = new Set<string>();
  const result: { title: string; rows: { label: string; value: string }[] }[] = [];
  for (const group of RC_CARD_GROUPS) {
    const rows: { label: string; value: string }[] = [];
    for (const key of group.keys) {
      const label = rcKeyToLabel(key);
      const entry = labelToEntry.get(label);
      if (entry) {
        rows.push(entry);
        used.add(entry.label);
      }
    }
    if (rows.length) result.push({ title: group.title, rows });
  }
  const other = entries.filter((e) => !used.has(e.label));
  if (other.length) result.push({ title: 'Other', rows: other });
  return result;
}

const RC_VIEW_AMOUNT = 50;

@Component({
  selector: 'app-connect-vehicle-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, ReactiveFormsModule],
  templateUrl: './connect-vehicle-detail.component.html',
  styleUrl: './connect-vehicle-detail.component.scss',
})
export class ConnectVehicleDetailComponent implements OnInit, OnDestroy {
  private connect = inject(ConnectService);
  private voucherService = inject(VoucherService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private fb = inject(FormBuilder);
  private store = inject(MobilityStateStore);
  getVehicleTypeLabel = getVehicleTypeLabel;
  getRcDisplayEntries = getRcDisplayEntries;
  getRcCardGroups = getRcCardGroups;

  vehicle = signal<ConnectVehicle | null>(null);
  qr = signal<VehicleQRResponse | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);

  /** Delete flow: OTP requested and modal visible */
  deleteModalOpen = signal(false);
  deleteOtpSent = signal(false);
  deleteOtp = signal('');
  deleteError = signal<string | null>(null);
  deleteInProgress = signal(false);
  deleteRequestInProgress = signal(false);

  /** RC fetch (Get more data) */
  fetchRcInProgress = signal(false);
  rcError = signal<string | null>(null);

  /** Pay Rs 50 from voucher to view full RC – modal: select voucher + enter PIN */
  payRcModalOpen = signal(false);
  payRcConfirmStep = signal(false);
  payRcModalVouchers = signal<VoucherListItem[]>([]);
  payRcModalVouchersLoading = signal(false);
  payRcInProgress = signal(false);
  payRcError = signal<string | null>(null);
  payRcForm = this.fb.nonNullable.group({
    voucher_id: [0 as number, [Validators.required, Validators.min(1)]],
    pin: ['', [Validators.required, Validators.minLength(4), Validators.maxLength(6)]],
  });

  /** Verify ownership to unlock RC (when rc_locked) */
  verifyOwnershipForm = this.fb.nonNullable.group({
    owner_name: ['', [Validators.required]],
    chassis_number: ['', [Validators.required]],
    engine_number: ['', [Validators.required]],
  });
  verifyInProgress = signal(false);
  verifyError = signal<string | null>(null);

  /** Scan URL encoded in the QR (same-origin path or absolute scan_url from API). */
  qrData = computed(() => {
    const q = this.qr();
    return q?.scan_path
      ? `${window.location.origin}${q.scan_path}`
      : (q?.scan_url ?? null);
  });

  /** PNG data URL for sticker `<img>` (generated locally from `qrData`, no third-party image API). */
  qrImageUrl = signal<string | null>(null);
  private qrImageGen = 0;

  constructor() {
    effect(() => {
      const data = this.qrData();
      if (!data) {
        this.qrImageUrl.set(null);
        return;
      }
      const id = ++this.qrImageGen;
      void QRCode.toDataURL(data, { width: 200, margin: 2, errorCorrectionLevel: 'M' }).then(
        (url) => {
          if (id === this.qrImageGen) this.qrImageUrl.set(url);
        }
      );
    });

    effect(() => {
      const v = this.vehicle();
      const qrData = this.qrData();
      const qrImageUrl = this.qrImageUrl();
      if (!v || !qrData || !qrImageUrl) return;
      this.store.setConnectQrSnapshot({
        vehicleId: v.id,
        registrationNumber: v.registration_number,
        qrData,
        qrImageUrl,
      });
    });
  }

  ngOnDestroy(): void {
    if (this.copyFeedbackTimer) clearTimeout(this.copyFeedbackTimer);
  }

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      this.error.set('Invalid vehicle');
      this.loading.set(false);
      return;
    }
    const n = parseInt(id, 10);
    if (isNaN(n)) {
      this.error.set('Invalid vehicle');
      this.loading.set(false);
      return;
    }
    this.connect.getVehicle(n).subscribe({
      next: (v) => {
        this.vehicle.set(v);
        this.connect.getVehicleQr(n).subscribe({
          next: (qrData) => this.qr.set(qrData),
          error: () => {},
        });
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.status === 401 ? 'Session expired. Please log in again.' : 'Vehicle not found');
        this.loading.set(false);
      },
    });
  }

  openDeleteModal() {
    this.deleteModalOpen.set(true);
    this.deleteOtpSent.set(false);
    this.deleteOtp.set('');
    this.deleteError.set(null);
  }

  cancelDelete() {
    this.deleteModalOpen.set(false);
    this.deleteOtpSent.set(false);
    this.deleteOtp.set('');
    this.deleteError.set(null);
  }

  onDeleteOtpInput(e: Event) {
    const el = e.target as HTMLInputElement;
    if (el) this.deleteOtp.set(el.value);
  }

  requestDeleteOtp() {
    const v = this.vehicle();
    if (!v || this.deleteRequestInProgress()) return;
    this.deleteError.set(null);
    this.deleteRequestInProgress.set(true);
    this.connect.requestDeleteOtp(v.id).subscribe({
      next: () => {
        this.deleteOtpSent.set(true);
        this.deleteRequestInProgress.set(false);
      },
      error: (err) => {
        const msg = err?.error?.detail || err?.message || 'Failed to send OTP';
        this.deleteError.set(msg);
        this.deleteRequestInProgress.set(false);
      },
    });
  }

  confirmDelete() {
    const v = this.vehicle();
    const otp = this.deleteOtp().trim();
    if (!v || !otp || this.deleteInProgress()) return;
    this.deleteError.set(null);
    this.deleteInProgress.set(true);
    this.connect.confirmDeleteVehicle(v.id, otp).subscribe({
      next: () => {
        this.deleteModalOpen.set(false);
        const rest = this.store.connectVehicles().filter((x) => x.id !== v.id);
        this.store.setConnectVehicles(rest);
        this.store.notifyConnectVehicleListChanged();
        this.router.navigate(['/connect/vehicles']);
      },
      error: (err) => {
        this.deleteError.set(err?.error?.detail || err?.message || 'Invalid or expired OTP');
        this.deleteInProgress.set(false);
      },
    });
  }

  getMoreData() {
    const v = this.vehicle();
    if (!v || this.fetchRcInProgress()) return;
    this.rcError.set(null);
    this.fetchRcInProgress.set(true);
    this.connect.fetchVehicleRc(v.id).subscribe({
      next: (updated) => {
        const payload = updated as ConnectVehicle & { rc_message?: string };
        if (payload.rc_message) {
          this.rcError.set(payload.rc_message);
        } else {
          this.rcError.set(null);
        }
        const { rc_message: _, ...vehicleData } = payload;
        this.vehicle.set(vehicleData as ConnectVehicle);
        this.fetchRcInProgress.set(false);
      },
      error: (err) => {
        this.rcError.set(err?.error?.detail || err?.message || 'Failed to fetch RC data');
        this.fetchRcInProgress.set(false);
      },
    });
  }

  /** Refetch vehicle (e.g. after successful unlock). */
  refetchVehicle() {
    const v = this.vehicle();
    if (!v) return;
    this.connect.getVehicle(v.id).subscribe({
      next: (updated) => this.vehicle.set(updated),
      error: () => {},
    });
  }

  verifyOwnership() {
    const v = this.vehicle();
    if (!v || this.verifyInProgress() || this.verifyOwnershipForm.invalid) return;
    this.verifyError.set(null);
    this.verifyInProgress.set(true);
    const raw = this.verifyOwnershipForm.getRawValue();
    this.connect.unlockVehicleRc(v.id, {
      owner_name: raw.owner_name.trim(),
      chassis_number: raw.chassis_number.trim(),
      engine_number: raw.engine_number.trim(),
    }).subscribe({
      next: () => {
        this.verifyInProgress.set(false);
        this.verifyError.set(null);
        this.refetchVehicle();
      },
      error: (err) => {
        this.verifyError.set(err?.error?.detail || err?.message || 'Verification failed.');
        this.verifyInProgress.set(false);
      },
    });
  }

  /** Open Pay RC modal: load vouchers with balance >= 50, then user selects voucher and enters PIN. */
  openPayModal() {
    this.payRcModalOpen.set(true);
    this.payRcConfirmStep.set(false);
    this.payRcError.set(null);
    this.payRcForm.reset({ voucher_id: 0, pin: '' });
    this.payRcModalVouchersLoading.set(true);
    this.payRcModalVouchers.set([]);
    this.voucherService.getVouchers({ limit: 100 }).subscribe({
      next: (res) => {
        const eligible = (res.vouchers ?? []).filter((v) => v.currentBalance >= RC_VIEW_AMOUNT);
        this.payRcModalVouchers.set(eligible);
        this.payRcModalVouchersLoading.set(false);
        if (eligible.length === 1) this.payRcForm.patchValue({ voucher_id: eligible[0].id });
      },
      error: () => {
        this.payRcModalVouchers.set([]);
        this.payRcModalVouchersLoading.set(false);
      },
    });
  }

  closePayModal() {
    this.payRcModalOpen.set(false);
    this.payRcConfirmStep.set(false);
    this.payRcError.set(null);
  }

  /** Show confirmation step before submitting RC pay. */
  proceedToRcPayConfirm() {
    if (this.payRcForm.invalid) return;
    this.payRcError.set(null);
    this.payRcConfirmStep.set(true);
  }

  /** Submit Pay RC: send selected voucher_id + pin to backend. */
  submitPayRc() {
    const v = this.vehicle();
    if (!v || this.payRcInProgress()) return;
    if (this.payRcForm.invalid) return;
    const { voucher_id, pin } = this.payRcForm.getRawValue();
    if (!voucher_id || !pin) return;
    this.payRcError.set(null);
    this.payRcInProgress.set(true);
    this.connect.payRcView(v.id, { voucher_id, pin }).subscribe({
      next: (res) => {
        this.payRcInProgress.set(false);
        this.payRcError.set(null);
        this.closePayModal();
        if (res.vehicle) this.vehicle.set(res.vehicle);
      },
      error: (err) => {
        this.payRcError.set(err?.error?.detail || err?.message || 'Payment failed.');
        this.payRcInProgress.set(false);
      },
    });
  }

  /** Open chat for this vehicle (get or create thread by QR, then navigate). */
  openChat() {
    const v = this.vehicle();
    const qrCode = this.qr()?.qr_code;
    if (!v || !qrCode) return;
    this.connect.getOrCreateThread(qrCode).subscribe({
      next: (thread) => this.router.navigate(['/connect/chats', thread.id]),
      error: () => {},
    });
  }

  /** Copy feedback after copying registration (clipboard). */
  copyFeedback = signal<'idle' | 'copied' | 'failed'>('idle');
  private copyFeedbackTimer: ReturnType<typeof setTimeout> | null = null;

  copyRegistration(registrationNumber: string) {
    const text = (registrationNumber || '').trim();
    if (!text) return;

    const done = (ok: boolean) => {
      this.copyFeedback.set(ok ? 'copied' : 'failed');
      if (this.copyFeedbackTimer) clearTimeout(this.copyFeedbackTimer);
      this.copyFeedbackTimer = setTimeout(() => this.copyFeedback.set('idle'), 2200);
    };

    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(text).then(
        () => done(true),
        () => this._copyRegistrationFallback(text, done)
      );
      return;
    }
    this._copyRegistrationFallback(text, done);
  }

  private _copyRegistrationFallback(text: string, done: (ok: boolean) => void) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      done(ok);
    } catch {
      done(false);
    }
  }

  /** Save generated QR PNG (same image as on the sticker). */
  downloadConnectQr() {
    const dataUrl = this.qrImageUrl();
    const v = this.vehicle();
    if (!dataUrl || !v?.registration_number) return;
    const safe = v.registration_number.replace(/[^a-zA-Z0-9_-]/g, '_');
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `parkpe-connect-qr-${safe}.png`;
    a.rel = 'noopener';
    a.click();
  }
}
