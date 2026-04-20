import { Component, input, computed, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import type { ConnectVehicle, VehicleRCData } from '../services/connect.service';
import { getVehicleTypeLabel } from '../data/vehicle-types-data';

export type StatusChip = {
  label: string;
  status: 'ok' | 'warning' | 'critical' | 'info' | 'balance';
  icon: string;
};

function truncateVehicleDetails(s: string, maxLen: number): string {
  const t = s.trim();
  if (!t || t === '—') return t;
  if (t.length <= maxLen) return t;
  return `${t.slice(0, Math.max(0, maxLen - 1)).trimEnd()}…`;
}

/** Parse date string (YYYY-MM-DD or DD-MM-YYYY) to Date; null if invalid. */
function parseDate(s: string): Date | null {
  if (!s || s === '—' || typeof s !== 'string') return null;
  const t = s.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(t)) {
    const d = new Date(t);
    return isNaN(d.getTime()) ? null : d;
  }
  const match = t.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
  if (match) {
    const d = parseInt(match[1], 10);
    const m = parseInt(match[2], 10) - 1;
    const y = parseInt(match[3], 10);
    const date = new Date(y, m, d);
    if (date.getFullYear() === y && date.getMonth() === m && date.getDate() === d) return date;
  }
  return null;
}

function isDateActive(dateStr: string): boolean {
  const d = parseDate(dateStr);
  if (!d) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  d.setHours(0, 0, 0, 0);
  return d.getTime() >= today.getTime();
}

@Component({
  selector: 'app-connect-vehicle-card',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-vehicle-card.component.html',
  styleUrl: './connect-vehicle-card.component.scss',
})
export class ConnectVehicleCardComponent {
  /** The vehicle to display (from Connect API + optional RC data). */
  vehicle = input.required<ConnectVehicle>();
  /** Fallback FASTag amount when `vehicle.fastag_balance` is unset (e.g. dashboard wallet total). */
  fastagBalance = input<number | null>(null);
  /** Compact mode: hide action bar, smaller padding (e.g. list view). */
  compact = input<boolean>(false);
  /**
   * Dashboard: shorter card, no fixed height, truncated meta, Recharge + Connect only (no Manage).
   */
  variant = input<'default' | 'dashboard'>('default');
  /**
   * When dashboard + exactly one vehicle on the page: use a horizontal strip on wide screens
   * (details left, chips + actions right).
   */
  dashboardSingleRow = input(false);
  /** Show "View & QR" as primary; when false, card may be used in dashboard carousel. */
  showViewLink = input<boolean>(true);
  /** Parent handles BBPS refresh API for this vehicle id. */
  fastagRefreshRequested = output<number>();
  /** Parent-provided loading state for FASTag refresh action. */
  fastagRefreshing = input<boolean>(false);

  isDashboard = computed(() => this.variant() === 'dashboard');

  /** Single-vehicle dashboard layout (parent passes true when only one card is shown). */
  isDashboardRow = computed(() => this.isDashboard() && this.dashboardSingleRow());

  private v = computed(() => this.vehicle());
  private rc = computed(() => this.v().vehicle_rc ?? this.v().rc_data ?? null);

  getVehicleTypeLabel = getVehicleTypeLabel;

  /** Car = show FASTag; Bike = no FASTag; EV = Coming Soon only. */
  isCar = computed(() => {
    const t = (this.v().vehicle_type || '').toLowerCase();
    return t === 'four_wheeler' || t.includes('car') || t === 'fourwheeler';
  });

  isBike = computed(() => {
    const t = (this.v().vehicle_type || '').toLowerCase();
    return t === 'two_wheeler' || t.includes('two') || t.includes('bike') || t.includes('scooter') || t.includes('motorcycle');
  });

  isEv = computed(() => {
    const r = this.rc();
    if (!r) return false;
    const rec = r as Record<string, unknown>;
    const fuel = String(rec['fuel_type'] ?? rec['type'] ?? '').toLowerCase();
    const maker = String(rec['vehicle_manufacturer_name'] ?? '').toLowerCase();
    return fuel.includes('electric') || maker.includes('ola') || maker.includes('ather') || maker.includes('electric');
  });

  /** RC Verified when we have RC data from Cashfree/govt API. */
  isRcVerified = computed(() => !!this.rc());

  /** No RC data yet (or locked): CTA links to vehicle detail to fetch verified RC. */
  needsRcInfo = computed(() => !this.rc());

  /** Display fuel type from RC (compliance-safe). */
  fuelLabel = computed(() => {
    const r = this.rc();
    if (!r) return null;
    const rec = r as Record<string, unknown>;
    const fuel = rec['fuel_type'] ?? rec['type'];
    return fuel ? String(fuel) : null;
  });

  /** Brand + model from RC or vehicle. */
  brandModel = computed(() => {
    const v = this.v();
    const r = this.rc();
    const brand = (r as VehicleRCData | undefined)?.vehicle_manufacturer_name || v.brand || '';
    const model = (r as VehicleRCData | undefined)?.model || v.model || '';
    return [brand, model].filter(Boolean).join(' ') || '—';
  });

  /** Truncated make/model for dense dashboard cards; full string in `brandModel` for tooltips. */
  displayBrandModel = computed(() =>
    truncateVehicleDetails(this.brandModel(), this.isDashboard() ? 56 : 72),
  );

