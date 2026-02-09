import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';

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

  ngOnInit() {
    const gateway = this.route.snapshot.params['gateway'];
    const params = this.route.snapshot.queryParams;

    if (!params['order_id'] && !params['orderId']) {
      this.router.navigate(['/payment/status'], { queryParams: { status: 'failed', reason: 'incomplete' } });
      return;
    }

    const orderId = params['order_id'] ?? params['orderId'];

    this.paymentService.verifyPayment(gateway, params).subscribe({
      next: (response) => {
        const res = response as any;
        const success = res?.success === true;
        const balance = res?.balance;
        this.router.navigate(['/payment/status'], {
          queryParams: {
            status: success ? 'success' : 'failed',
            ...(balance != null && balance !== '' ? { balance: String(balance) } : {}),
            ...(orderId ? { orderId } : {}),
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
              ...(orderId ? { orderId } : {}),
            },
          });
          return;
        }
        this.router.navigate(['/payment/status'], {
          queryParams: { status: 'failed', reason: 'not_confirmed', ...(orderId ? { orderId } : {}) },
        });
      },
    });
  }
}
