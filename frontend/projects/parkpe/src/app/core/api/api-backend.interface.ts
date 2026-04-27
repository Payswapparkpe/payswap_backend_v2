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

/** Poll GET /api/bbps/pay-status/<ref>/ (Mobikwik bill payment phase) */
export interface BbpsPayStatusResponse {
  success: boolean;
  ref_id: string;
  vendorStatus?: string | null;
  phase: 'success' | 'failed' | 'pending';
  message?: string;
}

export interface NotificationBannerItem {
  id: number;
  name: string;
  title: string;
  message: string;
  ctaText?: string;
  ctaUrl?: string;
  imageUrl?: string;
  bgColor?: string;
  textColor?: string;
  priority?: number;
}

export interface InboxNotificationItem {
  id: number;
  title: string;
  message: string;
  channel: string;
  isRead: boolean;
  readAt?: string | null;
  deepLink?: string;
  metadata?: Record<string, unknown>;
  createdAt?: string | null;
}

export interface FleetControlCenterKpi {
  label: string;
  value: string | number;
  trend?: string;
}

export interface FleetControlCenterModule {
  title: string;
  description: string;
  route: string;
  cta: string;
}

export interface FleetControlCenterResponse {
  kpis: FleetControlCenterKpi[];
  priorityAlerts: string[];
  modules: FleetControlCenterModule[];
}

export interface FleetListResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

export interface FleetVehicleItem {
  id: number;
  /** ParkPe user id the vehicle is registered under (self or a roster driver). */
  ownerUserId?: number;
  registrationNumber: string;
  vehicleType: string;
  brand: string;
  model: string;
  year?: number | null;
  isPrimary: boolean;
  ownerName: string;
  ownerPhone: string;
  scans24h: number;
  calls24h: number;
  complianceState: string;
  insuranceUpto?: string | null;
  pucUpto?: string | null;
  createdAt?: string | null;
}

/** POST /api/dashboard/fleet/vehicles — matches Django VehicleCreateSerializer + declaration. */
export interface FleetVehicleCreatePayload {
  vehicleType: string;
  registrationNumber: string;
  brand: string;
  model: string;
  year?: number | null;
  acceptOwnershipDeclaration: boolean;
  /** Fleet admin/manager only: register under this driver (must be on roster). */
  ownerUserId?: number | null;
}

export interface FleetRosterDriverItem {
  userId: number;
  username: string;
  name: string;
  phone: string;
}

export type FleetVehiclesListResponse = FleetListResponse<FleetVehicleItem> & {
  canDelegateToDrivers?: boolean;
  rosterDrivers?: FleetRosterDriverItem[];
};

export interface FleetDriverItem {
  id: number;
  name: string;
  phone: string;
  email: string;
  city?: string | null;
  vehiclesCount: number;
  scans24h: number;
  reportsAgainst24h: number;
  warningCount: number;
  blockedUntil?: string | null;
}

export interface FleetTripItem {
  id: number;
  qrCode: string;
  vehicleId?: number | null;
  registrationNumber: string;
  vehicleType: string;
  scannedBy: string;
  scannerPhone: string;
  ipAddress?: string | null;
  createdAt?: string | null;
  /** `manual` = logged from Fleet Trips form; `connect` = real QR scan. */
  entrySource?: 'connect' | 'manual';
}

/** POST /api/dashboard/fleet/trips — manual visit (no on-site QR). */
export interface FleetTripManualCreatePayload {
  vehicleId: number;
  notes?: string;
}

export interface FleetComplianceItem {
  vehicleId: number;
  registrationNumber: string;
  ownerName: string;
  ownerPhone: string;
  insuranceUpto?: string | null;
  pucUpto?: string | null;
  complianceState: string;
}

export interface FleetComplianceResponse extends FleetListResponse<FleetComplianceItem> {
  summary: {
    compliant: number;
    expiring: number;
    expired: number;
    missing_rc: number;
  };
}

export interface FleetTrendPoint {
  date: string;
  label: string;
  scans: number;
  calls: number;
  callSuccessRate: number;
  reports: number;
}

export interface FleetTrendsResponse {
  series: FleetTrendPoint[];
  days: number;
}

