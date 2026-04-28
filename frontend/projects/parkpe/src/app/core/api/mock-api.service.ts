import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, delay, of, map } from 'rxjs';
import type {
  ApiBackend,
  BbpsSavedBillApi,
  BbpsSavedBillAdd,
  NotificationBannerItem,
  InboxNotificationItem,
  FleetControlCenterResponse,
  FleetListResponse,
  FleetVehicleItem,
  FleetVehicleCreatePayload,
  FleetVehiclesListResponse,
  FleetRosterDriverItem,
  FleetDriverItem,
  FleetTripItem,
  FleetTripManualCreatePayload,
  FleetComplianceResponse,
  FleetTrendsResponse,
  FleetInterestStatus,
} from './api-backend.interface';
import {
  User,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  RegisterVerifyRequest,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
} from 'shared';
import {
  PaymentGateway,
  GatewayConfig,
  PaymentRequest,
  PaymentResponse,
  Transaction,
  RefundDetails,
  PaymentOrder,
  VoucherStatementEntry,
} from 'shared';
import {
  ParkingLocation,
  ParkingSlot,
  BookingRequest,
  Booking,
} from '../models/parking.model';
import {
  BBPSOperator,
  BillFetchRequest,
  BillFetchResponse,
  BBPSPaymentRequest,
  BBPSPaymentResponse,
} from '../models/bbps.model';
import {
  FastagRechargeRequest,
  FastagRechargeResponse,
} from '../models/fastag.model';
import {
  ChallanSearchRequest,
  Challan,
  ChallanPaymentRequest,
  ChallanPaymentResponse,
} from '../models/challan.model';
import { generateTransactionId } from '../utils/transaction-id';

/**
 * Mock API Service
 * Loads data from local JSON files to simulate API responses
 * Used when environment.useMockApi = true
 */
@Injectable({
  providedIn: 'root',
})
export class MockApiService implements ApiBackend {
  private http = inject(HttpClient);
  private mockDelay = 500; // Simulate network delay
  private fleetInterestState: FleetInterestStatus = { status: 'none' };
  /** Manual trips added in mock mode (prepended to list). */
  private mockFleetManualTrips: FleetTripItem[] = [];

  private mockFleetRosterDrivers: FleetRosterDriverItem[] = [
    { userId: 501, username: 'D01MOCK01', name: 'Roster Driver One', phone: '9811111111' },
  ];

  // Auth API
  login(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http
      .get<LoginResponse>('assets/mock/auth/login.json')
      .pipe(delay(this.mockDelay));
  }

  fleetLogin(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http
      .get<LoginResponse>('assets/mock/auth/login.json')
      .pipe(
        map((res) => {
          const fleetUser: User = {
            ...res.user,
            role: 'admin',
          };
          (fleetUser as unknown as Record<string, unknown>)['roleCode'] = 'fleet_admin';
          return { ...res, user: fleetUser };
        }),
        delay(this.mockDelay)
      );
  }

  parkingLogin(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http
      .get<LoginResponse>('assets/mock/auth/login.json')
      .pipe(
        map((res) => {
          const parkingUser: User = {
            ...res.user,
            role: 'parking',
          };
          (parkingUser as unknown as Record<string, unknown>)['roleCode'] = 'parking_owner';
          return { ...res, user: parkingUser };
        }),
        delay(this.mockDelay)
      );
  }

  requestLoginOtp(phone: string): Observable<{ message: string; expires_in: number }> {
    return of({ message: 'OTP sent to your mobile number.', expires_in: 300 }).pipe(delay(this.mockDelay));
  }

  verifyLoginOtp(phone: string, otp: string): Observable<LoginResponse> {
    return this.http
      .get<LoginResponse>('assets/mock/auth/login.json')
      .pipe(delay(this.mockDelay));
  }

  register(payload: RegisterRequest): Observable<RegisterResponse> {
    return this.http
      .get<RegisterResponse>('assets/mock/auth/register.json')
      .pipe(delay(this.mockDelay));
  }

  registerSendOtp(_payload: RegisterRequest): Observable<{ message: string; expires_in: number }> {
    return of({ message: 'OTP sent to your mobile number.', expires_in: 300 }).pipe(delay(this.mockDelay));
  }

