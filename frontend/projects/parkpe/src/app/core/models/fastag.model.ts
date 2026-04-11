// FASTag Recharge Request
export interface FastagRechargeRequest {
  vehicleNumber: string;
  fastagId?: string;
  operatorId?: string;
  operatorCode?: string;
  operatorName?: string;
  amount: number;
  customerName: string;
  customerEmail: string;
  customerPhone: string;
  provider?: string; // Bank/Provider name
}

// FASTag Recharge Response
export interface FastagRechargeResponse {
  success: boolean;
  orderId: string;
  transactionId?: string;
  vehicleNumber: string;
  amount: number;
  status: 'pending' | 'success' | 'failed';
  timestamp: Date | string;
  message?: string;
  balanceAfterRecharge?: number;
}

// FASTag Details
export interface FastagDetails {
  fastagId: string;
  vehicleNumber: string;
  provider: string;
  balance: number;
  status: 'active' | 'inactive' | 'blocked';
  lastRechargeDate?: Date | string;
  lastRechargeAmount?: number;
  registrationDate?: Date | string;
}

// FASTag Transaction
export interface FastagTransaction {
  id: string;
  fastagId: string;
  vehicleNumber: string;
  type: 'recharge' | 'toll' | 'refund';
  amount: number;
  balance: number;
  timestamp: Date | string;
  location?: string;
  status: string;
}
