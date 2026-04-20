/** ParkPe customer voucher (Gift Voucher / VoucherX) – list and detail from API */

export interface VoucherListItem {
  id: number;
  /** Display code from API (`voucherCode`); hyphenated for 16-char codes. */
  voucherCode: string;
  referenceNumber: string;
  originalAmount: number;
  currentBalance: number;
  currency: string;
  status: string;
  issuedAt: string | null;
  /** True when metadata.parkpe_user_id is set (ParkPe account linked). */
  parkpeLinked?: boolean;
  /** Formatted linked profile phone when linked; else null. */
  linkedUserPhone?: string | null;
}

export interface VoucherTransaction {
  id: number;
  transactionType: string;
  transactionId?: string;
  transactionDirection?: 'credit' | 'debit';
  transactionAmount: number | null;
  balanceBefore: number;
  balanceAfter: number;
  redemptionMethod: string | null;
  transactionStatus: string;
  transactionRef: string | null;
  createdAt: string | null;
}

export interface VoucherDetail {
  id: number;
  voucherCode: string;
  referenceNumber: string;
  originalAmount: number;
  currentBalance: number;
  currency: string;
  status: string;
  issuedAt: string | null;
  parkpeLinked?: boolean;
  linkedUserPhone?: string | null;
  transactions: VoucherTransaction[];
}

export interface VoucherListResponse {
  vouchers: VoucherListItem[];
  total: number;
}

export interface VoucherRevealPinResponse {
  pin: string;
}

export interface VoucherClaimResponse {
  success: boolean;
  message: string;
  voucherId: number;
}
