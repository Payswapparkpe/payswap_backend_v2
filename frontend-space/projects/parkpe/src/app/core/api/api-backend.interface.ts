import { Observable } from 'rxjs';
import {
  User,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
} from '../models/auth.model';
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
  BBPSCategory,
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
 * API Backend Interface
 * Defines the contract for all API operations
 * Can be implemented by MockApiService or RealApiService
 */
export interface OtpRequestResponse {
  message: string;
  expires_in: number;
}

export interface ApiBackend {
  // Auth API
  login(credentials: LoginRequest): Observable<LoginResponse>;
  requestLoginOtp(phone: string): Observable<OtpRequestResponse>;
  verifyLoginOtp(phone: string, otp: string): Observable<LoginResponse>;
  register(payload: RegisterRequest): Observable<RegisterResponse>;
  logout(): Observable<{ success: boolean }>;
  forgotPassword(payload: ForgotPasswordRequest): Observable<ForgotPasswordResponse>;
  getProfile(): Observable<User>;
  updateProfile(payload: Partial<User>): Observable<User>;

  // Payment API
  getGateways(): Observable<GatewayConfig[]>;
  createOrder(
    gateway: PaymentGateway,
    request: PaymentRequest
  ): Observable<any>; // Gateway-specific order response
  verifyPayment(
    gateway: PaymentGateway,
    response: any
  ): Observable<PaymentResponse>;
  getTransaction(id: string): Observable<Transaction>;
  getTransactionHistory(params?: {
    page?: number;
    limit?: number;
    type?: string;
    status?: string;
    gateway?: PaymentGateway;
  }): Observable<{ transactions: Transaction[]; total: number }>;
  requestRefund(
    transactionId: string,
    amount: number,
    reason: string
  ): Observable<RefundDetails>;
  downloadReceipt(transactionId: string): Observable<Blob | string>;
  getVoucherBalance(): Observable<{ balance: number; currency: string }>;
  getVouchers(params?: { page?: number; limit?: number }): Observable<import('../models/voucher.model').VoucherListResponse>;
  getVoucherDetail(id: number): Observable<import('../models/voucher.model').VoucherDetail>;
  revealVoucherPin(id: number): Observable<import('../models/voucher.model').VoucherRevealPinResponse>;
  getPaymentOrders(params?: { page?: number; limit?: number; status?: string }): Observable<{ orders: PaymentOrder[]; total: number }>;
  getVoucherStatement(params?: { page?: number; limit?: number }): Observable<{ entries: VoucherStatementEntry[]; total: number; balance: number }>;

  // Parking API
  getLocations(): Observable<ParkingLocation[]>;
  getSlots(locationId: string): Observable<ParkingSlot[]>;
  createBooking(payload: BookingRequest): Observable<Booking>;
  getBooking(id: string): Observable<Booking>;

  // BBPS API
  getCategories(): Observable<string[]>;
  getOperators(category: string): Observable<BBPSOperator[]>;
  fetchBill(request: BillFetchRequest): Observable<BillFetchResponse>;
  payBill(payload: BBPSPaymentRequest): Observable<BBPSPaymentResponse>;

  // FASTag API
  createRechargeOrder(
    payload: FastagRechargeRequest
  ): Observable<FastagRechargeResponse>;

  // Challan API
  searchChallans(request: ChallanSearchRequest): Observable<Challan[]>;
  getChallan(id: string): Observable<Challan>;
  payChallan(
    id: string,
    payload: ChallanPaymentRequest
  ): Observable<ChallanPaymentResponse>;

  // Dashboard API (optional)
  getDashboardSummary(): Observable<{
    totalSpendMonth: number;
    pendingChallans: number;
    fastagBalance: number;
    activeBookings: number;
  }>;
}
