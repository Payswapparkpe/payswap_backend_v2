import { Injectable, inject } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, from, switchMap, tap, catchError, throwError, map, of } from 'rxjs';
import { API_BACKEND_TOKEN } from '../constants';
import {
  PaymentGateway,
  PaymentRequest,
  PaymentResponse,
  GatewayConfig,
} from 'shared';
import { environment } from '../../../environments/environment';
import { EncryptionService } from './encryption.service';
import { LoggerService } from './logger.service';
import { NotificationService } from './notification.service';

declare var Cashfree: any;

/**
 * Payment Gateway Service – Cashfree only (Razorpay removed).
 * Cashfree v3: script exposes Cashfree(mode). Call Cashfree({ mode: 'sandbox' }) to get instance, then .checkout().
 */
@Injectable({
  providedIn: 'root',
})
export class PaymentGatewayService {
  private api = inject(API_BACKEND_TOKEN);
  private encryption = inject(EncryptionService);
  private logger = inject(LoggerService);
  private notify = inject(NotificationService);
  private router = inject(Router);

  private billingGateMessage(err: unknown): boolean {
    const e = err as { error?: { code?: string; detail?: string } };
    if (e?.error?.code === 'billing_address_incomplete') {
      this.notify.showError(
        e.error?.detail || 'Add your billing address (PIN, state, address) under Settings before paying.'
      );
      void this.router.navigate(['/settings']);
      return true;
    }
    return false;
  }

  private scriptsLoaded: Record<PaymentGateway, boolean> = {
    cashfree: false,
    bbps: false,
    razorpay: false, // kept for type; not used
  };

  /** Get Cashfree v3 instance. Must call after script loaded. Cashfree({ mode }) returns instance with .checkout(). */
  private getCashfreeInstance(): any {
    const CashfreeCtor = (typeof window !== 'undefined' && (window as any).Cashfree) || (typeof Cashfree !== 'undefined' ? Cashfree : null);
    if (!CashfreeCtor || typeof CashfreeCtor !== 'function') return null;
    const mode = environment.paymentGateways.cashfree.environment === 'production' ? 'production' : 'sandbox';
    return CashfreeCtor({ mode });
  }

  getAvailableGateways(): Observable<GatewayConfig[]> {
    return this.api.getGateways();
  }

  initiatePayment(
    gateway: PaymentGateway,
    request: PaymentRequest
  ): Observable<PaymentResponse> {
    this.logger.info('initiate_payment', { service: 'payment', action: 'initiate_payment', gateway });
    return this.loadScript(gateway).pipe(
      switchMap(() => this.api.createOrder(gateway, request)),
      switchMap((orderData) => this.processPayment(gateway, orderData, request)),
      tap((res) =>
        this.logger.info('payment_success', {
          service: 'payment',
          action: 'payment_success',
          gateway,
          transactionId: res?.transactionId,
        })
      ),
      catchError((err) => {
        this.billingGateMessage(err);
        this.logger.warn('payment_failed', { service: 'payment', action: 'payment_failed', gateway, error: err?.message });
        return throwError(() => err);
      })
    );
  }

  /**
   * Create order and open checkout with custom success handler (e.g. for BBPS PG: call payBill instead of verify).
   */
  /**
   * Create order and open Cashfree checkout (redirect). For BBPS return URL must call payBill with orderId/paymentId.
   */
  createOrderAndOpenCheckout(
    gateway: PaymentGateway,
    request: PaymentRequest,
    _onPaymentSuccess: (response: any) => void
  ): Observable<void> {
    const effectiveGateway = gateway === 'razorpay' ? 'cashfree' : gateway;
    return this.loadScript(effectiveGateway as PaymentGateway).pipe(
      switchMap(() => this.api.createOrder(effectiveGateway as PaymentGateway, request)),
      switchMap((orderData) => {
        if (effectiveGateway === 'cashfree') {
          const sessionId = orderData.paymentSessionId ?? orderData.payment_session_id;
          const cf = this.getCashfreeInstance();
          if (!sessionId || !cf || typeof cf.checkout !== 'function') {
            return throwError(
              () =>
                new Error(
                  'Cashfree checkout could not start (missing payment session or SDK). Check CASHFREE_PG_* env and script URL.'
                )
            );
          }
          cf.checkout({ paymentSessionId: sessionId, redirectTarget: '_self' });
        }
        return of(undefined as void);
      }),
      map(() => undefined as void),
      catchError((err) => {
        this.billingGateMessage(err);
        this.logger.warn('createOrderAndOpenCheckout failed', { gateway: effectiveGateway, error: err?.message });
        return throwError(() => err);
      })
    );
  }

  private loadScript(gateway: PaymentGateway): Observable<void> {
    const effective = gateway === 'razorpay' ? 'cashfree' : gateway;
    if (this.scriptsLoaded[effective] || this.scriptsLoaded['cashfree']) {
      return from(Promise.resolve());
    }

    const effectiveGateway = gateway === 'razorpay' ? 'cashfree' : gateway;
    return from(
      new Promise<void>((resolve, reject) => {
        const script = document.createElement('script');
        script.src = environment.paymentGateways.cashfree.scriptUrl;
        script.onload = () => {
          this.scriptsLoaded['cashfree'] = true;
          this.logger.debug('payment script loaded', { service: 'payment', gateway: 'cashfree' });
          resolve();
        };
        script.onerror = () => {
          this.logger.error('payment script load failed', { service: 'payment', gateway: 'cashfree' });
          reject(new Error(`Failed to load ${gateway} SDK`));
        };
        document.body.appendChild(script);
      })
    );
  }

  private processPayment(
    gateway: PaymentGateway,
    orderData: any,
    request: PaymentRequest
  ): Observable<PaymentResponse> {
    return this.processCashfreePayment(orderData, request);
  }

  private processCashfreePayment(
    orderData: any,
    request: PaymentRequest
  ): Observable<PaymentResponse> {
    return new Observable((observer) => {
      const sessionId = orderData.paymentSessionId ?? orderData.payment_session_id;
      if (!sessionId) {
        observer.error(new Error('Payment session not received'));
        return;
      }
      const cf = this.getCashfreeInstance();
      if (!cf) {
        observer.error(new Error('Cashfree SDK not loaded'));
        return;
      }
      if (typeof cf.checkout === 'function') {
        cf.checkout({ paymentSessionId: sessionId, redirectTarget: '_self' });
        // Redirect flow: user is sent to Cashfree; observer never completes here
      } else {
        observer.error(new Error('Cashfree checkout not available'));
      }
    });
  }

  verifyPayment(gateway: PaymentGateway, response: any): Observable<PaymentResponse> {
    this.logger.info('verify_payment', { service: 'payment', action: 'verify_payment', gateway });
    return this.api.verifyPayment(gateway, response).pipe(
      tap((res) =>
        this.logger.info('verify_payment result', {
          service: 'payment',
          gateway,
          success: !!res?.transactionId,
        })
      ),
      catchError((err) => {
        this.logger.warn('verify_payment failed', { service: 'payment', gateway, error: err?.message });
        return throwError(() => err);
      })
    );
  }

  getTransaction(id: string) {
    return this.api.getTransaction(id);
  }

  getTransactionHistory(params?: any) {
    return this.api.getTransactionHistory(params);
  }

  requestRefund(transactionId: string, amount: number, reason: string) {
    return this.api.requestRefund(transactionId, amount, reason);
  }

  downloadReceipt(transactionId: string, options?: { attachment?: boolean; format?: 'pdf' }) {
    return this.api.downloadReceipt(transactionId, options);
  }
}