  registerVerify(_payload: RegisterVerifyRequest): Observable<LoginResponse> {
    return this.http
      .get<LoginResponse>('assets/mock/auth/login.json')
      .pipe(delay(this.mockDelay));
  }

  lookupPincode(pincode: string): Observable<import('../models/auth.model').PincodeLookupResponse> {
    return of({
      pincode: pincode,
      addresses: [{ state: 'Delhi', district: 'Central', city: 'Central', taluk: '', officename: 'GPO', area: 'GPO', pincode }],
    }).pipe(delay(this.mockDelay));
  }

  logout(): Observable<{ success: boolean }> {
    return of({ success: true }).pipe(delay(300));
  }

  forgotPassword(
    payload: ForgotPasswordRequest
  ): Observable<ForgotPasswordResponse> {
    return this.http
      .get<ForgotPasswordResponse>('assets/mock/auth/forgot-password.json')
      .pipe(delay(this.mockDelay));
  }

  getProfile(): Observable<User> {
    return this.http
      .get<User>('assets/mock/auth/profile.json')
      .pipe(delay(this.mockDelay));
  }

  updateProfile(payload: Partial<User>): Observable<User> {
    // Mock: return updated profile
    return this.http
      .get<User>('assets/mock/auth/profile.json')
      .pipe(delay(this.mockDelay));
  }

  getPinStatus(): Observable<{ hasPin: boolean; pinSetAt?: string | null; pinLockedUntil?: string | null; isLocked: boolean; fullAuthFresh: boolean }> {
    return of({
      hasPin: true,
      pinSetAt: new Date().toISOString(),
      pinLockedUntil: null,
      isLocked: false,
      fullAuthFresh: true,
    }).pipe(delay(this.mockDelay));
  }

  setSessionPin(_payload: { pin: string; currentPin?: string; forceReset?: boolean }): Observable<{ success: boolean; hasPin: boolean }> {
    return of({ success: true, hasPin: true }).pipe(delay(this.mockDelay));
  }

  verifySessionPin(_pin: string): Observable<{ success: boolean; verified: boolean; remainingAttempts?: number }> {
    return of({ success: true, verified: true, remainingAttempts: 4 }).pipe(delay(this.mockDelay));
  }

  getPasskeyStatus(): Observable<{ supported: boolean; enabled: boolean }> {
    return of({ supported: true, enabled: false }).pipe(delay(this.mockDelay));
  }

  getPasskeyRegisterOptions(): Observable<{ publicKey: Record<string, unknown> }> {
    return of({
      publicKey: {
        challenge: 'mock-challenge',
        rp: { name: 'ParkPe', id: 'localhost' },
        user: { id: 'mock-user', name: 'mock-user', displayName: 'Mock User' },
        pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
      },
    }).pipe(delay(this.mockDelay));
  }

  verifyPasskeyRegistration(_credential: Record<string, unknown>): Observable<{ success: boolean; enabled: boolean }> {
    return of({ success: true, enabled: true }).pipe(delay(this.mockDelay));
  }

  getPasskeyAuthOptions(): Observable<{ publicKey: Record<string, unknown> }> {
    return of({
      publicKey: {
        challenge: 'mock-auth-challenge',
        rpId: 'localhost',
        allowCredentials: [],
      },
    }).pipe(delay(this.mockDelay));
  }

  verifyPasskeyAuth(_credential: Record<string, unknown>): Observable<{ success: boolean; verified: boolean }> {
    return of({ success: true, verified: true }).pipe(delay(this.mockDelay));
  }

  disablePasskey(): Observable<{ success: boolean; enabled: boolean }> {
    return of({ success: true, enabled: false }).pipe(delay(this.mockDelay));
  }

  getPasskeyCredentials(): Observable<{ items: import('./api-backend.interface').PasskeyCredentialItem[] }> {
    return of({
      items: [
        {
          id: 1,
          label: 'Primary Device',
          transports: ['internal'],
          createdAt: new Date().toISOString(),
          lastUsedAt: new Date().toISOString(),
        },
      ],
    }).pipe(delay(this.mockDelay));
  }

  updatePasskeyCredential(credentialId: number, label: string): Observable<{ success: boolean; id: number; label: string }> {
    return of({ success: true, id: credentialId, label }).pipe(delay(this.mockDelay));
  }

