import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-challan-search',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="feature-title">Search Challans</h1>

      <form [formGroup]="searchForm" (ngSubmit)="searchChallans()" class="search-form card">
        <div class="form-group">
          <label>Vehicle Number</label>
          <input type="text" formControlName="vehicleNumber" class="form-control" placeholder="e.g., KA01AB1234" />
        </div>

        <div class="form-group">
          <label>State (Optional)</label>
          <select formControlName="state" class="form-control">
            <option value="">All States</option>
            <option value="KA">Karnataka</option>
            <option value="DL">Delhi</option>
            <option value="MH">Maharashtra</option>
            <option value="TN">Tamil Nadu</option>
          </select>
        </div>

        <button type="submit" class="btn btn-primary btn-block" [disabled]="loading">
          @if (loading) {
            <span class="spinner"></span> Searching...
          } @else {
            <span class="material-icons">search</span> Search Challans
          }
        </button>
      </form>
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 600px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .search-form { padding: 2rem; }
    .form-group { margin-bottom: 1.5rem; }
    .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
    .form-control { width: 100%; padding: 0.75rem; border: 2px solid var(--border-light); border-radius: var(--radius-md); }
    .btn-block { width: 100%; padding: 1rem; display: flex; align-items: center; justify-content: center; gap: 0.5rem; }
  `],
})
export class ChallanSearchComponent implements OnInit {
  private fb = inject(FormBuilder);
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private notification = inject(NotificationService);

  searchForm: FormGroup;
  loading = false;

  constructor() {
    this.searchForm = this.fb.group({
      vehicleNumber: ['', Validators.required],
      state: [''],
    });
  }

  ngOnInit() {
    const vehicleNumber = this.route.snapshot.queryParams['vehicleNumber'] ?? this.router.getCurrentNavigation()?.extras?.state?.['vehicleNumber'];
    if (vehicleNumber && typeof vehicleNumber === 'string' && vehicleNumber.trim()) {
      this.searchForm.patchValue({ vehicleNumber: vehicleNumber.trim() });
    }
  }

  searchChallans() {
    if (this.searchForm.invalid) return;

    this.loading = true;
    this.api.searchChallans(this.searchForm.value).subscribe({
      next: (challans) => {
        this.router.navigate(['/challan/list'], { state: { challans } });
      },
      error: () => {
        this.loading = false;
        this.notification.showError('Search failed');
      },
    });
  }
}
