import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';

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
          <input type="text" formControlName="vehicleNumber" class="form-control" placeholder="e.g., DL01AB1234" />
        </div>

        <div class="form-group">
          <label>Recharge Amount (₹)</label>
          <input type="number" formControlName="amount" class="form-control" placeholder="Enter amount" />
          <p class="form-hint">Minimum: ₹100 | Maximum: ₹10,000</p>
        </div>

        <button type="submit" class="btn btn-primary btn-block" [disabled]="loading">
          @if (loading) {
            <span class="spinner"></span> Processing...
          } @else {
            Continue to Payment
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

  fastagForm: FormGroup;
  loading = false;

  constructor() {
    this.fastagForm = this.fb.group({
      vehicleNumber: ['', Validators.required],
      amount: ['', [Validators.required, Validators.min(100), Validators.max(10000)]],
    });
  }

  ngOnInit() {
    const reg = this.route.snapshot.queryParams['registration_number'] ?? this.router.getCurrentNavigation()?.extras?.state?.['registration_number'];
    if (reg && typeof reg === 'string' && reg.trim()) {
      this.fastagForm.patchValue({ vehicleNumber: reg.trim() });
    }
  }

  onSubmit() {
    if (this.fastagForm.invalid) return;
    this.router.navigate(['/fastag/confirm'], {
      state: { recharge: this.fastagForm.value }
    });
  }
}
