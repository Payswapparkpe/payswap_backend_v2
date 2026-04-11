import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import type {
  VoucherListItem,
  VoucherDetail,
  VoucherListResponse,
  VoucherRevealPinResponse,
  VoucherClaimResponse,
} from '../../../core/models/voucher.model';

/**
 * ParkPe customer voucher service – list, detail, reveal PIN.
 * No total balance (RBI gift PPI). Use single voucher + PIN for payments.
 */
@Injectable({
  providedIn: 'root',
})
export class VoucherService {
  private api = inject(API_BACKEND_TOKEN);

  getVouchers(params?: { page?: number; limit?: number }): Observable<VoucherListResponse> {
    return this.api.getVouchers(params);
  }

  getVoucherDetail(id: number): Observable<VoucherDetail> {
    return this.api.getVoucherDetail(id);
  }

  revealPin(id: number): Observable<VoucherRevealPinResponse> {
    return this.api.revealVoucherPin(id);
  }

  claimVoucher(voucherCode: string, pin: string): Observable<VoucherClaimResponse> {
    return this.api.claimVoucher({ voucherCode, pin });
  }
}
