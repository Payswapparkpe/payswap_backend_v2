import { Injectable, NgZone, inject } from '@angular/core';
import { Observable, interval, merge, of } from 'rxjs';
import { catchError, filter, map, startWith, switchMap, take, timeout } from 'rxjs/operators';
import { API_BACKEND_TOKEN } from '../constants';
import type { Transaction } from '../models/payment.model';
import type { Booking } from '../models/parking.model';

@Injectable({ providedIn: 'root' })
export class RealtimeStatusService {
  private api = inject(API_BACKEND_TOKEN);
  private zone = inject(NgZone);

  watchPayment(orderId: string, maxWaitMs = 60_000): Observable<Transaction | null> {
    const safeOrderId = String(orderId || '').trim();
    if (!safeOrderId) return of(null);
    const poll$ = interval(3000).pipe(
      startWith(0),
      switchMap(() =>
        this.api.getTransaction(safeOrderId).pipe(
          map((txn) => (txn?.status === 'success' ? txn : null)),
          catchError(() => of(null))
        )
      ),
      filter((txn) => txn != null),
      take(1),
      timeout(maxWaitMs),
      catchError(() => of(null))
    );

    const sse$ = this.openSse(`/api/payment/stream/status/${encodeURIComponent(safeOrderId)}`).pipe(
      filter((event) => !!event && String(event['status'] || '').toLowerCase() === 'success'),
      switchMap(() =>
        this.api.getTransaction(safeOrderId).pipe(
          catchError(() => of(null))
        )
      ),
      filter((txn) => txn != null),
      take(1),
      timeout(maxWaitMs),
      catchError(() => of(null))
    );

    return merge(sse$, poll$).pipe(take(1));
  }

  watchBooking(bookingId: string, maxWaitMs = 60_000): Observable<Booking | null> {
    const safeId = String(bookingId || '').trim();
    if (!safeId) return of(null);
    return interval(4000).pipe(
      startWith(0),
      switchMap(() => this.api.getBooking(safeId).pipe(catchError(() => of(null)))),
      filter((b) => b != null),
      map((b) => (b && ['confirmed', 'active', 'completed'].includes(String(b.status)) ? b : null)),
      filter((b) => b != null),
      take(1),
      timeout(maxWaitMs),
      catchError(() => of(null))
    );
  }

  private openSse(url: string): Observable<Record<string, unknown> | null> {
    return new Observable((subscriber) => {
      if (typeof window === 'undefined' || typeof EventSource === 'undefined') {
        subscriber.complete();
        return;
      }
      const source = new EventSource(url);
      source.onmessage = (evt) => {
        this.zone.run(() => {
          try {
            subscriber.next(JSON.parse(evt.data || '{}'));
          } catch {
            subscriber.next(null);
          }
        });
      };
      source.onerror = () => {
        source.close();
        subscriber.complete();
      };
      return () => source.close();
    });
  }
}
