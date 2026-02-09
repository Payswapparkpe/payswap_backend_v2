import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import type {
  VoucherListItem,
  VoucherDetail,
  VoucherListResponse,
  VoucherRevealPinResponse,
} from '../../../core/models/voucher.model';

/**
 * ParkPe customer voucher service – list, detail, reveal PIN, balance.
 * Uses VoucherX (Gift Voucher) APIs.
 */
@Injectable({
  providedIn: 'root',
})
export class VoucherService {
  private api = inject(API_BACKEND_TOKEN);

  getBalance(): Observable<{ balance: number; currency: string }> {
    return this.api.getVoucherBalance();
  }

  getVouchers(params?: { page?: number; limit?: number }): Observable<VoucherListResponse> {
    return this.api.getVouchers(params);
  }

  getVoucherDetail(id: number): Observable<VoucherDetail> {
    return this.api.getVoucherDetail(id);
  }

  revealPin(id: number): Observable<VoucherRevealPinResponse> {
    return this.api.revealVoucherPin(id);
  }
}
