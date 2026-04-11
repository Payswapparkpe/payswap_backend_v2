import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { FastagRechargeRequest, FastagRechargeResponse } from '../../../core/models/fastag.model';

@Injectable({
  providedIn: 'root',
})
export class FastagService {
  private api = inject(API_BACKEND_TOKEN);

  createRecharge(payload: FastagRechargeRequest): Observable<FastagRechargeResponse> {
    return this.api.createRechargeOrder(payload);
  }
}