  deletePasskeyCredential(_credentialId: number): Observable<{ success: boolean; enabled: boolean }> {
    return of({ success: true, enabled: false }).pipe(delay(this.mockDelay));
  }

  requestPasskeyRecoveryOtp(): Observable<{ message: string; expires_in: number }> {
    return of({ message: 'OTP sent to your mobile number.', expires_in: 300 }).pipe(delay(this.mockDelay));
  }

  verifyPasskeyRecoveryOtp(_otp: string): Observable<{ success: boolean; revoked: number; enabled: boolean }> {
    return of({ success: true, revoked: 1, enabled: false }).pipe(delay(this.mockDelay));
  }

  getSecurityOverview(): Observable<import('./api-backend.interface').SecurityOverviewResponse> {
    return of({
      mfa: { enabled: false, configured: false, method: null },
      passkey: { enabled: false },
      pinLock: { pinSet: false, pinSetAt: null, pinLockedUntil: null, fullAuthFresh: true },
      connect: { blockedUntil: null, warningCount: 0 },
      devices: [],
    }).pipe(delay(this.mockDelay));
  }

  revokeSessions(_payload?: { device_id?: number }): Observable<{ success: boolean; revoked: number }> {
    return of({ success: true, revoked: 1 }).pipe(delay(this.mockDelay));
  }

  getSecurityActivity(): Observable<{ items: import('./api-backend.interface').SecurityActivityItem[] }> {
    return of({
      items: [
        {
          id: 1,
          source: 'parkpe',
          action: 'settings_updated',
          change_summary: { language: { from: 'en', to: 'hi' } },
          created_at: new Date().toISOString(),
        },
      ],
    }).pipe(delay(this.mockDelay));
  }

  // Payment API
  getGateways(): Observable<GatewayConfig[]> {
    return this.http
      .get<GatewayConfig[]>('assets/mock/payment/gateways.json')
      .pipe(delay(this.mockDelay));
  }

  createOrder(
    gateway: PaymentGateway,
    request: PaymentRequest
  ): Observable<any> {
    return this.http
      .get<any>('assets/mock/payment/create-order.json')
      .pipe(delay(this.mockDelay));
  }

  verifyPayment(
    gateway: PaymentGateway,
    response: any
  ): Observable<PaymentResponse> {
    return this.http
      .get<PaymentResponse>('assets/mock/payment/verify.json')
      .pipe(delay(this.mockDelay));
  }

  getVouchers(_params?: { page?: number; limit?: number }): Observable<{ vouchers: import('../models/voucher.model').VoucherListItem[]; total: number }> {
    return of({ vouchers: [], total: 0 }).pipe(delay(this.mockDelay));
  }

  getVoucherDetail(_id: number): Observable<import('../models/voucher.model').VoucherDetail> {
    return of({
      id: 0,
      voucherCode: '****-****-****-****',
      referenceNumber: '',
      originalAmount: 0,
      currentBalance: 0,
      currency: 'INR',
      status: 'ACTIVE',
      issuedAt: null,
      parkpeLinked: true,
      linkedUserPhone: '+91 98765 43210',
      transactions: [],
    }).pipe(delay(this.mockDelay));
  }

  revealVoucherPin(_id: number): Observable<{ pin: string }> {
    return of({ pin: '****' }).pipe(delay(this.mockDelay));
  }

  claimVoucher(_body: { voucherCode: string; pin: string }): Observable<import('../models/voucher.model').VoucherClaimResponse> {
    return of({
      success: true,
      message: 'Voucher linked to your account.',
      voucherId: 1,
    }).pipe(delay(this.mockDelay));
  }

  getPaymentOrders(_params?: { page?: number; limit?: number; status?: string }): Observable<{ orders: PaymentOrder[]; total: number }> {
    return of({ orders: [], total: 0 }).pipe(delay(this.mockDelay));
  }

  getVoucherStatement(_params?: { page?: number; limit?: number }): Observable<{ entries: VoucherStatementEntry[]; total: number }> {
    return of({ entries: [], total: 0 }).pipe(delay(this.mockDelay));
  }

  getTransaction(id: string): Observable<Transaction> {
    // Mock: return first transaction from list
    return this.http
      .get<{ transactions: Transaction[] }>(
        'assets/mock/payment/transactions.json'
      )
      .pipe(
        delay(this.mockDelay),
        // @ts-ignore
        (source) => source.pipe((obs) => obs.subscribe({
          next: (data) => of(data.transactions[0])
        }))
      );
  }

