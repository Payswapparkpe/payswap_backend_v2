import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { Challan } from '../../../core/models/challan.model';

@Component({
  selector: 'app-challan-payment-methods',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a [routerLink]="['/challan/pay', challanId]" class="back-link"><span class="material-icons">arrow_back</span> Back</a>
      <h1 class="feature-title">Select Payment Method</h1>
      @if (challan) {
        <div class="card payment-card">
          <p><strong>{{ challan.challanNumber }}</strong> · {{ challan.vehicleNumber }}</p>
          <p class="amount">₹{{ challan.totalAmount }}</p>
          <div class="method-grid">
            <button class="btn" [class.active]="paymentMode==='upi'" (click)="paymentMode='upi'">UPI</button>
            <button class="btn" [class.active]="paymentMode==='card'" (click)="paymentMode='card'">Card</button>
            <button class="btn" [class.active]="paymentMode==='netbanking'" (click)="paymentMode='netbanking'">Netbanking</button>
          </div>
          <button class="btn btn-primary btn-block" (click)="continue()">Continue</button>
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 1rem; max-width: 640px; margin: 0 auto; }
    .back-link { display:inline-flex; gap:.5rem; align-items:center; margin-bottom:1rem; text-decoration:none; }
    .feature-title { margin: 0 0 1rem; }
    .payment-card { padding: 1rem; }
    .amount { font-size: 1.5rem; font-weight: 700; color: var(--error); }
    .method-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.5rem; margin:1rem 0; }
    .method-grid .btn { border:1px solid var(--border-light); }
    .method-grid .btn.active { border-color: var(--primary-500); background: var(--primary-50); }
    .btn-block { width: 100%; }
  `],
})
export class ChallanPaymentMethodsComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  challanId = '';
  challan: Challan | null = null;
  paymentMode: 'upi' | 'card' | 'netbanking' = 'upi';

  ngOnInit(): void {
    this.challanId = this.route.snapshot.params['id'];
    this.api.getChallan(this.challanId).subscribe({ next: (c) => (this.challan = c) });
  }

  continue(): void {
    this.router.navigate(['/challan/pay', this.challanId, 'processing'], {
      state: { challan: this.challan, paymentMode: this.paymentMode },
    });
  }
}
