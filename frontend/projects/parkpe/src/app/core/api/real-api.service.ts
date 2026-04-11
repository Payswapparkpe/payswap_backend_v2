import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, of, throwError } from 'rxjs';
import { catchError, map, shareReplay, tap } from 'rxjs/operators';

/** Backend does not expose these routes yet (BUG-006); return controlled error instead of 404. */
const UNSUPPORTED = 'Endpoint not available on backend.';
import { environment } from '../../../environments/environment';
import { ApiBackend } from './api-backend.interface';
import {
  User,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  RegisterVerifyRequest,
  PincodeLookupResponse,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
} from 'shared';
import type { OtpRequestResponse } from './api-backend.interface';
import {
  PaymentGateway,
  GatewayConfig,
  PaymentRequest,
  PaymentResponse,
  Transaction,
  RefundDetails,
  PaymentOrder,
  VoucherStatementEntry,
  GatewayOrderResponse,
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
import type { BbpsSavedBillApi, BbpsSavedBillAdd, BbpsPayCartResponse } from './api-backend.interface';

/**
 * Real API Service
 * Makes actual HTTP calls to the backend API
 * Used when environment.useMockApi = false
 */
@Injectable({
  providedIn: 'root',
})
export class RealApiService implements ApiBackend {
  private http = inject(HttpClient);
  private apiUrl = environment.apiUrl;
  private static readonly OPERATORS_CACHE_TTL_MS = 12 * 60 * 60 * 1000;
  private static readonly OPERATORS_CACHE_VERSION = 'v2';
  private static readonly MOBIKWIK_ICON_BASE = environment.mobikwikIconBase;
  private static readonly CACHE_TTL_SHORT_MS = 60 * 1000;
  private static readonly CACHE_TTL_MEDIUM_MS = 5 * 60 * 1000;
  private static readonly CACHE_TTL_LONG_MS = 30 * 60 * 1000;
  private memoryCache = new Map<string, { expiresAt: number; obs$: Observable<unknown> }>();

  private getCached<T>(key: string, ttlMs: number, loader: () => Observable<T>): Observable<T> {
    const now = Date.now();
    const hit = this.memoryCache.get(key);
    if (hit && hit.expiresAt > now) return hit.obs$ as Observable<T>;
    const obs$ = loader().pipe(shareReplay({ bufferSize: 1, refCount: false }));
    this.memoryCache.set(key, { expiresAt: now + ttlMs, obs$ });
    return obs$;
  }

  private invalidateCache(prefix: string): void {
    for (const key of this.memoryCache.keys()) {
      if (key.startsWith(prefix)) this.memoryCache.delete(key);
    }
  }

  // Auth API
  login(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.apiUrl}/auth/login`, credentials);
  }

  requestLoginOtp(phone: string): Observable<OtpRequestResponse> {
    return this.http.post<OtpRequestResponse>(`${this.apiUrl}/auth/otp/request`, { phone });
  }

  verifyLoginOtp(phone: string, otp: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.apiUrl}/auth/otp/verify`, { phone, otp });
  }

  register(payload: RegisterRequest): Observable<RegisterResponse> {
    return this.http.post<RegisterResponse>(`${this.apiUrl}/auth/register`, payload);
  }

  registerSendOtp(payload: RegisterRequest): Observable<{ message: string; expires_in: number }> {
    return this.http.post<{ message: string; expires_in: number }>(
      `${this.apiUrl}/auth/register/send-otp`,
      payload
    );
  }

  registerVerify(payload: RegisterVerifyRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.apiUrl}/auth/register/verify`, payload);
  }

  lookupPincode(pincode: string): Observable<PincodeLookupResponse> {
    const params = new HttpParams().set('pincode', pincode.trim());
    return this.http.get<PincodeLookupResponse>(`${this.apiUrl}/dashboard/pincode`, { params });
  }

  logout(): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(`${this.apiUrl}/auth/logout`, {});
  }

  forgotPassword(payload: ForgotPasswordRequest): Observable<ForgotPasswordResponse> {
    return this.http.post<ForgotPasswordResponse>(
      `${this.apiUrl}/auth/forgot-password`,
      payload
    );
  }

  getProfile(): Observable<User> {
    return this.http.get<User>(`${this.apiUrl}/auth/profile`);
  }

  updateProfile(payload: Partial<User>): Observable<User> {
    return this.http.patch<User>(`${this.apiUrl}/auth/profile`, payload);
  }

  // Payment API (ParkPe: voucher purchase – no wallet)
  getGateways(): Observable<GatewayConfig[]> {
    return this.http
      .get<{ gateways: { id: string; name: string }[] }>(`${this.apiUrl}/payment/gateways`)
      .pipe(
        map((r) =>
          (r.gateways || []).map((g) => ({
            name: g.id as PaymentGateway,
            displayName: g.name,
            logo: '',
            enabled: true,
            supportedMethods: [],
            minAmount: 1,
            maxAmount: 1000000,
          } as GatewayConfig))
        )
      );
  }

  createOrder(gateway: PaymentGateway, request: PaymentRequest): Observable<GatewayOrderResponse> {
    const body: Record<string, unknown> = { amount: request.amount, currency: request.currency || 'INR' };
    // Use window location only in browser environment
    const returnUrl = (request as any).returnUrl ?? (typeof window !== 'undefined' ? `${window.location.origin}/payment/callback/cashfree` : undefined);
    if (returnUrl) body['return_url'] = returnUrl;

    return this.http.post<GatewayOrderResponse>(
      `${this.apiUrl}/payment/create-order/${gateway}`,
      body
    ).pipe(tap(() => this.invalidateCache('payment:')));
  }

  verifyPayment(gateway: PaymentGateway, response: Record<string, any>): Observable<PaymentResponse> {
    const body: Record<string, string> = {};
    // Normalize response keys from different SDKs
    if (response['orderId']) body['orderId'] = response['orderId'];
    if (response['order_id']) body['order_id'] = response['order_id'];
    if (response['paymentId']) body['paymentId'] = response['paymentId'];
    if (response['payment_id']) body['payment_id'] = response['payment_id'];
    if (response['cf_payment_id']) body['cf_payment_id'] = response['cf_payment_id'];
    if (response['razorpay_order_id']) body['orderId'] = response['razorpay_order_id'];
    if (response['razorpay_payment_id']) body['paymentId'] = response['razorpay_payment_id'];
    if (response['razorpay_signature']) body['signature'] = response['razorpay_signature'];

    return this.http.post<PaymentResponse>(
      `${this.apiUrl}/payment/verify/${gateway}`,
      Object.keys(body).length ? body : response
    ).pipe(
      tap(() => {
        this.invalidateCache('payment:');
        this.invalidateCache('vouchers:list:');
      })
    );
  }

  getVouchers(params?: { page?: number; limit?: number }): Observable<{ vouchers: import('../models/voucher.model').VoucherListItem[]; total: number }> {
    let httpParams = new HttpParams();
    if (params?.page) httpParams = httpParams.set('page', params.page.toString());
    if (params?.limit) httpParams = httpParams.set('limit', params.limit.toString());
    const key = `vouchers:list:${params?.page ?? 1}:${params?.limit ?? 50}`;
    return this.getCached(
      key,
      RealApiService.CACHE_TTL_SHORT_MS,
      () =>
        this.http.get<{ vouchers: import('../models/voucher.model').VoucherListItem[]; total: number }>(
          `${this.apiUrl}/voucher/vouchers`,
          { params: httpParams }
        )
    );
  }

  getVoucherDetail(id: number): Observable<import('../models/voucher.model').VoucherDetail> {
    return this.http.get<import('../models/voucher.model').VoucherDetail>(
      `${this.apiUrl}/voucher/vouchers/${id}`
    );
  }

  revealVoucherPin(id: number): Observable<{ pin: string }> {
    return this.http.post<{ pin: string }>(
      `${this.apiUrl}/voucher/vouchers/${id}/reveal-pin`,
      {}
    );
  }

  claimVoucher(body: { voucherCode: string; pin: string }): Observable<import('../models/voucher.model').VoucherClaimResponse> {
    return this.http
      .post<import('../models/voucher.model').VoucherClaimResponse>(
        `${this.apiUrl}/voucher/vouchers/claim`,
        { voucherCode: body.voucherCode, pin: body.pin }
      )
      .pipe(tap(() => this.invalidateCache('vouchers:list:')));
  }

  getPaymentOrders(params?: {
    page?: number;
    limit?: number;
    status?: string;
  }): Observable<{ orders: PaymentOrder[]; total: number }> {
    let httpParams = new HttpParams();
    if (params) {
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.limit) httpParams = httpParams.set('limit', params.limit.toString());
      if (params.status) httpParams = httpParams.set('status', params.status);
    }
    const key = `payment:orders:${params?.page ?? 1}:${params?.limit ?? 50}:${params?.status ?? 'all'}`;
    return this.getCached(
      key,
      RealApiService.CACHE_TTL_SHORT_MS,
      () =>
        this.http.get<{ orders: PaymentOrder[]; total: number }>(
          `${this.apiUrl}/payment/orders`,
          { params: httpParams }
        )
    );
  }

  getVoucherStatement(params?: {
    page?: number;
    limit?: number;
  }): Observable<{ entries: VoucherStatementEntry[]; total: number }> {
    let httpParams = new HttpParams();
    if (params) {
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.limit) httpParams = httpParams.set('limit', params.limit.toString());
    }
    const key = `payment:voucher-statement:${params?.page ?? 1}:${params?.limit ?? 50}`;
    return this.getCached(
      key,
      RealApiService.CACHE_TTL_SHORT_MS,
      () =>
        this.http.get<{ entries: VoucherStatementEntry[]; total: number }>(
          `${this.apiUrl}/payment/voucher-statement`,
          { params: httpParams }
        )
    );
  }

  getTransaction(id: string): Observable<Transaction> {
    return this.http.get<Transaction>(`${this.apiUrl}/payment/transactions/${id}`);
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
    let httpParams = new HttpParams();
    if (params) {
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.limit) httpParams = httpParams.set('limit', params.limit.toString());
      if (params.type) httpParams = httpParams.set('type', params.type);
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.gateway) httpParams = httpParams.set('gateway', params.gateway);
      if (params.dateFrom) httpParams = httpParams.set('date_from', params.dateFrom);
      if (params.dateTo) httpParams = httpParams.set('date_to', params.dateTo);
    }
    return this.http.get<{ transactions: Transaction[]; total: number }>(
      `${this.apiUrl}/payment/transactions`,
      { params: httpParams }
    );
  }

  requestRefund(
    _transactionId: string,
    _amount: number,
    _reason: string
  ): Observable<RefundDetails> {
    return throwError(() => new Error(UNSUPPORTED));
  }

  downloadReceipt(_transactionId: string): Observable<Blob | string> {
    return throwError(() => new Error(UNSUPPORTED));
  }

  // Parking API – backend routes not yet implemented
  getLocations(): Observable<ParkingLocation[]> {
    if (!environment.features?.parking) return throwError(() => new Error(UNSUPPORTED));
    return throwError(() => new Error(UNSUPPORTED));
  }

  getSlots(_locationId: string): Observable<ParkingSlot[]> {
    if (!environment.features?.parking) return throwError(() => new Error(UNSUPPORTED));
    return throwError(() => new Error(UNSUPPORTED));
  }

  createBooking(_payload: BookingRequest): Observable<Booking> {
    if (!environment.features?.parking) return throwError(() => new Error(UNSUPPORTED));
    return throwError(() => new Error(UNSUPPORTED));
  }

  getBooking(_id: string): Observable<Booking> {
    if (!environment.features?.parking) return throwError(() => new Error(UNSUPPORTED));
    return throwError(() => new Error(UNSUPPORTED));
  }

  // BBPS API (Mobikwik backend – backend uses X-App: parkpe for product toggle)
  private bbpsHeaders = { 'X-App': 'parkpe', 'Content-Type': 'application/json' };

  getCategories(): Observable<string[]> {
    return this.getCached(
      'bbps:categories',
      RealApiService.CACHE_TTL_LONG_MS,
      () =>
        this.http.get<string[]>(`${this.apiUrl}/bbps/categories`, {
          headers: this.bbpsHeaders,
        })
    );
  }

  getOperators(category: string): Observable<BBPSOperator[]> {
    const normalizedCategory = (category || '').trim().toLowerCase();
    const cacheKey = this.getOperatorsCacheKey(normalizedCategory);
    const cached = this.readOperatorsCache(cacheKey);
    if (cached) {
      return of(cached);
    }
    return this.http.get<BBPSOperator[]>(
      `${this.apiUrl}/bbps/operators?category=${encodeURIComponent(normalizedCategory)}`,
      { headers: this.bbpsHeaders }
    ).pipe(
      map((ops) => this.normalizeOperatorsIcons(ops)),
      tap((ops) => this.writeOperatorsCache(cacheKey, ops)),
      catchError((err) => {
        const stale = this.readOperatorsCache(cacheKey, true);
        if (stale) return of(stale);
        return throwError(() => err);
      })
    );
  }

  private getOperatorsCacheKey(category: string): string {
    return `parkpe:bbps:operators:${RealApiService.OPERATORS_CACHE_VERSION}:${category || 'all'}`;
  }

  private readOperatorsCache(key: string, allowStale = false): BBPSOperator[] | null {
    if (typeof localStorage === 'undefined') return null;
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as { ts?: number; data?: BBPSOperator[] };
      if (!parsed || !Array.isArray(parsed.data)) return null;
      const ts = Number(parsed.ts || 0);
      if (!allowStale && (!ts || (Date.now() - ts) > RealApiService.OPERATORS_CACHE_TTL_MS)) {
        return null;
      }
      return this.normalizeOperatorsIcons(parsed.data);
    } catch {
      return null;
    }
  }

  private writeOperatorsCache(key: string, data: BBPSOperator[]): void {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(
        key,
        JSON.stringify({
          ts: Date.now(),
          data: this.normalizeOperatorsIcons(data),
        })
      );
    } catch {
      // Ignore storage quota/private mode errors.
    }
  }

  private normalizeOperatorsIcons(ops: BBPSOperator[] | null | undefined): BBPSOperator[] {
    if (!Array.isArray(ops)) return [];
    return ops.map((op) => {
      const mobikwikOpIdRaw = String((op as { mobikwikOpId?: string }).mobikwikOpId ?? '').trim();
      const mobikwikOpId = this.normalizeOpId(mobikwikOpIdRaw);
      const logoRaw = String(op.logo ?? '').trim();
      let logo = logoRaw;

      // Prefer strict Mobikwik op icon whenever op id is available.
      if (mobikwikOpId) {
        logo = `${RealApiService.MOBIKWIK_ICON_BASE}/op${mobikwikOpId}.png`;
      } else {
        const extracted = this.extractOpIdFromLogo(logoRaw);
        if (extracted) {
          logo = `${RealApiService.MOBIKWIK_ICON_BASE}/op${extracted}.png`;
        }
      }

      return {
        ...op,
        mobikwikOpId: mobikwikOpId || (op as { mobikwikOpId?: string }).mobikwikOpId,
        logo,
      };
    });
  }

  private normalizeOpId(raw: string): string {
    if (!raw) return '';
    const value = raw.trim();
    if (/^op\d+$/i.test(value)) return value.replace(/^op/i, '');
    if (/^\d+\.0$/.test(value)) return value.slice(0, -2);
    if (/^\d+$/.test(value)) return value;
    return '';
  }

  private extractOpIdFromLogo(logo: string): string {
    const match = logo.match(/\/operator_icons\/op(\d+)\.png/i);
    return match?.[1] ?? '';
  }

  fetchBill(request: BillFetchRequest): Observable<BillFetchResponse> {
    return this.http.post<BillFetchResponse>(
      `${this.apiUrl}/bbps/fetch-bill`,
      request,
      { headers: this.bbpsHeaders }
    );
  }

  payBill(payload: BBPSPaymentRequest): Observable<BBPSPaymentResponse> {
    return this.http.post<BBPSPaymentResponse>(
      `${this.apiUrl}/bbps/pay`,
      payload,
      { headers: this.bbpsHeaders }
    );
  }

  payCart(payload: { bills: { billId: string; operatorId: string; consumerId: string; amount: number }[]; voucher_id: number; pin: string }): Observable<BbpsPayCartResponse> {
    return this.http.post<BbpsPayCartResponse>(
      `${this.apiUrl}/bbps/pay-cart`,
      payload,
      { headers: this.bbpsHeaders }
    );
  }

  getBbpsFavorites(): Observable<{ operatorId: string; operatorName: string; category: string; mobikwikOpId?: string }[]> {
    return this.getCached(
      'bbps:favorites',
      RealApiService.CACHE_TTL_MEDIUM_MS,
      () =>
        this.http.get<{ operatorId: string; operatorName: string; category: string; mobikwikOpId?: string }[]>(
          `${this.apiUrl}/bbps/favorites`,
          { headers: this.bbpsHeaders }
        )
    );
  }

  addBbpsFavorite(body: { operatorId: string; operatorName?: string; category?: string; mobikwikOpId?: string }): Observable<{ operatorId: string; operatorName: string; category: string; mobikwikOpId?: string }> {
    return this.http.post<{ operatorId: string; operatorName: string; category: string; mobikwikOpId?: string }>(
      `${this.apiUrl}/bbps/favorites`,
      body,
      { headers: this.bbpsHeaders }
    ).pipe(tap(() => this.invalidateCache('bbps:favorites')));
  }

  removeBbpsFavorite(operatorId: string): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/bbps/favorites/${encodeURIComponent(operatorId)}`,
      { headers: this.bbpsHeaders }
    ).pipe(tap(() => this.invalidateCache('bbps:favorites')));
  }

  getBbpsSavedBills(): Observable<BbpsSavedBillApi[]> {
    return this.getCached(
      'bbps:saved-bills',
      RealApiService.CACHE_TTL_MEDIUM_MS,
      () =>
        this.http.get<BbpsSavedBillApi[]>(
          `${this.apiUrl}/bbps/saved-bills`,
          { headers: this.bbpsHeaders }
        )
    );
  }

  addBbpsSavedBill(bill: BbpsSavedBillAdd): Observable<BbpsSavedBillApi> {
    return this.http.post<BbpsSavedBillApi>(
      `${this.apiUrl}/bbps/saved-bills`,
      bill,
      { headers: this.bbpsHeaders }
    ).pipe(tap(() => this.invalidateCache('bbps:saved-bills')));
  }

  updateBbpsSavedBill(id: string, body: { nickname?: string }): Observable<BbpsSavedBillApi> {
    return this.http.patch<BbpsSavedBillApi>(
      `${this.apiUrl}/bbps/saved-bills/${id}`,
      body,
      { headers: this.bbpsHeaders }
    ).pipe(tap(() => this.invalidateCache('bbps:saved-bills')));
  }

  removeBbpsSavedBill(id: string): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/bbps/saved-bills/${id}/delete`,
      { headers: this.bbpsHeaders }
    ).pipe(tap(() => this.invalidateCache('bbps:saved-bills')));
  }

  // FASTag API
  createRechargeOrder(payload: FastagRechargeRequest): Observable<FastagRechargeResponse> {
    return this.http.post<FastagRechargeResponse>(
      `${this.apiUrl}/fastag/recharge`,
      payload
    );
  }

  // Challan API – backend routes not yet implemented
  searchChallans(_request: ChallanSearchRequest): Observable<Challan[]> {
    return throwError(() => new Error(UNSUPPORTED));
  }

  getChallan(_id: string): Observable<Challan> {
    return throwError(() => new Error(UNSUPPORTED));
  }

  payChallan(
    _id: string,
    _payload: ChallanPaymentRequest
  ): Observable<ChallanPaymentResponse> {
    return throwError(() => new Error(UNSUPPORTED));
  }

  // Dashboard API
  getDashboardSummary(): Observable<{
    totalSpendMonth: number;
    pendingChallans: number;
    fastagBalance: number;
    activeBookings: number;
  }> {
    return this.getCached(
      'dashboard:summary',
      RealApiService.CACHE_TTL_SHORT_MS,
      () =>
        this.http.get<{
          totalSpendMonth: number;
          pendingChallans: number;
          fastagBalance: number;
          activeBookings: number;
        }>(`${this.apiUrl}/dashboard/summary`)
    );
  }
}
