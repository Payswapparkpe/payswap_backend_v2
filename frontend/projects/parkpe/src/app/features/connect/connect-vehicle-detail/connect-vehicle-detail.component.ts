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
import { Subscription } from 'rxjs';

/** Convert snake_case key to user-friendly label (curated list first, then auto-convert). */
const RC_LABEL_MAP: Record<string, string> = {
  vehicle_manufacturer_name: 'Manufacturer',
  model: 'Model',
  type: 'Fuel Type',
  fuel_type: 'Fuel Type',
  vehicle_colour: 'Colour',
  chassis: 'Chassis No.',
  engine: 'Engine No.',
  reg_no: 'Reg. Number',
  reg_authority: 'RTO',
  reg_date: 'Registered On',
  rc_status: 'RC Status',
  rc_expiry_date: 'RC Expiry',
  status: 'Status',
  vehicle_insurance_company_name: 'Insurer',
  vehicle_insurance_upto: 'Insured Till',
  pucc_upto: 'PUC Valid Till',
  pucc_no: 'PUC Cert No.',
  pucc_number: 'PUC Cert No.',
  owner: 'Owner Name',
  address: 'Address',
  is_commercial: 'Usage',
  vehicle_category: 'Vehicle Category',
  vehicle_cubic_capacity: 'Engine Capacity',
  gross_vehicle_weight: 'GVW (kg)',
  norms_type: 'Emission Norms',
  owner_count: 'No. of Owners',
  rc_financer: 'Financer',
  body_type: 'Body Type',
  vehicle_class: 'Vehicle Class',
  class: 'Class',
  permanent_address: 'Permanent Address',
  present_address: 'Present Address',
};

/** Title-case a string (handles ALL CAPS input like "TATA MOTORS PASSENGER VEHICLES LTD"). */
function toTitleCase(s: string): string {
  if (!s) return s;
  // Only convert if the string is all-uppercase (or mostly uppercase)
  const upper = s.replace(/[^a-zA-Z]/g, '');
  if (upper.length === 0 || upper !== upper.toUpperCase()) return s;
  return s
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bLtd\b/g, 'Ltd.')
    .replace(/\bPvt\b/g, 'Pvt.')
    .replace(/\bDto\b/g, 'DTO')
    .replace(/\bRto\b/g, 'RTO');
}

