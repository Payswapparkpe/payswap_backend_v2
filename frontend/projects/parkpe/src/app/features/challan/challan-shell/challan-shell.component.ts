import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { NotificationService } from '../../../core/services/notification.service';
import type { Challan } from '../../../core/models/challan.model';
import { ChallanSessionService } from '../services/challan-session.service';

@Component({
  selector: 'app-challan-shell',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="challan-shell">
      <div class="challan-shell-head">
        <a routerLink="/dashboard" class="back-link">
          <span class="material-icons">arrow_back</span> Back to Dashboard
        </a>
        <h1 class="page-title">Challans</h1>
      </div>

      <div class="service-layout">
        <aside class="service-col-left">
          <div class="service-panel challan-left-panel">
            <form [formGroup]="searchForm" (ngSubmit)="searchChallans()" class="challan-search-form">
              <div class="form-group">
                <label>Vehicle Number</label>
                <input type="text" formControlName="vehicleNumber" class="form-control" placeholder="e.g., KA01AB1234" />
              </div>
              <div class="form-group">
                <label>Challan Number (Optional)</label>
                <input type="text" formControlName="challanNumber" class="form-control" placeholder="e.g., CHLN123456" />
              </div>
              <div class="form-group">
                <label>State (Optional)</label>
                <select formControlName="state" class="form-control">
                  <option value="">All States</option>
                  @for (st of indiaStates; track st.code) {
                    <option [value]="st.code">{{ st.name }}</option>
                  }
                </select>
              </div>
              <div class="quick-links">
                <a routerLink="/challan/history" class="link-chip">History</a>
                <a routerLink="/challan/vehicles" class="link-chip">My Vehicles</a>
              </div>
              <button type="submit" class="btn btn-primary btn-block" [disabled]="searchLoading()">
                @if (searchLoading()) {
                  <span class="spinner"></span> Searching...
                } @else {
                  <span class="material-icons">search</span> Search Challans
                }
              </button>
              <button
                type="button"
                class="btn btn-outline btn-block"
                [disabled]="searchLoading() || !(searchForm.value.vehicleNumber || '').trim()"
                (click)="refreshChallans()"
              >
                <span class="material-icons">refresh</span> Refresh Challans
              </button>
            </form>
            @if (lastUpdatedAt()) {
              <p class="last-updated">Last fetched: {{ lastUpdatedAt() | date:'dd MMM, hh:mm a' }}</p>
            }
          </div>
        </aside>

        <main class="service-col-right">
          <div class="service-placeholder">
            <p class="service-placeholder-title">Find challans and open full list view</p>
            <p class="service-placeholder-hint">Search by vehicle number. We save latest results and show them in a clean list page.</p>
            <a routerLink="/challan/list" class="btn btn-primary">Open Challan List</a>
          </div>
        </main>
      </div>
    </div>
  `,
  styles: [`
    .challan-shell { padding: 1rem; max-width: 1400px; margin: 0 auto; }
    .challan-shell-head { margin-bottom: 1rem; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 0.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .page-title { font-size: 1.5rem; font-weight: 700; margin: 0; }
    .challan-left-panel { display: flex; flex-direction: column; gap: 1rem; min-height: 0; }
    .challan-search-form .form-group { margin-bottom: 1rem; }
    .challan-search-form .form-group label { display: block; margin-bottom: 0.35rem; font-weight: 500; font-size: 0.875rem; }
    .challan-search-form .form-control { width: 100%; padding: 0.6rem 0.75rem; border: 1px solid var(--border-light); border-radius: var(--radius-md); }
    .challan-search-form .btn-block { width: 100%; padding: 0.75rem; display: flex; align-items: center; justify-content: center; gap: 0.5rem; }
    .quick-links { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.75rem; }
    .link-chip { border: 1px solid var(--border-light); border-radius: var(--radius-full); font-size: 0.75rem; padding: 0.25rem 0.6rem; text-decoration: none; color: inherit; }
    .last-updated { font-size: 0.8rem; color: var(--text-muted); margin-top: .25rem; }
    .spinner { width: 20px; height: 20px; border: 2px solid var(--border-light); border-top-color: var(--primary-500); border-radius: 50%; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (max-width: 767px) {
      .service-layout { display: block; }
      .service-col-left, .service-col-right { width: 100%; }
      .service-col-right { margin-top: 0.75rem; }
    }
  `],
})
export class ChallanShellComponent implements OnInit {
  private fb = inject(FormBuilder);
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private notification = inject(NotificationService);
  private session = inject(ChallanSessionService);

  searchForm = this.fb.group({
    vehicleNumber: ['', Validators.required],
    challanNumber: [''],
    state: [''],
  });

  challans = signal<Challan[]>([]);
  searchLoading = signal(false);
  searched = signal(false);
  lastUpdatedAt = this.session.updatedAt;
  indiaStates = [
    { code: 'AN', name: 'Andaman and Nicobar Islands' }, { code: 'AP', name: 'Andhra Pradesh' },
    { code: 'AR', name: 'Arunachal Pradesh' }, { code: 'AS', name: 'Assam' }, { code: 'BR', name: 'Bihar' },
    { code: 'CH', name: 'Chandigarh' }, { code: 'CT', name: 'Chhattisgarh' }, { code: 'DN', name: 'Dadra and Nagar Haveli and Daman and Diu' },
    { code: 'DL', name: 'Delhi' }, { code: 'GA', name: 'Goa' }, { code: 'GJ', name: 'Gujarat' }, { code: 'HR', name: 'Haryana' },
    { code: 'HP', name: 'Himachal Pradesh' }, { code: 'JK', name: 'Jammu and Kashmir' }, { code: 'JH', name: 'Jharkhand' },
    { code: 'KA', name: 'Karnataka' }, { code: 'KL', name: 'Kerala' }, { code: 'LA', name: 'Ladakh' }, { code: 'LD', name: 'Lakshadweep' },
    { code: 'MP', name: 'Madhya Pradesh' }, { code: 'MH', name: 'Maharashtra' }, { code: 'MN', name: 'Manipur' }, { code: 'ML', name: 'Meghalaya' },
    { code: 'MZ', name: 'Mizoram' }, { code: 'NL', name: 'Nagaland' }, { code: 'OD', name: 'Odisha' }, { code: 'PY', name: 'Puducherry' },
    { code: 'PB', name: 'Punjab' }, { code: 'RJ', name: 'Rajasthan' }, { code: 'SK', name: 'Sikkim' }, { code: 'TN', name: 'Tamil Nadu' },
    { code: 'TG', name: 'Telangana' }, { code: 'TR', name: 'Tripura' }, { code: 'UP', name: 'Uttar Pradesh' }, { code: 'UT', name: 'Uttarakhand' },
    { code: 'WB', name: 'West Bengal' },
  ];

  ngOnInit() {
    const qp = this.route.snapshot.queryParams;
    const vehicleNumber =
      qp['vehicleNumber'] ??
      qp['registrationNumber'] ??
      qp['registration_number'] ??
      this.router.getCurrentNavigation()?.extras?.state?.['vehicleNumber'];
    if (vehicleNumber && typeof vehicleNumber === 'string' && vehicleNumber.trim()) {
      this.searchForm.patchValue({ vehicleNumber: vehicleNumber.trim() });
      this.fetchChallans(false);
    }
  }

  searchChallans() {
    this.fetchChallans(false);
  }

  refreshChallans() {
    this.fetchChallans(true);
  }

  private fetchChallans(forceRefresh: boolean) {
    if (this.searchForm.invalid) return;
    this.searchLoading.set(true);
    this.searched.set(true);
    const req = {
      vehicleNumber: this.searchForm.value.vehicleNumber ?? '',
      state: this.searchForm.value.state ?? undefined,
      forceRefresh,
    };
    this.api.searchChallans(req).subscribe({
      next: (list) => {
        const queryChallan = (this.searchForm.value.challanNumber || '').trim().toLowerCase();
        const filtered = queryChallan
          ? (list ?? []).filter((c: Challan) =>
              String(c.challanNumber || '').toLowerCase().includes(queryChallan)
            )
          : (list ?? []);
        this.challans.set(filtered);
        this.session.save({
          vehicleNumber: (this.searchForm.value.vehicleNumber || '').trim().toUpperCase(),
          state: this.searchForm.value.state ?? '',
          challanNumber: this.searchForm.value.challanNumber ?? '',
          items: filtered,
        });
        this.router.navigate(['/challan/list']);
        this.searchLoading.set(false);
      },
      error: () => {
        this.notification.showError('Search failed');
        this.searchLoading.set(false);
      },
    });
  }
}