/** GET /api/dashboard/fleet/interest/status */
export interface FleetInterestStatus {
  status: 'none' | 'pending' | 'approved' | 'rejected';
  submittedAt?: string;
  companyName?: string;
  message?: string;
  rejectionReason?: string;
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

export interface PasskeyStatusResponse {
  supported: boolean;
  enabled: boolean;
}

export interface PasskeyOptionsResponse {
  publicKey: Record<string, unknown>;
}

export interface PasskeyCredentialItem {
  id: number;
  label: string;
  transports: string[];
  createdAt?: string | null;
  lastUsedAt?: string | null;
}

export interface PinStatusResponse {
  hasPin: boolean;
  pinSetAt?: string | null;
  pinLockedUntil?: string | null;
  isLocked: boolean;
  fullAuthFresh: boolean;
}

export interface SecurityOverviewResponse {
  mfa: { enabled: boolean; configured: boolean; method?: string | null };
  passkey: { enabled: boolean };
  pinLock: { pinSet: boolean; pinSetAt?: string | null; pinLockedUntil?: string | null; fullAuthFresh?: boolean };
  connect: { blockedUntil?: string | null; warningCount: number };
  devices: { id: number; device_platform: string; app_platform: string; is_active: boolean; last_seen_at?: string | null; updated_at?: string | null }[];
}

export interface SecurityActivityItem {
  id: number;
  source: string;
  action: string;
  change_summary: Record<string, unknown>;
  created_at: string;
}

export interface ApiBackend {
  // Auth API
  login(credentials: LoginRequest): Observable<LoginResponse>;
  fleetLogin(credentials: LoginRequest): Observable<LoginResponse>;
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
  getPinStatus(): Observable<PinStatusResponse>;
  setSessionPin(payload: { pin: string; currentPin?: string; forceReset?: boolean }): Observable<{ success: boolean; hasPin: boolean }>;
  verifySessionPin(pin: string): Observable<{ success: boolean; verified: boolean; remainingAttempts?: number }>;
  getPasskeyStatus(): Observable<PasskeyStatusResponse>;
  getPasskeyRegisterOptions(): Observable<PasskeyOptionsResponse>;
  verifyPasskeyRegistration(credential: Record<string, unknown>): Observable<{ success: boolean; enabled: boolean }>;
  getPasskeyAuthOptions(): Observable<PasskeyOptionsResponse>;
  verifyPasskeyAuth(credential: Record<string, unknown>): Observable<{ success: boolean; verified: boolean }>;
  disablePasskey(): Observable<{ success: boolean; enabled: boolean }>;
  getPasskeyCredentials(): Observable<{ items: PasskeyCredentialItem[] }>;
  updatePasskeyCredential(credentialId: number, label: string): Observable<{ success: boolean; id: number; label: string }>;
  deletePasskeyCredential(credentialId: number): Observable<{ success: boolean; enabled: boolean }>;
  requestPasskeyRecoveryOtp(): Observable<{ message: string; expires_in: number }>;
  verifyPasskeyRecoveryOtp(otp: string): Observable<{ success: boolean; revoked: number; enabled: boolean }>;
  getSecurityOverview(): Observable<SecurityOverviewResponse>;
  revokeSessions(payload?: { device_id?: number }): Observable<{ success: boolean; revoked: number }>;
  getSecurityActivity(): Observable<{ items: SecurityActivityItem[] }>;

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
  downloadReceipt(
    transactionId: string,
    options?: { attachment?: boolean; format?: 'pdf' }
  ): Observable<Blob | string>;
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
  getBbpsPayStatus(refId: string): Observable<BbpsPayStatusResponse>;
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
  getNotificationBanners(params?: { slot?: string; screen?: string; service?: string }): Observable<{ banners: NotificationBannerItem[] }>;
  getNotificationFeed(params?: { limit?: number; offset?: number }): Observable<{ items: InboxNotificationItem[]; total: number }>;
  getNotificationUnreadCount(): Observable<{ unread: number }>;
  markNotificationRead(notificationId: number): Observable<{ success: boolean }>;
  registerPushToken(payload: { token: string; devicePlatform?: string; appPlatform?: string }): Observable<{ success: boolean; id: number }>;
  getFleetControlCenter(): Observable<FleetControlCenterResponse>;
  getFleetVehicles(params?: { page?: number; limit?: number; search?: string; vehicleType?: string }): Observable<FleetVehiclesListResponse>;
  createFleetVehicle(payload: FleetVehicleCreatePayload): Observable<FleetVehicleItem>;
  getFleetRoster(): Observable<{ canDelegateToDrivers: boolean; rosterDrivers: FleetRosterDriverItem[] }>;
  linkFleetRosterDriver(payload: { driverUserId?: number; username?: string; phone?: string }): Observable<FleetRosterDriverItem>;
  unlinkFleetRosterDriver(driverUserId: number): Observable<void>;
  getFleetDrivers(params?: { page?: number; limit?: number; search?: string }): Observable<FleetListResponse<FleetDriverItem>>;
  getFleetTrips(params?: { page?: number; limit?: number; dateFrom?: string; dateTo?: string }): Observable<FleetListResponse<FleetTripItem>>;
  createFleetTripManual(payload: FleetTripManualCreatePayload): Observable<FleetTripItem>;
  getFleetCompliance(params?: { page?: number; limit?: number; status?: string }): Observable<FleetComplianceResponse>;
  getFleetTrends(params?: { days?: number }): Observable<FleetTrendsResponse>;
  getFleetInterestStatus(): Observable<FleetInterestStatus>;
  submitFleetInterest(payload: { companyName?: string; message?: string }): Observable<{
    success: boolean;
    status: string;
    submittedAt?: string;
    message?: string;
  }>;
}
