import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { ApiBackend } from './api-backend.interface';
import {
  User,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
} from '../models/auth.model';
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
} from '../models/payment.model';
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

  createOrder(gateway: PaymentGateway, request: PaymentRequest): Observable<any> {
    const body: Record<string, unknown> = { amount: request.amount, currency: request.currency || 'INR' };
    const returnUrl = (request as any).returnUrl ?? (typeof window !== 'undefined' ? `${window.location.origin}/payment/callback/cashfree` : undefined);
    if (returnUrl) body['return_url'] = returnUrl;
    return this.http.post<any>(
      `${this.apiUrl}/payment/create-order/${gateway}`,
      body
    );
  }

  verifyPayment(gateway: PaymentGateway, response: any): Observable<PaymentResponse> {
    const body: Record<string, string> = {};
    if (response?.['orderId']) body['orderId'] = response['orderId'];
    if (response?.['order_id']) body['order_id'] = response['order_id'];
    if (response?.['paymentId']) body['paymentId'] = response['paymentId'];
    if (response?.['payment_id']) body['payment_id'] = response['payment_id'];
    if (response?.['razorpay_order_id']) body['orderId'] = response['razorpay_order_id'];
    if (response?.['razorpay_payment_id']) body['paymentId'] = response['razorpay_payment_id'];
    return this.http.post<PaymentResponse>(
      `${this.apiUrl}/payment/verify/${gateway}`,
      Object.keys(body).length ? body : response
    );
  }

  getVoucherBalance(): Observable<{ balance: number; currency: string }> {
    return this.http.get<{ balance: number; currency: string }>(
      `${this.apiUrl}/voucher/balance`
    );
  }

  getVouchers(params?: { page?: number; limit?: number }): Observable<{ vouchers: import('../models/voucher.model').VoucherListItem[]; total: number }> {
    let httpParams = new HttpParams();
    if (params?.page) httpParams = httpParams.set('page', params.page.toString());
    if (params?.limit) httpParams = httpParams.set('limit', params.limit.toString());
    return this.http.get<{ vouchers: import('../models/voucher.model').VoucherListItem[]; total: number }>(
      `${this.apiUrl}/voucher/vouchers`,
      { params: httpParams }
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
    return this.http.get<{ orders: PaymentOrder[]; total: number }>(
      `${this.apiUrl}/payment/orders`,
      { params: httpParams }
    );
  }

  getVoucherStatement(params?: {
    page?: number;
    limit?: number;
  }): Observable<{ entries: VoucherStatementEntry[]; total: number; balance: number }> {
    let httpParams = new HttpParams();
    if (params) {
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.limit) httpParams = httpParams.set('limit', params.limit.toString());
    }
    return this.http.get<{ entries: VoucherStatementEntry[]; total: number; balance: number }>(
      `${this.apiUrl}/payment/voucher-statement`,
      { params: httpParams }
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
  }): Observable<{ transactions: Transaction[]; total: number }> {
    let httpParams = new HttpParams();
    if (params) {
      if (params.page) httpParams = httpParams.set('page', params.page.toString());
      if (params.limit) httpParams = httpParams.set('limit', params.limit.toString());
      if (params.type) httpParams = httpParams.set('type', params.type);
      if (params.status) httpParams = httpParams.set('status', params.status);
      if (params.gateway) httpParams = httpParams.set('gateway', params.gateway);
    }
    return this.http.get<{ transactions: Transaction[]; total: number }>(
      `${this.apiUrl}/payment/transactions`,
      { params: httpParams }
    );
  }

  requestRefund(
    transactionId: string,
    amount: number,
    reason: string
  ): Observable<RefundDetails> {
    return this.http.post<RefundDetails>(
      `${this.apiUrl}/payment/refund/${transactionId}`,
      { amount, reason }
    );
  }

  downloadReceipt(transactionId: string): Observable<Blob | string> {
    return this.http.get(`${this.apiUrl}/payment/receipt/${transactionId}`, {
      responseType: 'blob',
    }) as Observable<Blob>;
  }

  // Parking API
  getLocations(): Observable<ParkingLocation[]> {
    return this.http.get<ParkingLocation[]>(`${this.apiUrl}/parking/locations`);
  }

  getSlots(locationId: string): Observable<ParkingSlot[]> {
    return this.http.get<ParkingSlot[]>(
      `${this.apiUrl}/parking/locations/${locationId}/slots`
    );
  }

  createBooking(payload: BookingRequest): Observable<Booking> {
    return this.http.post<Booking>(`${this.apiUrl}/parking/bookings`, payload);
  }

  getBooking(id: string): Observable<Booking> {
    return this.http.get<Booking>(`${this.apiUrl}/parking/bookings/${id}`);
  }

  // BBPS API (Mobikwik backend – backend uses X-App: parkpe for product toggle)
  private bbpsHeaders = { 'X-App': 'parkpe', 'Content-Type': 'application/json' };

  getCategories(): Observable<string[]> {
    return this.http.get<string[]>(`${this.apiUrl}/bbps/categories`, {
      headers: this.bbpsHeaders,
    });
  }

  getOperators(category: string): Observable<BBPSOperator[]> {
    return this.http.get<BBPSOperator[]>(
      `${this.apiUrl}/bbps/operators?category=${encodeURIComponent(category)}`,
      { headers: this.bbpsHeaders }
    );
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

  // FASTag API
  createRechargeOrder(
    payload: FastagRechargeRequest
  ): Observable<FastagRechargeResponse> {
    return this.http.post<FastagRechargeResponse>(
      `${this.apiUrl}/fastag/recharge`,
      payload
    );
  }

  // Challan API
  searchChallans(request: ChallanSearchRequest): Observable<Challan[]> {
    let httpParams = new HttpParams().set('vehicleNumber', request.vehicleNumber);
    if (request.state) httpParams = httpParams.set('state', request.state);
    if (request.chassisNumber)
      httpParams = httpParams.set('chassisNumber', request.chassisNumber);
    if (request.engineNumber)
      httpParams = httpParams.set('engineNumber', request.engineNumber);

    return this.http.get<Challan[]>(`${this.apiUrl}/challan/search`, {
      params: httpParams,
    });
  }

  getChallan(id: string): Observable<Challan> {
    return this.http.get<Challan>(`${this.apiUrl}/challan/${id}`);
  }

  payChallan(
    id: string,
    payload: ChallanPaymentRequest
  ): Observable<ChallanPaymentResponse> {
    return this.http.post<ChallanPaymentResponse>(
      `${this.apiUrl}/challan/${id}/pay`,
      payload
    );
  }

  // Dashboard API
  getDashboardSummary(): Observable<{
    totalSpendMonth: number;
    pendingChallans: number;
    fastagBalance: number;
    activeBookings: number;
  }> {
    return this.http.get<{
      totalSpendMonth: number;
      pendingChallans: number;
      fastagBalance: number;
      activeBookings: number;
    }>(`${this.apiUrl}/dashboard/summary`);
  }
}