  getTransactionHistory(params?: {
    page?: number;
    limit?: number;
    type?: string;
    status?: string;
    gateway?: PaymentGateway;
    dateFrom?: string;
    dateTo?: string;
  }): Observable<{ transactions: Transaction[]; total: number }> {
    return this.http
      .get<{ transactions: Transaction[]; total: number }>(
        'assets/mock/payment/transactions.json'
      )
      .pipe(delay(this.mockDelay));
  }

  requestRefund(
    transactionId: string,
    amount: number,
    reason: string
  ): Observable<RefundDetails> {
    // Mock refund response
    return of({
      refundId: generateTransactionId(),
      amount,
      status: 'processing' as const,
      reason,
      initiatedAt: new Date().toISOString(),
    } as RefundDetails).pipe(delay(this.mockDelay));
  }

  downloadReceipt(
    transactionId: string,
    options?: { attachment?: boolean; format?: 'pdf' }
  ): Observable<Blob | string> {
    if (options?.format === 'pdf') {
      const minimalPdf = '%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF';
      return of(new Blob([minimalPdf], { type: 'application/pdf' })).pipe(delay(this.mockDelay));
    }
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Receipt</title></head><body><h1>Mock receipt</h1><p>${transactionId}</p></body></html>`;
    return of(new Blob([html], { type: 'text/html;charset=utf-8' })).pipe(delay(this.mockDelay));
  }

  // Parking API
  getLocations(): Observable<ParkingLocation[]> {
    return this.http
      .get<ParkingLocation[]>('assets/mock/parking/locations.json')
      .pipe(delay(this.mockDelay));
  }

  getSlots(locationId: string): Observable<ParkingSlot[]> {
    return this.http
      .get<{ locationId: string; slots: ParkingSlot[] }>(
        'assets/mock/parking/slots.json'
      )
      .pipe(
        delay(this.mockDelay),
        // @ts-ignore
        (source) => source.pipe((obs) => obs.subscribe({
          next: (data) => of(data.slots)
        }))
      );
  }

  createBooking(payload: BookingRequest): Observable<Booking> {
    return this.http
      .get<Booking>('assets/mock/parking/booking.json')
      .pipe(delay(this.mockDelay));
  }

  getBooking(id: string): Observable<Booking> {
    return this.http
      .get<Booking>('assets/mock/parking/booking.json')
      .pipe(delay(this.mockDelay));
  }

  // BBPS API – short delay so operator/biller screens open quickly
  private bbpsDelay = 120;

  getCategories(): Observable<string[]> {
    return this.http
      .get<{ categories: string[] }>('assets/mock/bbps/categories.json')
      .pipe(
        delay(this.bbpsDelay),
        map((data) => data.categories ?? [])
      );
  }

  getOperators(category: string): Observable<BBPSOperator[]> {
    return this.http
      .get<Record<string, BBPSOperator[]>>('assets/mock/bbps/operators.json')
      .pipe(
        delay(this.bbpsDelay),
        map((data) => data[category] ?? [])
      );
  }

  fetchBill(request: BillFetchRequest): Observable<BillFetchResponse> {
    return this.http
      .get<BillFetchResponse>('assets/mock/bbps/bill.json')
      .pipe(delay(this.bbpsDelay));
  }

  payBill(payload: BBPSPaymentRequest): Observable<BBPSPaymentResponse> {
    // Mock payment success
    return of({
      success: true,
      transactionId: generateTransactionId(),
      billId: payload.billId,
      receiptNumber: 'RCPT_BBPS_001',
      amount: payload.amount,
      status: 'success',
      timestamp: new Date().toISOString(),
      message: 'Bill paid successfully',
    }).pipe(delay(this.mockDelay));
  }

  payCart(payload: { bills: { billId: string; operatorId: string; consumerId: string; amount: number }[]; voucher_id: number; pin: string }): Observable<import('./api-backend.interface').BbpsPayCartResponse> {
    const total = payload.bills.reduce((s, b) => s + b.amount, 0);
    return of({
      success: true,
      message: 'All bills paid successfully.',
      total,
      results: payload.bills.map((b) => ({
        billId: b.billId,
        operatorId: b.operatorId,
        consumerId: b.consumerId,
        amount: b.amount,
        transactionId: generateTransactionId(),
        status: 'SUBMITTED',
      })),
    }).pipe(delay(this.bbpsDelay));
  }

  getBbpsPayStatus(refId: string): Observable<import('./api-backend.interface').BbpsPayStatusResponse> {
    const res: import('./api-backend.interface').BbpsPayStatusResponse = {
      success: true,
      ref_id: refId,
      vendorStatus: 'SUCCESS',
      phase: 'success',
    };
    return of(res).pipe(delay(this.bbpsDelay));
  }

  getBbpsFavorites(): Observable<{ operatorId: string; operatorName: string; category: string; mobikwikOpId?: string }[]> {
    return of([]).pipe(delay(this.bbpsDelay));
  }

  addBbpsFavorite(body: { operatorId: string; operatorName?: string; category?: string; mobikwikOpId?: string }): Observable<{ operatorId: string; operatorName: string; category: string; mobikwikOpId?: string }> {
    return of({
      operatorId: body.operatorId,
      operatorName: body.operatorName ?? 'Biller',
      category: body.category ?? '',
      mobikwikOpId: body.mobikwikOpId,
    }).pipe(delay(this.bbpsDelay));
  }

  removeBbpsFavorite(_operatorId: string): Observable<void> {
    return of(undefined).pipe(delay(this.bbpsDelay));
  }

  getBbpsSavedBills(): Observable<BbpsSavedBillApi[]> {
    return of([]).pipe(delay(this.bbpsDelay));
  }

  addBbpsSavedBill(bill: BbpsSavedBillAdd): Observable<BbpsSavedBillApi> {
    return of({
      id: `saved_${Date.now()}`,
      nickname: bill.nickname ?? '',
      operatorId: bill.operatorId,
      operatorName: bill.operatorName,
      category: bill.category,
      mobikwikOpId: bill.mobikwikOpId,
      consumerId: bill.consumerId,
      lastAmount: bill.lastAmount,
      billId: bill.billId,
      createdAt: new Date().toISOString(),
    }).pipe(delay(this.bbpsDelay));
  }

  updateBbpsSavedBill(id: string, body: { nickname?: string }): Observable<BbpsSavedBillApi> {
    return of({
      id,
      nickname: body.nickname ?? '',
      operatorId: '',
      operatorName: '',
      category: '',
      mobikwikOpId: '',
      consumerId: '',
      createdAt: new Date().toISOString(),
    }).pipe(delay(this.bbpsDelay));
  }

  removeBbpsSavedBill(_id: string): Observable<void> {
    return of(undefined).pipe(delay(this.bbpsDelay));
  }

  // FASTag API
  createRechargeOrder(
    payload: FastagRechargeRequest
  ): Observable<FastagRechargeResponse> {
    return this.http
      .get<FastagRechargeResponse>('assets/mock/fastag/recharge.json')
      .pipe(delay(this.mockDelay));
  }

  // Challan API
  searchChallans(request: ChallanSearchRequest): Observable<Challan[]> {
    return this.http
      .get<{ challans: Challan[] }>('assets/mock/challan/search.json')
      .pipe(
        delay(this.mockDelay),
        // @ts-ignore
        (source) => source.pipe((obs) => obs.subscribe({
          next: (data) => of(data.challans)
        }))
      );
  }

  getChallan(id: string): Observable<Challan> {
    return this.http
      .get<Challan>('assets/mock/challan/detail.json')
      .pipe(delay(this.mockDelay));
  }

  payChallan(
    id: string,
    payload: ChallanPaymentRequest
  ): Observable<ChallanPaymentResponse> {
    return of({
      success: true,
      transactionId: generateTransactionId(),
      challanId: id,
      receiptNumber: 'RCPT_CHALLAN_001',
      amount: payload.amount,
      status: 'success',
      paidAt: new Date().toISOString(),
      message: 'Challan paid successfully',
    }).pipe(delay(this.mockDelay));
  }

  // Dashboard API
  getDashboardSummary(): Observable<{
    totalSpendMonth: number;
    pendingChallans: number;
    fastagBalance: number;
    activeBookings: number;
  }> {
    return this.http
      .get<{
        totalSpendMonth: number;
        pendingChallans: number;
        fastagBalance: number;
        activeBookings: number;
      }>('assets/mock/profile/dashboard-summary.json')
      .pipe(delay(this.mockDelay));
  }

  getNotificationBanners(_params?: { slot?: string; screen?: string; service?: string }): Observable<{ banners: NotificationBannerItem[] }> {
    return of({
      banners: [
        {
          id: 1,
          name: 'mock-bbps-offer',
          title: 'Smart Pay Offer',
          message: 'Pay BBPS bills using voucher and unlock extra cashback rewards.',
          ctaText: 'View offers',
          ctaUrl: '/vouchers',
          bgColor: '#1f4f94',
          textColor: '#ffffff',
        },
      ],
    }).pipe(delay(this.bbpsDelay));
  }

  getNotificationFeed(_params?: { limit?: number; offset?: number }): Observable<{ items: InboxNotificationItem[]; total: number }> {
    return of({
      items: [
        {
          id: 101,
          title: 'Welcome to Notification Center',
          message: 'Your in-app inbox is now active for campaign alerts.',
          channel: 'in_app',
          isRead: false,
          createdAt: new Date().toISOString(),
        },
      ],
      total: 1,
    }).pipe(delay(this.mockDelay));
  }

  getNotificationUnreadCount(): Observable<{ unread: number }> {
    return of({ unread: 1 }).pipe(delay(this.bbpsDelay));
  }

  markNotificationRead(_notificationId: number): Observable<{ success: boolean }> {
    return of({ success: true }).pipe(delay(this.bbpsDelay));
  }

  registerPushToken(_payload: { token: string; devicePlatform?: string; appPlatform?: string }): Observable<{ success: boolean; id: number }> {
    return of({ success: true, id: 1 }).pipe(delay(this.bbpsDelay));
  }

  getFleetControlCenter(): Observable<FleetControlCenterResponse> {
    return of({
      kpis: [
        { label: 'Active Vehicles', value: 1284, trend: 'live' },
        { label: 'Trips Today', value: 426, trend: 'today' },
        { label: 'On-time Rate', value: '96.4%', trend: '24h' },
        { label: 'Open Alerts', value: 37, trend: 'live' },
      ],
      priorityAlerts: [
        '12 vehicles nearing insurance expiry in next 15 days.',
        '7 route deviation events flagged in North zone in last 2 hours.',
        '3 driver documents pending compliance verification.',
      ],
      modules: [
        {
          title: 'Fleet Ops',
          description: 'Dispatch board, trip monitoring, and route adherence.',
          route: '/fleet/trips',
          cta: 'Open Fleet Ops',
        },
        {
          title: 'Vehicles',
          description: 'Vehicle master, RC health, and uptime readiness.',
          route: '/fleet/vehicles',
          cta: 'Manage Vehicles',
        },
        {
          title: 'Drivers',
          description: 'Driver roster, risk behavior, and performance snapshot.',
          route: '/fleet/drivers',
          cta: 'Open Driver Hub',
        },
        {
          title: 'Notification Center',
          description: 'Broadcast updates, route alerts, and escalations to fleet users.',
          route: '/notifications',
          cta: 'Open Notifications',
        },
        {
          title: 'Payments & Settlement',
          description: 'Voucher and payment workflows for fleet operations.',
          route: '/payment/history',
          cta: 'Open Payments',
        },
        {
          title: 'Compliance & Governance',
          description: 'Policies, approvals, and operational audit controls.',
          route: '/fleet/compliance',
          cta: 'Open Settings',
        },
      ],
    }).pipe(delay(this.mockDelay));
  }

  getFleetVehicles(params?: { page?: number; limit?: number; search?: string; vehicleType?: string }): Observable<FleetVehiclesListResponse> {
    const page = params?.page ?? 1;
    const limit = params?.limit ?? 10;
    const items: FleetVehicleItem[] = Array.from({ length: limit }).map((_, idx) => ({
      id: idx + 1 + (page - 1) * limit,
      ownerUserId: idx % 4 === 1 ? 501 : 1,
      registrationNumber: `DL01AB${(1000 + idx).toString()}`,
      vehicleType: idx % 3 === 0 ? 'commercial' : 'four_wheeler',
      brand: idx % 2 === 0 ? 'Tata' : 'Mahindra',
      model: idx % 2 === 0 ? 'Ace' : 'Bolero',
      year: 2019 + (idx % 5),
      isPrimary: idx % 4 === 0,
      ownerName: idx % 4 === 1 ? 'Roster Driver One' : `Driver ${idx + 1}`,
      ownerPhone: `98${(10000000 + idx).toString().slice(0, 8)}`,
      scans24h: 5 + idx,
      calls24h: 2 + (idx % 3),
      complianceState: idx % 5 === 0 ? 'expiring' : 'compliant',
      insuranceUpto: '2026-09-30',
      pucUpto: '2026-05-30',
      createdAt: new Date().toISOString(),
    }));
    return of({
      items,
      total: 120,
      page,
      limit,
      canDelegateToDrivers: true,
      rosterDrivers: [...this.mockFleetRosterDrivers],
    }).pipe(delay(this.mockDelay));
  }

  createFleetVehicle(payload: FleetVehicleCreatePayload): Observable<FleetVehicleItem> {
    const roster = payload.ownerUserId
      ? this.mockFleetRosterDrivers.find((d) => d.userId === payload.ownerUserId)
      : null;
    const item: FleetVehicleItem = {
      id: Math.floor(Math.random() * 1_000_000) + 10_000,
      ownerUserId: payload.ownerUserId ?? 1,
      registrationNumber: payload.registrationNumber.trim().toUpperCase(),
      vehicleType: payload.vehicleType,
      brand: payload.brand,
      model: payload.model,
      year: payload.year ?? null,
      isPrimary: false,
      ownerName: roster?.name ?? 'Mock Fleet Owner',
      ownerPhone: roster?.phone ?? '9800000000',
      scans24h: 0,
      calls24h: 0,
      complianceState: 'missing_rc',
      insuranceUpto: null,
      pucUpto: null,
      createdAt: new Date().toISOString(),
    };
    return of(item).pipe(delay(this.mockDelay));
  }

  getFleetRoster(): Observable<{ canDelegateToDrivers: boolean; rosterDrivers: FleetRosterDriverItem[] }> {
    return of({
      canDelegateToDrivers: true,
      rosterDrivers: [...this.mockFleetRosterDrivers],
    }).pipe(delay(this.mockDelay));
  }

  linkFleetRosterDriver(payload: { driverUserId?: number; username?: string; phone?: string }): Observable<FleetRosterDriverItem> {
    const n = this.mockFleetRosterDrivers.length;
    const row: FleetRosterDriverItem = {
      userId: payload.driverUserId ?? 9000 + n,
      username: payload.username?.trim() || `DMOCK${n}`,
      name: `Linked driver ${n + 1}`,
      phone: payload.phone?.trim() || '9898989898',
    };
    this.mockFleetRosterDrivers = [...this.mockFleetRosterDrivers, row];
    return of(row).pipe(delay(this.mockDelay));
  }

  unlinkFleetRosterDriver(driverUserId: number): Observable<void> {
    this.mockFleetRosterDrivers = this.mockFleetRosterDrivers.filter((d) => d.userId !== driverUserId);
    return of(undefined).pipe(delay(this.mockDelay));
  }

  getFleetDrivers(params?: { page?: number; limit?: number; search?: string }): Observable<FleetListResponse<FleetDriverItem>> {
    const page = params?.page ?? 1;
    const limit = params?.limit ?? 10;
    const items: FleetDriverItem[] = Array.from({ length: limit }).map((_, idx) => ({
      id: idx + 1 + (page - 1) * limit,
      name: `Fleet Driver ${idx + 1}`,
      phone: `99${(10000000 + idx).toString().slice(0, 8)}`,
      email: `fleet.driver${idx + 1}@parkpe.test`,
      city: idx % 2 === 0 ? 'Delhi' : 'Gurgaon',
      vehiclesCount: 1 + (idx % 3),
      scans24h: 3 + idx,
      reportsAgainst24h: idx % 2,
      warningCount: idx % 3,
      blockedUntil: idx % 10 === 0 ? new Date(Date.now() + 3600_000).toISOString() : null,
    }));
    return of({ items, total: 84, page, limit }).pipe(delay(this.mockDelay));
  }

  getFleetTrips(params?: { page?: number; limit?: number; dateFrom?: string; dateTo?: string }): Observable<FleetListResponse<FleetTripItem>> {
    const page = params?.page ?? 1;
    const limit = params?.limit ?? 10;
    const baseTotal = 345;
    const manual = [...this.mockFleetManualTrips];
    const total = manual.length + baseTotal;
    const start = (page - 1) * limit;
    const items: FleetTripItem[] = [];
    for (let i = start; i < start + limit && i < total; i++) {
      if (i < manual.length) {
        items.push(manual[i]);
      } else {
        const j = i - manual.length;
        items.push({
          id: j + 1,
          qrCode: `QR-MOCK-${j + 1}`,
          vehicleId: j + 10,
          registrationNumber: `HR26CD${(2000 + j).toString()}`,
          vehicleType: j % 2 === 0 ? 'commercial' : 'four_wheeler',
          scannedBy: `Ops User ${j + 1}`,
          scannerPhone: `97${(10000000 + j).toString().slice(0, 8)}`,
          ipAddress: '127.0.0.1',
          createdAt: new Date(Date.now() - j * 600000).toISOString(),
          entrySource: 'connect',
        });
      }
    }
    return of({ items, total, page, limit }).pipe(delay(this.mockDelay));
  }

  createFleetTripManual(payload: FleetTripManualCreatePayload): Observable<FleetTripItem> {
    const item: FleetTripItem = {
      id: Math.floor(Date.now() / 1000) + Math.floor(Math.random() * 1000),
      qrCode: `manual:${payload.vehicleId}`,
      vehicleId: payload.vehicleId,
      registrationNumber: `MOCK-${payload.vehicleId}`,
      vehicleType: 'four_wheeler',
      scannedBy: 'You (mock)',
      scannerPhone: '0000000000',
      ipAddress: '127.0.0.1',
      createdAt: new Date().toISOString(),
      entrySource: 'manual',
    };
    this.mockFleetManualTrips = [item, ...this.mockFleetManualTrips];
    return of(item).pipe(delay(this.mockDelay));
  }

  getFleetCompliance(params?: { page?: number; limit?: number; status?: string }): Observable<FleetComplianceResponse> {
    const page = params?.page ?? 1;
    const limit = params?.limit ?? 10;
    const states = ['compliant', 'expiring', 'expired', 'missing_rc'];
    const items = Array.from({ length: limit }).map((_, idx) => {
      const state = states[idx % states.length];
      return {
        vehicleId: idx + 100,
        registrationNumber: `UP32EF${(3000 + idx).toString()}`,
        ownerName: `Owner ${idx + 1}`,
        ownerPhone: `96${(10000000 + idx).toString().slice(0, 8)}`,
        insuranceUpto: state === 'expired' ? '2025-01-01' : '2026-12-31',
        pucUpto: state === 'expiring' ? '2026-05-01' : '2026-11-20',
        complianceState: state,
      };
    }).filter((row) => !params?.status || row.complianceState === params.status);
    return of({
      items,
      total: 98,
      page,
      limit,
      summary: { compliant: 52, expiring: 18, expired: 14, missing_rc: 14 },
    }).pipe(delay(this.mockDelay));
  }

  getFleetTrends(params?: { days?: number }): Observable<FleetTrendsResponse> {
    const days = params?.days ?? 7;
    const series = Array.from({ length: days }).map((_, idx) => ({
      date: new Date(Date.now() - (days - idx - 1) * 86400000).toISOString().slice(0, 10),
      label: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][idx % 7],
      scans: 100 + idx * 8,
      calls: 80 + idx * 6,
      callSuccessRate: 92 + (idx % 4),
      reports: 4 + (idx % 3),
    }));
    return of({ series, days }).pipe(delay(this.mockDelay));
  }

  getFleetInterestStatus(): Observable<FleetInterestStatus> {
    return of({ ...this.fleetInterestState }).pipe(delay(this.mockDelay));
  }

  submitFleetInterest(payload: { companyName?: string; message?: string }): Observable<{
    success: boolean;
    status: string;
    submittedAt?: string;
    message?: string;
  }> {
    const submittedAt = new Date().toISOString();
    this.fleetInterestState = {
      status: 'pending',
      submittedAt,
      companyName: payload.companyName,
      message: payload.message,
    };
    return of({ success: true, status: 'pending', submittedAt }).pipe(delay(this.mockDelay));
  }
}
