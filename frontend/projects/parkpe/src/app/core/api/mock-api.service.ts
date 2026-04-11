import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, delay, of, map } from 'rxjs';
import type { ApiBackend, BbpsSavedBillApi, BbpsSavedBillAdd } from './api-backend.interface';
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

  // Auth API
  login(credentials: LoginRequest): Observable<LoginResponse> {
    return this.http
      .get<LoginResponse>('assets/mock/auth/login.json')
      .pipe(delay(this.mockDelay));
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

  downloadReceipt(transactionId: string): Observable<Blob | string> {
    // Mock: return receipt URL
    return of(`/receipts/${transactionId}.pdf`).pipe(delay(this.mockDelay));
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
}
