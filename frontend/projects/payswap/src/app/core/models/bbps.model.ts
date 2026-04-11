// BBPS Category
export type BBPSCategory =
  | 'electricity'
  | 'water'
  | 'gas'
  | 'dth'
  | 'broadband'
  | 'mobile_postpaid'
  | 'landline'
  | 'insurance'
  | 'loan_repayment'
  | 'municipal_taxes'
  | 'education'
  | 'subscription';

// BBPS Operator
export interface BBPSOperator {
  id: string;
  name: string;
  code: string;
  category: BBPSCategory;
  logo?: string;
  description?: string;
  parameters: BBPSParameter[];
  paymentModes: string[];
  minAmount?: number;
  maxAmount?: number;
}

// BBPS Parameter (for bill fetch)
export interface BBPSParameter {
  name: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'date';
  required: boolean;
  pattern?: string;
  maxLength?: number;
  minLength?: number;
  options?: { value: string; label: string }[];
  placeholder?: string;
  helpText?: string;
}

// Bill Fetch Request
export interface BillFetchRequest {
  operatorId: string;
  operatorCode: string;
  parameters: Record<string, string | number>;
}

// Bill Fetch Response
export interface BillFetchResponse {
  billId: string;
  operatorId: string;
  operatorName: string;
  consumerId: string;
  consumerName?: string;
  billNumber: string;
  billDate: Date | string;
  dueDate: Date | string;
  amount: number;
  currency: string;
  billDetails: BBPSBillDetail[];
  latePaymentCharge?: number;
  additionalInfo?: string;
}

// Bill Detail
export interface BBPSBillDetail {
  label: string;
  value: string | number;
}

// BBPS Payment Request
export interface BBPSPaymentRequest {
  billId: string;
  operatorId: string;
  consumerId: string;
  amount: number;
  paymentMode?: string;
  customerName: string;
  customerEmail: string;
  customerPhone: string;
  billDetails?: Record<string, any>;
  /** ParkPe: 'voucher' = use voucher balance; 'pg' = Card/UPI (send orderId, paymentId, gateway) */
  paymentMethod?: 'voucher' | 'pg';
  orderId?: string;
  paymentId?: string;
  gateway?: string;
}

// BBPS Payment Response
export interface BBPSPaymentResponse {
  success: boolean;
  transactionId: string;
  billId: string;
  receiptNumber: string;
  amount: number;
  status: string;
  timestamp: Date | string;
  message?: string;
}
