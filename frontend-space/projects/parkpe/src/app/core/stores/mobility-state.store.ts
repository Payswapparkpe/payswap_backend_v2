import { Injectable, computed, signal } from '@angular/core';
import type { ConnectVehicle } from '../../features/connect/services/connect.service';
import type { Booking } from '../models/parking.model';

type DashboardSummary = {
  totalSpendMonth: number;
  pendingChallans: number;
  fastagBalance: number;
  activeBookings: number;
};

type Snapshot<T> = { ts: number; data: T };
export type ConnectQrSnapshot = {
  vehicleId: number;
  registrationNumber: string;
  qrData: string;
  qrImageUrl: string;
};
export type PaymentStatusSnapshot = {
  tone: 'success' | 'error' | 'warning';
  orderRef: string;
  gatewayRef: string;
  amount: number | null;
  statusMessage: string;
  headline: string;
  gatewayLabel: string;
};

@Injectable({ providedIn: 'root' })
export class MobilityStateStore {
  private readonly DASHBOARD_KEY = 'parkpe:snapshot:dashboard-summary';
  private readonly VEHICLES_KEY = 'parkpe:snapshot:connect-vehicles';
  private readonly ACTIVE_BOOKING_KEY = 'parkpe:snapshot:active-booking';
  private readonly CONNECT_QR_KEY = 'parkpe:snapshot:connect-qr';
  private readonly PAYMENT_STATUS_KEY = 'parkpe:snapshot:payment-status';

  readonly dashboardSummary = signal<DashboardSummary>({
    totalSpendMonth: 0,
    pendingChallans: 0,
    fastagBalance: 0,
    activeBookings: 0,
  });
  readonly dashboardSummaryTs = signal<number | null>(null);

  readonly connectVehicles = signal<ConnectVehicle[]>([]);
  readonly connectVehiclesTs = signal<number | null>(null);

  readonly activeBooking = signal<Booking | null>(null);
  readonly activeBookingTs = signal<number | null>(null);
  readonly connectQrSnapshot = signal<ConnectQrSnapshot | null>(null);
  readonly connectQrSnapshotTs = signal<number | null>(null);
  readonly paymentStatusSnapshot = signal<PaymentStatusSnapshot | null>(null);
  readonly paymentStatusSnapshotTs = signal<number | null>(null);

  readonly hasOfflineSnapshot = computed(
    () =>
      this.dashboardSummaryTs() != null ||
      this.connectVehiclesTs() != null ||
      this.activeBookingTs() != null ||
      this.connectQrSnapshotTs() != null ||
      this.paymentStatusSnapshotTs() != null
  );

  constructor() {
    const dashboard = this.read<DashboardSummary>(this.DASHBOARD_KEY);
    const vehicles = this.read<ConnectVehicle[]>(this.VEHICLES_KEY);
    const booking = this.read<Booking>(this.ACTIVE_BOOKING_KEY);
    const connectQr = this.read<ConnectQrSnapshot>(this.CONNECT_QR_KEY);
    const payment = this.read<PaymentStatusSnapshot>(this.PAYMENT_STATUS_KEY);

    this.dashboardSummary.set(dashboard?.data ?? this.dashboardSummary());
    this.dashboardSummaryTs.set(dashboard?.ts ?? null);
    this.connectVehicles.set(vehicles?.data ?? []);
    this.connectVehiclesTs.set(vehicles?.ts ?? null);
    this.activeBooking.set(booking?.data ?? null);
    this.activeBookingTs.set(booking?.ts ?? null);
    this.connectQrSnapshot.set(connectQr?.data ?? null);
    this.connectQrSnapshotTs.set(connectQr?.ts ?? null);
    this.paymentStatusSnapshot.set(payment?.data ?? null);
    this.paymentStatusSnapshotTs.set(payment?.ts ?? null);
  }

  setDashboardSummary(summary: DashboardSummary): void {
    this.dashboardSummary.set(summary);
    this.dashboardSummaryTs.set(Date.now());
    this.write(this.DASHBOARD_KEY, summary);
  }

  setConnectVehicles(vehicles: ConnectVehicle[]): void {
    this.connectVehicles.set(vehicles);
    this.connectVehiclesTs.set(Date.now());
    this.write(this.VEHICLES_KEY, vehicles);
  }

  setActiveBooking(booking: Booking | null): void {
    this.activeBooking.set(booking);
    this.activeBookingTs.set(booking ? Date.now() : null);
    if (booking) this.write(this.ACTIVE_BOOKING_KEY, booking);
  }

  setConnectQrSnapshot(snapshot: ConnectQrSnapshot): void {
    this.connectQrSnapshot.set(snapshot);
    this.connectQrSnapshotTs.set(Date.now());
    this.write(this.CONNECT_QR_KEY, snapshot);
  }

  setPaymentStatusSnapshot(snapshot: PaymentStatusSnapshot): void {
    this.paymentStatusSnapshot.set(snapshot);
    this.paymentStatusSnapshotTs.set(Date.now());
    this.write(this.PAYMENT_STATUS_KEY, snapshot);
  }

  private write<T>(key: string, data: T): void {
    if (typeof localStorage === 'undefined') return;
    try {
      const payload: Snapshot<T> = { ts: Date.now(), data };
      localStorage.setItem(key, JSON.stringify(payload));
    } catch {
      // Ignore storage quota/private mode errors.
    }
  }

  private read<T>(key: string): Snapshot<T> | null {
    if (typeof localStorage === 'undefined') return null;
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as Snapshot<T>;
      return parsed?.data != null ? parsed : null;
    } catch {
      return null;
    }
  }
}
