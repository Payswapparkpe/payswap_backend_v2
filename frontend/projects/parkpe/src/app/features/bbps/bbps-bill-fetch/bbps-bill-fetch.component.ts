import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { NotificationService } from '../../../core/services/notification.service';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';

@Component({
  selector: 'app-bbps-bill-fetch',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, StepIndicatorComponent],
  template: `
    <div class="feature-container">
      <app-step-indicator [steps]="stepLabels" [currentStep]="3" />
      <h1 class="feature-title">Fetch Bill</h1>

      <form [formGroup]="billForm" (ngSubmit)="fetchBill()" class="bill-form card">
        <div class="form-group">
          <label>Consumer ID / Account Number</label>
          <input type="text" formControlName="consumerId" class="form-control" placeholder="Enter consumer ID" />
        </div>

        <button type="submit" class="btn btn-primary btn-block" [disabled]="loading">
          @if (loading) {
            <span class="spinner"></span> Fetching...
          } @else {
            Fetch Bill
          }
        </button>
      </form>

      @if (bill) {
        <div class="bill-details card">
          <h2>Bill Details</h2>
          <div class="detail-row"><span>Bill Number:</span><span>{{ bill.billNumber }}</span></div>
          <div class="detail-row"><span>Consumer:</span><span>{{ bill.consumerName }}</span></div>
          <div class="detail-row"><span>Due Date:</span><span>{{ bill.dueDate | date }}</span></div>
          <div class="detail-row highlight">
            <span>Amount:</span><span class="amount">₹{{ bill.amount }}</span>
          </div>
          <button class="btn btn-primary btn-block" (click)="payBill()">Pay Now</button>
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 600px; margin: 0 auto; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .bill-form, .bill-details { padding: 2rem; margin-bottom: 1.5rem; }
    .form-group { margin-bottom: 1.5rem; }
    .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
    .form-control { width: 100%; padding: 0.75rem; border: 2px solid var(--border-light); border-radius: var(--radius-md); }
    .btn-block { width: 100%; padding: 1rem; }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light);

      &.highlight {
        background: var(--primary-50);
        padding: 1rem;
        border-radius: var(--radius-md);
        margin: 1rem 0;
        border-bottom: none;
      }
    }
    .amount { font-size: 1.5rem; font-weight: 700; color: var(--primary-700); }
  `],
})
export class BBPSBillFetchComponent {
  readonly stepLabels = ['Category', 'Operator', 'Fetch Bill', 'Pay'];
  private fb = inject(FormBuilder);
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);
  private notification = inject(NotificationService);

  billForm: FormGroup;
  bill: any = null;
  loading = false;

  constructor() {
    this.billForm = this.fb.group({
      consumerId: ['', Validators.required],
    });
  }

  fetchBill() {
    if (this.billForm.invalid) return;

    this.loading = true;
    this.api.fetchBill({
      operatorId: 'op_elec_001',
      operatorCode: 'BESCOM',
      parameters: { consumerId: this.billForm.value.consumerId },
    }).subscribe({
      next: (data) => {
        this.bill = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.notification.showError('Failed to fetch bill');
      },
    });
  }

  payBill() {
    this.router.navigate(['/bbps/pay'], { state: { bill: this.bill } });
  }
}