function rcKeyToLabel(key: string): string {
  return RC_LABEL_MAP[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Keys to skip entirely (almost always empty or irrelevant for consumers). */
const RC_SKIP_KEYS = new Set([
  'national_permit_issued_by', 'national_permit_number', 'national_permit_upto',
  'noc_details', 'non_use_from', 'non_use_to', 'non_use_status',
  'challan_details', 'mobile_number', 'owner_father_name',
  'blacklist_status', 'blacklist_details', 'permit_type', 'permit_validity_from', 'permit_validity_upto',
  'financer', 'financer_address', 'wheelbase',
  // split_* are redundant when formatted address is already shown
  'split_permanent_address', 'split_present_address', 'split_address',
]);

/** Format a raw RC value to human-readable string. */
function formatRcValue(key: string, val: unknown): string | null {
  if (val === null || val === undefined || val === '') return null;
  if (typeof val === 'boolean') {
    if (key === 'is_commercial') return val ? 'Commercial use' : 'Private / Personal use';
    return val ? 'Yes' : 'No';
  }
  if (typeof val === 'string') {
    const trimmed = val.trim();
    if (!trimmed || trimmed === '-' || trimmed === 'NA' || trimmed === 'N/A') return null;
    if (key === 'is_commercial') return trimmed.toLowerCase() === 'true' ? 'Commercial use' : 'Private / Personal use';
    const titleCaseKeys = ['vehicle_manufacturer_name', 'model', 'owner', 'reg_authority', 'vehicle_insurance_company_name', 'vehicle_colour', 'body_type', 'vehicle_category', 'rc_financer'];
    if (titleCaseKeys.includes(key)) return toTitleCase(trimmed);
    return trimmed;
  }
  return null;
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

/** Flatten RC object into display rows; only non-empty, relevant fields. */
export function getRcDisplayEntries(rc: VehicleRCData): { label: string; value: string }[] {
  const entries: { label: string; value: string }[] = [];
  for (const key of Object.keys(rc).sort()) {
    if (RC_SKIP_KEYS.has(key)) continue;
    const raw = (rc as Record<string, unknown>)[key];
    const label = rcKeyToLabel(key);
    if (raw === null || raw === undefined) continue;
    if (typeof raw === 'object' && !Array.isArray(raw)) {
      const obj = raw as Record<string, unknown>;
      const value = isAddressLike(obj)
        ? formatAddressObject(obj)
        : JSON.stringify(raw, null, 2);
      if (value && value !== '—') entries.push({ label, value });
    } else if (Array.isArray(raw)) {
      const value = formatRcArray(raw);
      if (value && value !== '—') entries.push({ label, value });
    } else {
      const value = formatRcValue(key, raw);
      if (value) entries.push({ label, value });
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

  fastagRefreshing = signal(false);
  showFastagPanel = computed(() => {
    const v = this.vehicle();
    if (!v) return false;
    return v.vehicle_type === 'four_wheeler' || v.vehicle_type === 'commercial';
  });

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
  private routeParamSub: Subscription | null = null;
  private vehicleLoadSeq = 0;

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
    this.routeParamSub?.unsubscribe();
  }

  ngOnInit() {
    this.routeParamSub = this.route.paramMap.subscribe((params) => {
      const id = params.get('id');
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
      this.loadVehicle(n);
    });
  }

  private loadVehicle(vehicleId: number): void {
    const loadSeq = ++this.vehicleLoadSeq;
    this.loading.set(true);
    this.error.set(null);
    this.qr.set(null);
    this.fastagRefreshing.set(false);
    this.connect.getVehicle(vehicleId).subscribe({
      next: (v) => {
        if (loadSeq !== this.vehicleLoadSeq) return;
        this.vehicle.set(v);
        this.connect.getVehicleQr(vehicleId).subscribe({
          next: (qrData) => {
            if (loadSeq !== this.vehicleLoadSeq) return;
            this.qr.set(qrData);
          },
          error: () => {},
        });
        this.loading.set(false);
      },
      error: (err) => {
        if (loadSeq !== this.vehicleLoadSeq) return;
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

  /** BBPS View Bill — requires FASTag issuer on vehicle (set under Edit). */
  refreshFastagBalance(): void {
    const v = this.vehicle();
    if (!v || !v.fastag_biller_id?.trim() || this.fastagRefreshing()) return;
    this.fastagRefreshing.set(true);
    this.connect.refreshVehicleFastagBalance(v.id).subscribe({
      next: (updated) => {
        this.vehicle.set(updated);
        const cur = this.store.connectVehicles();
        const idx = cur.findIndex((x) => x.id === updated.id);
        const norm = { ...updated, rc_data: updated.vehicle_rc ?? updated.rc_data };
        const next = idx >= 0 ? cur.map((x, i) => (i === idx ? norm : x)) : [...cur, norm];
        this.store.setConnectVehicles(next);
        const ds = this.store.dashboardSummary();
        if (updated.is_primary && updated.fastag_balance != null) {
          this.store.setDashboardSummary({ ...ds, fastagBalance: updated.fastag_balance });
        }
        this.store.notifyConnectVehicleListChanged();
        this.fastagRefreshing.set(false);
      },
      error: () => {
        this.fastagRefreshing.set(false);
      },
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

  /** Compliance alerts derived from RC data (PUC, Insurance). */
  complianceAlerts = computed(() => {
    const v = this.vehicle();
    const rc = v?.vehicle_rc ?? v?.rc_data ?? null;
    if (!rc) return [];
    const alerts: { type: 'critical' | 'warning'; icon: string; title: string; message: string }[] = [];

    // PUC check
    const puc = rc.pucc_upto;
    if (puc && puc !== '—') {
      const d = this._parseDate(puc);
      if (d) {
        const days = Math.ceil((d.getTime() - Date.now()) / 86400000);
        if (days < 0) alerts.push({ type: 'critical', icon: 'air', title: 'PUC Expired', message: `PUC expired on ${puc}. Renew immediately to avoid fines.` });
        else if (days <= 30) alerts.push({ type: 'warning', icon: 'air', title: 'PUC Expiring Soon', message: `PUC valid till ${puc} (${days} day${days === 1 ? '' : 's'} left).` });
      }
    }

    // Insurance check
    const ins = rc.vehicle_insurance_upto;
    if (ins && ins !== '—') {
      const d = this._parseDate(ins);
      if (d) {
        const days = Math.ceil((d.getTime() - Date.now()) / 86400000);
        if (days < 0) alerts.push({ type: 'critical', icon: 'health_and_safety', title: 'Insurance Expired', message: `Insurance expired on ${ins}. Renew to stay legally covered.` });
        else if (days <= 30) alerts.push({ type: 'warning', icon: 'health_and_safety', title: 'Insurance Expiring Soon', message: `Insurance valid till ${ins} (${days} day${days === 1 ? '' : 's'} left).` });
      }
    }

    return alerts;
  });

  private _parseDate(s: string): Date | null {
    if (!s || s === '—') return null;
    const t = s.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(t)) {
      const d = new Date(t);
      return isNaN(d.getTime()) ? null : d;
    }
    const m = t.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    if (m) {
      const date = new Date(parseInt(m[3]), parseInt(m[2]) - 1, parseInt(m[1]));
      return isNaN(date.getTime()) ? null : date;
    }
    return null;
  }

  /** Save full Connect sticker PNG (not only the QR block). */
  async downloadConnectQr() {
    const dataUrl = this.qrImageUrl();
    const v = this.vehicle();
    if (!dataUrl || !v?.registration_number) return;
    const safe = v.registration_number.replace(/[^a-zA-Z0-9_-]/g, '_');
    try {
      const stickerDataUrl = await this.buildStickerImage(dataUrl, v.registration_number);
      this.triggerDownload(stickerDataUrl, `parkpe-connect-sticker-${safe}.png`);
    } catch {
      // Fallback: if sticker composition fails, at least download QR image.
      this.triggerDownload(dataUrl, `parkpe-connect-qr-${safe}.png`);
    }
  }

  private triggerDownload(url: string, filename: string) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.rel = 'noopener';
    a.click();
  }

  private async buildStickerImage(qrDataUrl: string, registrationNumber: string): Promise<string> {
    const width = 1400;
    const height = 680;
    const stripeHeight = 24;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas not available');

    // Rounded outer sticker with blue gradient background.
    this.roundRect(ctx, 0, 0, width, height, 28);
    const bg = ctx.createLinearGradient(0, 0, width, height);
    bg.addColorStop(0, '#0f2d6b');
    bg.addColorStop(0.5, '#1a3d7a');
    bg.addColorStop(1, '#0d2563');
    ctx.fillStyle = bg;
    ctx.fill();

    // Top content area (exclude safety stripe).
    const contentBottom = height - stripeHeight;
    const leftPad = 58;
    const topPad = 56;

    // Logo (best effort). If logo fails, fallback title text is drawn.
    let drewLogo = false;
    try {
      const logo = await this.loadImage('assets/parkpe-logo-dark-bg.svg');
      ctx.drawImage(logo, leftPad, topPad, 210, 100);
      drewLogo = true;
    } catch {
      drewLogo = false;
    }
    if (!drewLogo) {
      ctx.fillStyle = '#ffffff';
      ctx.font = '700 54px Inter, Arial, sans-serif';
      ctx.fillText('Park Pe', leftPad + 6, topPad + 72);
    }

    ctx.fillStyle = '#ffffff';
    ctx.font = '600 58px Inter, Arial, sans-serif';
    ctx.fillText('Scan to contact owner', leftPad, 340);

    // Icon row (text approximation for portable canvas render).
    ctx.fillStyle = 'rgba(255, 255, 255, 0.94)';
    ctx.font = '700 64px Inter, Arial, sans-serif';
    ctx.fillText('P', leftPad + 10, 452);
    ctx.font = '700 50px Inter, Arial, sans-serif';
    ctx.fillText('TRUCK', leftPad + 104, 450);
    ctx.fillText('NO CALL', leftPad + 310, 450);

    ctx.fillStyle = 'rgba(255, 255, 255, 0.88)';
    ctx.font = '500 44px Inter, Arial, sans-serif';
    ctx.fillText('Privacy Protected • No Number Sharing', leftPad, 535);

    // QR block area.
    const qrCardSize = 370;
    const qrCardX = width - leftPad - qrCardSize;
    const qrCardY = 58;
    this.roundRect(ctx, qrCardX, qrCardY, qrCardSize, qrCardSize, 20);
    ctx.fillStyle = '#ffffff';
    ctx.fill();

    const qrImage = await this.loadImage(qrDataUrl);
    const qrInnerPad = 24;
    ctx.drawImage(
      qrImage,
      qrCardX + qrInnerPad,
      qrCardY + qrInnerPad,
      qrCardSize - qrInnerPad * 2,
      qrCardSize - qrInnerPad * 2
    );

    // Registration number under QR.
    const reg = registrationNumber.toUpperCase();
    ctx.fillStyle = '#ffffff';
    ctx.font = '800 66px Inter, Arial, sans-serif';
    const regWidth = ctx.measureText(reg).width;
    ctx.fillText(reg, qrCardX + (qrCardSize - regWidth) / 2, contentBottom - 56);

    // Bottom yellow-black stripe.
    let x = 0;
    const stripeW = 34;
    while (x < width + stripeW) {
      ctx.fillStyle = '#facc15';
      ctx.beginPath();
      ctx.moveTo(x, contentBottom);
      ctx.lineTo(x + stripeW, contentBottom);
      ctx.lineTo(x + stripeW - 12, height);
      ctx.lineTo(x - 12, height);
      ctx.closePath();
      ctx.fill();

      ctx.fillStyle = '#1f2937';
      ctx.beginPath();
      ctx.moveTo(x + stripeW, contentBottom);
      ctx.lineTo(x + stripeW * 2, contentBottom);
      ctx.lineTo(x + stripeW * 2 - 12, height);
      ctx.lineTo(x + stripeW - 12, height);
      ctx.closePath();
      ctx.fill();
      x += stripeW * 2;
    }

    return canvas.toDataURL('image/png');
  }

  private loadImage(src: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error(`Failed to load image: ${src}`));
      img.src = src;
    });
  }

  private roundRect(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    radius: number
  ) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + width, y, x + width, y + height, r);
    ctx.arcTo(x + width, y + height, x, y + height, r);
    ctx.arcTo(x, y + height, x, y, r);
    ctx.arcTo(x, y, x + width, y, r);
    ctx.closePath();
  }
}