  /**
   * FASTag balance for display (car only). Prefers per-vehicle API value, then optional parent fallback
   * (e.g. dashboard wallet aggregate) when the vehicle has no tag balance yet.
   */
  fastagDisplay = computed(() => {
    if (!this.isCar()) return null;
    const fromVehicle = this.v().fastag_balance;
    if (fromVehicle !== null && fromVehicle !== undefined) return fromVehicle;
    const fromInput = this.fastagBalance();
    if (fromInput !== null && fromInput !== undefined) return fromInput;
    return null;
  });

  /** Low FASTag balance threshold (₹200). */
  isLowFastagBalance = computed(() => {
    const b = this.fastagDisplay();
    return b !== null && b < 200;
  });

  /** Status chips: PUC, Insurance, FASTag (car), EV placeholder (ev). No fake data. */
  statusChips = computed(() => {
    const chips: StatusChip[] = [];
    const r = this.rc();

    /** No verified RC yet: show what is unknown vs what we can still show (e.g. FASTag by number). */
    if (!r) {
      chips.push({ label: 'RC not verified', status: 'warning', icon: 'fact_check' });
      if (this.isEv()) {
        chips.push({ label: 'Charging Coming Soon', status: 'info', icon: 'ev_station' });
        return chips;
      }
      const bal = this.fastagDisplay();
      if (this.isCar() && bal !== null) {
        if (this.isLowFastagBalance()) {
          chips.push({ label: `₹${bal} · Low balance`, status: 'balance', icon: 'toll' });
        } else {
          chips.push({ label: `FASTag ₹${bal}`, status: 'ok', icon: 'toll' });
        }
      }
      chips.push({ label: 'PUC: unknown', status: 'info', icon: 'air' });
      chips.push({ label: 'Insurance: unknown', status: 'info', icon: 'health_and_safety' });
      return chips;
    }

    // EV: only "Charging Coming Soon"
    if (this.isEv()) {
      chips.push({ label: 'Charging Coming Soon', status: 'info', icon: 'ev_station' });
      return chips;
    }

    // FASTag (car only)
    const bal = this.fastagDisplay();
    if (bal !== null) {
      if (this.isLowFastagBalance()) {
        chips.push({ label: `₹${bal} · Low balance`, status: 'balance', icon: 'toll' });
      } else {
        chips.push({ label: `FASTag ₹${bal}`, status: 'ok', icon: 'toll' });
      }
    }

    // PUC
    const pucc = r?.pucc_upto;
    if (pucc && pucc !== '—') {
      const active = isDateActive(pucc);
      chips.push({
        label: active ? `PUC till ${formatShortDate(pucc)}` : 'PUC Expired',
        status: active ? 'ok' : 'critical',
        icon: 'air',
      });
    } else {
      chips.push({ label: 'Check PUC', status: 'info', icon: 'air' });
    }

    // Insurance
    const insUpto = r?.vehicle_insurance_upto;
    if (insUpto && insUpto !== '—') {
      const active = isDateActive(insUpto);
      const daysLeft = parseDate(insUpto) ? Math.ceil(((parseDate(insUpto)!.getTime() - Date.now()) / (1000 * 60 * 60 * 24))) : 0;
      let status: StatusChip['status'] = active ? 'ok' : 'critical';
      if (active && daysLeft <= 30) status = 'warning';
      chips.push({
        label: status === 'critical' ? 'Ins. Expired' : status === 'warning' ? `Ins. till ${formatShortDate(insUpto)}` : `Ins. till ${formatShortDate(insUpto)}`,
        status,
        icon: 'health_and_safety',
      });
    } else {
      chips.push({ label: 'Add Insurance', status: 'warning', icon: 'add_moderator' });
    }

    return chips;
  });

  /** RC status line (Active/Inactive) from API. */
  rcStatusLabel = computed(() => {
    const r = this.rc();
    const status = r != null ? (r as Record<string, unknown>)['rc_status'] : undefined;
    return status != null ? String(status) : null;
  });

  /** Overall compliance health of this vehicle (worst chip wins). */
  cardHealthStatus = computed<'critical' | 'warning' | 'ok'>(() => {
    const chips = this.statusChips();
    if (chips.some(c => c.status === 'critical')) return 'critical';
    if (chips.some(c => c.status === 'warning' || c.status === 'balance')) return 'warning';
    return 'ok';
  });

  /** True when FASTag is critically low (≤ ₹0). */
  isCriticalFastagBalance = computed(() => {
    const b = this.fastagDisplay();
    return b !== null && b <= 0;
  });

  /** Formatted FASTag balance with sign for display (e.g. "₹0", "₹500"). */
  fastagBalanceLabel = computed(() => {
    const b = this.fastagDisplay();
    return b !== null ? `₹${b}` : null;
  });

  /** Percentage for FASTag mini-bar (0–100, cap at 100, threshold ₹1000). */
  fastagBalancePct = computed(() => {
    const b = this.fastagDisplay();
    if (b === null) return 0;
    return Math.min(100, Math.round((Math.max(0, b) / 1000) * 100));
  });

  canRefreshFastag = computed(() => this.isCar() && !!(this.v().fastag_biller_id || '').trim());

  requestFastagRefresh(event?: Event): void {
    event?.preventDefault();
    event?.stopPropagation();
    if (!this.canRefreshFastag() || this.fastagRefreshing()) return;
    this.fastagRefreshRequested.emit(this.v().id);
  }
}

function formatShortDate(s: string): string {
  const d = parseDate(s);
  if (!d) return s;
  const day = d.getDate();
  const month = d.toLocaleString('en-IN', { month: 'short' });
  const year = d.getFullYear();
  return `${day}-${month}-${year}`;
}
