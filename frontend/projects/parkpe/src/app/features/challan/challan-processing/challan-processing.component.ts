import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { Challan } from '../../../core/models/challan.model';

@Component({
  selector: 'app-challan-processing',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="feature-container">
      <h1>Processing Payment</h1>
      <p>Please wait while we process your challan payment...</p>
      <div class="spinner"></div>
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; text-align: center; }
    .spinner { width: 30px; height: 30px; margin: 1rem auto; border:2px solid var(--border-light); border-top-color: var(--primary-500); border-radius:50%; animation: spin .8s linear infinite;}
    @keyframes spin { to { transform: rotate(360deg); } }
  `],
})
export class ChallanProcessingComponent implements OnInit {
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private api = inject(API_BACKEND_TOKEN);

  ngOnInit(): void {
    const challanId = this.route.snapshot.params['id'];
    const state = (this.router.getCurrentNavigation()?.extras?.state ?? window.history.state) as { challan?: Challan; paymentMode?: string };
    const challan = state?.challan;
    if (!challan) {
      this.router.navigate(['/challan/pay', challanId]);
      return;
    }
    this.api
      .payChallan(challanId, {
        challanId: challan.id,
        challanNumber: challan.challanNumber,
        vehicleNumber: challan.vehicleNumber,
        amount: challan.totalAmount,
        customerName: 'User',
        customerEmail: 'user@example.com',
        customerPhone: '+919999999999',
        paymentMode: state?.paymentMode ?? 'upi',
      })
      .subscribe({
        next: (res) =>
          this.router.navigate(['/challan/pay', challanId, 'success'], {
            state: { payment: res },
          }),
        error: (err) =>
          this.router.navigate(['/challan/pay', challanId, 'failed'], {
            state: { message: err?.error?.detail || 'Payment failed' },
          }),
      });
  }
}
