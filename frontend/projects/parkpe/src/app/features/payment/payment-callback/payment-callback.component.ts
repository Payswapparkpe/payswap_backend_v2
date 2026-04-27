import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { BBPSService } from '../../bbps/services/bbps.service';
import { BBPSPaymentRequest } from '../../../core/models/bbps.model';

const BBPS_PENDING_KEY = 'parkpe_bbps_pending_pay';

/** Cashfree redirect / SDK may use different keys for the PG payment id. */
function gatewayPaymentIdFromQuery(params: Record<string, string | undefined>): string {
  const v =
    params['cf_payment_id'] ??
    params['cf_payment_Id'] ??
    params['payment_id'] ??
    params['paymentId'] ??
    params['referenceId'] ??
    '';
  return String(v || '').trim();
}

@Component({
  selector: 'app-payment-callback',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="callback-container">
      <div class="spinner"></div>
      <p>Verifying payment...</p>
    </div>
  `,
  styles: [`
    .callback-container {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 1rem;
    }
  `],
})
export class PaymentCallbackComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private paymentService = inject(PaymentGatewayService);
  private bbps = inject(BBPSService);

  ngOnInit() {
    const gateway = this.route.snapshot.params['gateway'];
    const params = this.route.snapshot.queryParams;
    const pgFromUrl = gatewayPaymentIdFromQuery(params);

    if (!params['order_id'] && !params['orderId']) {
      this.router.navigate(['/payment/status'], {
        queryParams: {
          status: 'failed',
          reason: 'incomplete',
          ...(gateway ? { gateway } : {}),
          ...(pgFromUrl ? { gatewayPaymentId: pgFromUrl } : {}),
        },
      });
      return;
    }

    const orderId = params['order_id'] ?? params['orderId'];

    /** BBPS + Cashfree: complete Mobikwik pay after PG redirect (not voucher verify). */
    if (gateway === 'cashfree') {
      let pending: Partial<BBPSPaymentRequest> | null = null;
      try {
        const raw = sessionStorage.getItem(BBPS_PENDING_KEY);
        if (raw) pending = JSON.parse(raw) as Partial<BBPSPaymentRequest>;
      } catch {
        pending = null;
      }
      if (
        pending &&
        pending.operatorId &&
        pending.consumerId &&
        pending.amount != null &&
        pending.billId
      ) {
        const paymentId =
          params['cf_payment_id'] ??
          params['payment_id'] ??
          params['paymentId'] ??
          params['referenceId'] ??
          '';
        const payload: BBPSPaymentRequest = {
          billId: pending.billId,
          operatorId: pending.operatorId,
          consumerId: pending.consumerId,
          amount: Number(pending.amount),
          customerName: pending.customerName ?? 'Customer',
          customerEmail: pending.customerEmail ?? '',
          customerPhone: pending.customerPhone ?? '',
          billDetails: pending.billDetails,
          paymentMethod: 'pg',
          orderId,
          paymentId: paymentId || undefined,
          gateway: 'cashfree',
        };
        this.bbps.payBill(payload).subscribe({
          next: (res) => {
            try {
              sessionStorage.removeItem(BBPS_PENDING_KEY);
            } catch {
              /* ignore */
            }
            if (res.success) {
              this.router.navigate(['/payment/status'], {
                queryParams: {
                  status: 'success',
                  transactionId: res.transactionId ?? orderId,
                  orderId,
                  amount: payload.amount,
                  gateway: 'cashfree',
                  bbps: '1',
                  ...(paymentId ? { gatewayPaymentId: paymentId } : {}),
                },
              });
            } else {
              this.router.navigate(['/payment/status'], {
                queryParams: {
                  status: 'failed',
                  reason: 'not_confirmed',
                  orderId,
                  gateway: 'cashfree',
                  bbps: '1',
                  ...(paymentId || pgFromUrl ? { gatewayPaymentId: paymentId || pgFromUrl } : {}),
                },
              });
            }
          },
          error: () => {
            try {
              sessionStorage.removeItem(BBPS_PENDING_KEY);
            } catch {
              /* ignore */
            }
            this.router.navigate(['/payment/status'], {
              queryParams: {
                status: 'failed',
                reason: 'not_confirmed',
                orderId,
                gateway: 'cashfree',
                bbps: '1',
                ...(pgFromUrl ? { gatewayPaymentId: pgFromUrl } : {}),
              },
            });
          },
        });
        return;
      }
    }

    this.paymentService.verifyPayment(gateway, params).subscribe({
      next: (response) => {
        const res = response as unknown as Record<string, unknown>;
        const success = res?.['success'] === true;
        const apiPg =
          (typeof res?.['gatewayPaymentId'] === 'string' && res['gatewayPaymentId']) ||
          (typeof res?.['gateway_payment_id'] === 'string' && res['gateway_payment_id']) ||
          '';
        const tid =
          (typeof res?.['transactionId'] === 'string' && res['transactionId']) ||
          (typeof res?.['orderId'] === 'string' && res['orderId']) ||
          orderId ||
          '';
        const amt = res?.['amount'];
        const amountNum =
          typeof amt === 'number' ? amt : amt != null && amt !== '' ? Number(amt) : undefined;
        const gatewayPaymentId = (apiPg || pgFromUrl || '').trim();

        this.router.navigate(['/payment/status'], {
          queryParams: {
            status: success ? 'success' : 'failed',
            ...(gateway ? { gateway } : {}),
            ...(orderId ? { orderId } : {}),
            ...(tid ? { transactionId: tid } : {}),
            ...(gatewayPaymentId ? { gatewayPaymentId } : {}),
            ...(amountNum != null && !Number.isNaN(amountNum) ? { amount: amountNum } : {}),
            ...(!success ? { reason: 'not_confirmed' } : {}),
          },
        });
      },
      error: (err: { status?: number; error?: { detail?: string } }) => {
        // 503 = payment received but voucher could not be issued (e.g. brand not configured)
        if (err?.status === 503) {
          this.router.navigate(['/payment/status'], {
            queryParams: {
              status: 'failed',
              reason: 'voucher_delayed',
              ...(gateway ? { gateway } : {}),
              ...(orderId ? { orderId } : {}),
              ...(pgFromUrl ? { gatewayPaymentId: pgFromUrl } : {}),
            },
          });
          return;
        }
        this.router.navigate(['/payment/status'], {
          queryParams: {
            status: 'failed',
            reason: 'not_confirmed',
            ...(gateway ? { gateway } : {}),
            ...(orderId ? { orderId } : {}),
            ...(pgFromUrl ? { gatewayPaymentId: pgFromUrl } : {}),
          },
        });
      },
    });
  }
}
