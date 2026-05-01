import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';

@Component({
  selector: 'app-challan-failed',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <h1>Payment Failed</h1>
      <p>{{ message }}</p>
      <a class="btn btn-primary" [routerLink]="['/challan/pay', challanId, 'methods']">Retry Payment</a>
    </div>
  `,
})
export class ChallanFailedComponent {
  private route = inject(ActivatedRoute);
  private state = window.history.state as { message?: string };
  challanId = this.route.snapshot.params['id'];
  message = this.state?.message || 'Unable to process payment right now.';
}
