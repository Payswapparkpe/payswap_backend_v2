import { Injectable, inject } from '@angular/core';
import { Observable, tap, catchError, throwError } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { LoggerService } from '../../../core/services/logger.service';
import {
  BBPSOperator,
  BillFetchRequest,
  BillFetchResponse,
  BBPSPaymentRequest,
  BBPSPaymentResponse,
} from '../../../core/models/bbps.model';

@Injectable({
  providedIn: 'root',
})
export class BBPSService {
  private api = inject(API_BACKEND_TOKEN);
  private logger = inject(LoggerService);

  getCategories(): Observable<string[]> {
    this.logger.info('getCategories', { service: 'bbps', action: 'getCategories' });
    return this.api.getCategories().pipe(
      tap((cats) => this.logger.debug('getCategories result', { service: 'bbps', count: cats?.length }))
    );
  }

  getOperators(category: string): Observable<BBPSOperator[]> {
    this.logger.info('getOperators', { service: 'bbps', action: 'getOperators', category });
    return this.api.getOperators(category).pipe(
      tap((ops) => this.logger.debug('getOperators result', { service: 'bbps', category, count: ops?.length }))
    );
  }

  fetchBill(request: BillFetchRequest): Observable<BillFetchResponse> {
    this.logger.info('fetchBill', { service: 'bbps', action: 'fetchBill', operatorId: request?.operatorId });
    return this.api.fetchBill(request).pipe(
      tap(() => this.logger.info('fetchBill success', { service: 'bbps', operatorId: request?.operatorId })),
      catchError((err) => {
        this.logger.warn('fetchBill failed', { service: 'bbps', operatorId: request?.operatorId, status: err?.status });
        return throwError(() => err);
      })
    );
  }

  /** Poll Mobikwik bill payment status (GET /api/bbps/pay-status/:ref/). */
  getBillPaymentStatus(refId: string) {
    return this.api.getBbpsPayStatus(refId);
  }

  payBill(payload: BBPSPaymentRequest): Observable<BBPSPaymentResponse> {
    this.logger.info('payBill', { service: 'bbps', action: 'payBill', operatorId: payload?.operatorId });
    return this.api.payBill(payload).pipe(
      tap((res) =>
        this.logger.info('payBill result', {
          service: 'bbps',
          success: res?.success,
          transactionId: res?.transactionId,
        })
      ),
      catchError((err) => {
        this.logger.warn('payBill failed', { service: 'bbps', operatorId: payload?.operatorId, status: err?.status });
        return throwError(() => err);
      })
    );
  }
}
