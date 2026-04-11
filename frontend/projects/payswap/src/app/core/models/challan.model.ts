// Challan Search Request
export interface ChallanSearchRequest {
  vehicleNumber: string;
  state?: string;
  chassisNumber?: string;
  engineNumber?: string;
}

// Challan
export interface Challan {
  id: string;
  challanNumber: string;
  vehicleNumber: string;
  vehicleOwnerName?: string;
  offence: string;
  offenceCode?: string;
  offenceDate: Date | string;
  location: string;
  state: string;
  amount: number;
  penaltyAmount?: number;
  totalAmount: number;
  currency: string;
  dueDate?: Date | string;
  status: 'pending' | 'paid' | 'overdue' | 'disputed';
  issuingAuthority: string;
  officerName?: string;
  additionalDetails?: ChallanDetail[];
  images?: string[];
  paymentDeadline?: Date | string;
}

// Challan Detail
export interface ChallanDetail {
  label: string;
  value: string | number;
}

// Challan Payment Request
export interface ChallanPaymentRequest {
  challanId: string;
  challanNumber: string;
  vehicleNumber: string;
  amount: number;
  customerName: string;
  customerEmail: string;
  customerPhone: string;
  paymentMode?: string;
}

// Challan Payment Response
export interface ChallanPaymentResponse {
  success: boolean;
  transactionId: string;
  challanId: string;
  receiptNumber: string;
  amount: number;
  status: string;
  paidAt: Date | string;
  message?: string;
}

// Challan State (for NgRx)
export interface ChallanState {
  challans: Challan[];
  selectedChallan: Challan | null;
  loading: boolean;
  error: string | null;
}
