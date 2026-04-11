import { Observable } from 'rxjs';
import {
  User,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  RegisterSendOtpResponse,
  RegisterVerifyRequest,
  PincodeLookupResponse,
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

/** BBPS saved bill as returned from API (GET/POST/PATCH) */
export interface BbpsSavedBillApi {
  id: string;
  nickname: string;
  operatorId: string;
  operatorName: string;
  category: string;
  mobikwikOpId?: string;
  consumerId: string;
  lastAmount?: number;
  billId?: string;
  createdAt: string;
}

/** BBPS saved bill payload for POST (add) */
export interface BbpsSavedBillAdd {
  nickname?: string;
  operatorId: string;
  operatorName: string;
  category: string;
  mobikwikOpId?: string;
  consumerId: string;
  lastAmount?: number;
  billId?: string;
}

/** BBPS pay-cart success response */
export interface BbpsPayCartResponse {
  success: boolean;
  message: string;
  total: number;
  results: { billId: string; operatorId: string; consumerId: string; amount: number; transactionId: string; status: string }[];
}

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
  registerSendOtp(payload: RegisterRequest): Observable<RegisterSendOtpResponse>;
  registerVerify(payload: RegisterVerifyRequest): Observable<LoginResponse>;
  lookupPincode(pincode: string): Observable<PincodeLookupResponse>;
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
    dateFrom?: string;
    dateTo?: string;
  }): Observable<{ transactions: Transaction[]; total: number }>;
  requestRefund(
    transactionId: string,
    amount: number,
    reason: string
  ): Observable<RefundDetails>;
  downloadReceipt(transactionId: string): Observable<Blob | string>;
  getVouchers(params?: { page?: number; limit?: number }): Observable<import('../models/voucher.model').VoucherListResponse>;
  getVoucherDetail(id: number): Observable<import('../models/voucher.model').VoucherDetail>;
  revealVoucherPin(id: number): Observable<import('../models/voucher.model').VoucherRevealPinResponse>;
  claimVoucher(body: { voucherCode: string; pin: string }): Observable<import('../models/voucher.model').VoucherClaimResponse>;
  getPaymentOrders(params?: { page?: number; limit?: number; status?: string }): Observable<{ orders: PaymentOrder[]; total: number }>;
  getVoucherStatement(params?: { page?: number; limit?: number }): Observable<{ entries: VoucherStatementEntry[]; total: number }>;

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
  payCart(payload: { bills: { billId: string; operatorId: string; consumerId: string; amount: number }[]; voucher_id: number; pin: string }): Observable<BbpsPayCartResponse>;
  getBbpsFavorites(): Observable<{ operatorId: string; operatorName: string; category: string; mobikwikOpId?: string }[]>;
  addBbpsFavorite(body: { operatorId: string; operatorName?: string; category?: string; mobikwikOpId?: string }): Observable<{ operatorId: string; operatorName: string; category: string; mobikwikOpId?: string }>;
  removeBbpsFavorite(operatorId: string): Observable<void>;
  getBbpsSavedBills(): Observable<BbpsSavedBillApi[]>;
  addBbpsSavedBill(bill: BbpsSavedBillAdd): Observable<BbpsSavedBillApi>;
  updateBbpsSavedBill(id: string, body: { nickname?: string }): Observable<BbpsSavedBillApi>;
  removeBbpsSavedBill(id: string): Observable<void>;

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
