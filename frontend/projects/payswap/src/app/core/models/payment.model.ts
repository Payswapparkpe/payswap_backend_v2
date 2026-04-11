// Payment Gateway Types
export type PaymentGateway = 'razorpay' | 'cashfree' | 'bbps';

export type PaymentMethod = 'card' | 'netbanking' | 'upi' | 'wallet' | 'emi';

export type PaymentStatus =
  | 'pending'
  | 'processing'
  | 'success'
  | 'failed'
  | 'cancelled'
  | 'refunded'
  | 'partial_refund';

export type TransactionType =
  | 'parking'
  | 'bbps'
  | 'fastag'
  | 'challan'
  | 'voucher_purchase'
  | 'other';

export type RefundStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled';

// Customer Details
export interface CustomerDetails {
  name: string;
  email: string;
  phone: string;
}

export interface Address {
  line1: string;
  line2?: string;
  city: string;
  state: string;
  country: string;
  postalCode: string;
}

// Payment Request
export interface PaymentRequest {
  amount: number;
  currency: string;
  orderId: string;
  orderDescription: string;
  transactionType: TransactionType;
  customer: CustomerDetails;
  callbackUrl?: string;
  returnUrl?: string;
  metadata?: Record<string, any>;
}

// Razorpay Types
export interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  prefill: {
    name: string;
    email: string;
    contact: string;
  };
  theme: {
    color: string;
    backdrop_color?: string;
  };
  modal?: {
    ondismiss?: () => void;
    escape?: boolean;
    animation?: boolean;
  };
  handler: (response: RazorpayResponse) => void;
}

export interface RazorpayResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export interface RazorpayOrder {
  razorpayOrderId: string;
  amount: number;
  currency: string;
  receipt?: string;
}

// Cashfree Types
export interface CashfreeOptions {
  appId: string;
  orderId: string;
  orderAmount: number;
  orderCurrency: string;
  orderNote?: string;
  customerName: string;
  customerEmail: string;
  customerPhone: string;
  returnUrl: string;
  notifyUrl?: string;
  paymentModes?: string;
  theme?: {
    color: string;
    backgroundColor?: string;
  };
}

export interface CashfreeOrderRequest {
  order_id: string;
  order_amount: number;
  order_currency: string;
  customer_details: {
    customer_id: string;
    customer_name: string;
    customer_email: string;
    customer_phone: string;
  };
  order_meta?: {
    return_url: string;
    notify_url?: string;
  };
}

export interface CashfreePaymentResponse {
  orderId: string;
  orderStatus: string;
  paymentSessionId: string;
  txStatus?: string;
  txMsg?: string;
  txTime?: string;
  referenceId?: string;
  signature?: string;
}

// Generic Payment Response
export interface PaymentResponse {
  success: boolean;
  transactionId: string;
  orderId: string;
  gateway: PaymentGateway;
  amount: number;
  currency: string;
  status: PaymentStatus;
  timestamp: Date | string;
  message?: string;
  error?: PaymentError;
  receipt?: string;
  metadata?: Record<string, any>;
  /** ParkPe voucher balance after voucher purchase verify */
  balance?: number;
}

export interface PaymentError {
  code: string;
  message: string;
  description?: string;
  step?: string;
  source?: string;
}

// Transaction
export interface Transaction {
  id: string;
  orderId: string;
  transactionId: string;
  transactionType: TransactionType;
  gateway: PaymentGateway;
  amount: number;
  currency: string;
  status: PaymentStatus;
  customer: CustomerDetails;
  paymentMethod?: PaymentMethod;
  timestamp: Date | string;
  completedAt?: Date | string;
  description: string;
  receipt?: string;
  refund?: RefundDetails;
  metadata?: Record<string, any>;
}

// Refund Details
export interface RefundDetails {
  refundId: string;
  amount: number;
  status: RefundStatus;
  reason: string;
  initiatedAt: Date | string;
  completedAt?: Date | string;
  processedBy?: string;
}

// Gateway Configuration
export interface GatewayConfig {
  name: PaymentGateway;
  displayName: string;
  logo: string;
  enabled: boolean;
  supportedMethods: PaymentMethod[];
  minAmount: number;
  maxAmount: number;
  processingFee?: number;
  description?: string;
}

// Payment State (for NgRx)
export interface PaymentState {
  currentTransaction: Transaction | null;
  lastResponse: PaymentResponse | null;
  loading: boolean;
  error: PaymentError | null;
  availableGateways: GatewayConfig[];
  selectedGateway: PaymentGateway | null;
}

// Receipt Data
export interface Receipt {
  transactionId: string;
  orderId: string;
  date: Date | string;
  amount: number;
  currency: string;
  gateway: PaymentGateway;
  status: PaymentStatus;
  customer: CustomerDetails;
  description: string;
  paymentMethod?: string;
  merchantName: string;
  merchantAddress?: string;
  merchantGSTIN?: string;
  notes?: string[];
}

// Payment order (voucher purchase via PG) – for Payment Report
export interface PaymentOrder {
  id: string;
  orderId: string;
  amount: number;
  currency: string;
  gateway: string;
  status: 'pending' | 'completed' | 'failed';
  referenceId?: string;
  createdAt: string;
}

// Gateway Order Creation Response (for createOrder)
export interface RazorpayOrderResponse {
  id: string; // razorpay_order_id
  entity: string;
  amount: number;
  amount_paid: number;
  amount_due: number;
  currency: string;
  receipt: string;
  offer_id: string | null;
  status: string;
  attempts: number;
  notes: any[];
  created_at: number;
  key?: string; // Often returned for convenience
}

export interface CashfreeOrderResponse {
  cf_order_id: string;
  order_id: string;
  payment_session_id: string;
  order_status: string;
  order_token?: string; // Legacy
}

export type GatewayOrderResponse = RazorpayOrderResponse | CashfreeOrderResponse | any;

// Voucher statement entry (credit/debit) – for Voucher Statement report
export interface VoucherStatementEntry {
  id: string;
  amount: number;
  transactionType: 'credit' | 'debit';
  balanceAfter?: number;
  referenceId?: string;
  serviceCode?: string;
  description?: string;
  createdAt: string;
}
