import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { NotificationService } from '../../../core/services/notification.service';
import type { BBPSOperator } from '../../../core/models/bbps.model';

@Component({
  selector: 'app-fastag-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <div class="feature-container">
      <h1 class="feature-title">FASTag Recharge</h1>

      <form [formGroup]="fastagForm" (ngSubmit)="onSubmit()" class="fastag-form card">
        <div class="form-group">
          <label>Vehicle Number</label>
          <input
            type="text"
            formControlName="vehicleNumber"
            class="form-control"
            placeholder="e.g., DL01AB1234"
            [disabled]="loading"
          />
        </div>

        <div class="form-group">
          <label>FASTag Biller</label>
          <select
            formControlName="operatorId"
            class="form-control"
            [disabled]="loading || loadingOperators"
          >
            <option value="">Select biller</option>
            @for (op of operators; track op.id) {
              <option [value]="op.id">{{ op.name }}</option>
            }
          </select>
          @if (loadingOperators) {
            <p class="form-hint">Loading FASTag billers...</p>
          }
        </div>

        <div class="form-group">
          <label>Recharge Amount (₹)</label>
          <input
            type="number"
            formControlName="amount"
            class="form-control"
            placeholder="Enter amount"
            [disabled]="loading"
          />
          <p class="form-hint">Minimum: ₹100 | Maximum: ₹10,000</p>
        </div>

        <button type="submit" class="btn btn-primary btn-block" [disabled]="loading">
          @if (loading) {
            <span class="spinner"></span> Processing...
          } @else {
            Continue to Confirm
          }
        </button>
      </form>
    </div>
  `,
  styles: [`
    .feature-container { padding: 0; max-width: 100%; }
    .feature-title { font-size: 1.25rem; font-weight: 700; margin: 0 0 1.25rem; }
    .fastag-form { padding: 2rem; }
    .form-group { margin-bottom: 1.5rem; }
    .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
    .form-control { width: 100%; padding: 0.75rem; border: 2px solid var(--border-light); border-radius: var(--radius-md); }
    .form-hint { font-size: 0.875rem; color: var(--text-secondary); margin-top: 0.5rem; }
    .btn-block { width: 100%; padding: 1rem; }
  `],
})
export class FastagFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private api = inject(API_BACKEND_TOKEN);
  private notification = inject(NotificationService);

  fastagForm: FormGroup;
  loading = false;
  loadingOperators = false;
  operators: BBPSOperator[] = [];

  constructor() {
    this.fastagForm = this.fb.group({
      vehicleNumber: ['', Validators.required],
      operatorId: ['', Validators.required],
      amount: ['', [Validators.required, Validators.min(100), Validators.max(10000)]],
    });
  }

  ngOnInit() {
    const reg = this.route.snapshot.queryParams['registration_number'] ?? this.router.getCurrentNavigation()?.extras?.state?.['registration_number'];
    if (reg && typeof reg === 'string' && reg.trim()) {
      this.fastagForm.patchValue({ vehicleNumber: reg.trim() });
    }
    this.loadFastagOperators();
  }

  private loadFastagOperators() {
    this.loadingOperators = true;
    this.api.getOperators('fastag').subscribe({
      next: (ops) => {
        this.operators = Array.isArray(ops) ? ops : [];
        this.loadingOperators = false;
        if (!this.operators.length) {
          this.notification.showError('FASTag billers not configured. Please import operators sheet.');
          return;
        }
        if (this.operators.length === 1) {
          this.fastagForm.patchValue({ operatorId: this.operators[0].id });
        }
      },
      error: () => {
        this.loadingOperators = false;
        this.notification.showError('Unable to load FASTag billers');
      },
    });
  }

  onSubmit() {
    if (this.fastagForm.invalid) return;
    const vehicleNumber = String(this.fastagForm.value.vehicleNumber ?? '').trim().toUpperCase();
    const operatorId = String(this.fastagForm.value.operatorId ?? '').trim();
    const amount = Number(this.fastagForm.value.amount);
    const selectedOp = this.operators.find((o) => o.id === operatorId);
    this.router.navigate(['/fastag/confirm'], {
      state: {
        recharge: {
          vehicleNumber,
          amount,
          operatorId,
          operatorCode: selectedOp?.code || operatorId,
          operatorName: selectedOp?.name || '',
        },
      },
    });
  }
}
