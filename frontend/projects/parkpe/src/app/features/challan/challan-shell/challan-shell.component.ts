import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive, RouterOutlet, ActivatedRoute } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { NotificationService } from '../../../core/services/notification.service';
import type { Challan } from '../../../core/models/challan.model';

@Component({
  selector: 'app-challan-shell',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink, RouterLinkActive, RouterOutlet],
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
                <label>State (Optional)</label>
                <select formControlName="state" class="form-control">
                  <option value="">All States</option>
                  <option value="KA">Karnataka</option>
                  <option value="DL">Delhi</option>
                  <option value="MH">Maharashtra</option>
                  <option value="TN">Tamil Nadu</option>
                </select>
              </div>
              <button type="submit" class="btn btn-primary btn-block" [disabled]="searchLoading()">
                @if (searchLoading()) {
                  <span class="spinner"></span> Searching...
                } @else {
                  <span class="material-icons">search</span> Search Challans
                }
              </button>
            </form>

            @if (challans().length > 0) {
              <div class="challan-list-wrap">
                <h3 class="challan-list-heading">Results</h3>
                <div class="challans-list">
                  @for (challan of challans(); track challan.id) {
                    <a
                      [routerLink]="['/challan/detail', challan.id]"
                      class="challan-row"
                      routerLinkActive="selected"
                      [routerLinkActiveOptions]="{ exact: false }"
                    >
                      <div class="challan-row-header">
                        <span class="challan-num">{{ challan.challanNumber }}</span>
                        <span class="status-badge" [class.pending]="challan.status === 'pending'">{{ challan.status | titlecase }}</span>
                      </div>
                      <p class="challan-offence">{{ challan.offence }}</p>
                      <div class="challan-row-meta">
                        <span>{{ challan.vehicleNumber }}</span>
                        <span class="amount">₹{{ challan.totalAmount }}</span>
                      </div>
                    </a>
                  }
                </div>
              </div>
            } @else if (searched() && !searchLoading()) {
              <p class="challan-empty-hint">No challans found. Try a different vehicle or state.</p>
            }
          </div>
        </aside>

        <main class="service-col-right">
          @if (hasDetailOrPayRoute()) {
            <router-outlet />
          } @else {
            <div class="service-placeholder">
              <p class="service-placeholder-title">Select a challan</p>
              <p class="service-placeholder-hint">Search by vehicle number above, then choose a challan from the list to view details or pay.</p>
            </div>
          }
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
    .challan-list-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
    .challan-list-heading { font-size: 0.9375rem; font-weight: 600; margin: 0 0 0.5rem; }
    .challans-list { display: flex; flex-direction: column; gap: 0.5rem; overflow-y: auto; min-height: 0; }
    .challan-row {
      display: block; padding: 0.75rem 1rem; border: 1px solid var(--border-light); border-radius: var(--radius-md);
      text-decoration: none; color: inherit; transition: background 0.2s, border-color 0.2s;
    }
    .challan-row:hover { background: var(--surface-muted, #f8fafc); border-color: var(--primary-200); }
    .challan-row.selected { background: var(--primary-50); border-color: var(--primary-400); }
    .challan-row-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; }
    .challan-num { font-weight: 600; font-size: 0.875rem; }
    .status-badge { padding: 0.2rem 0.5rem; border-radius: var(--radius-full); font-size: 0.65rem; font-weight: 600; background: var(--success); color: white; }
    .status-badge.pending { background: var(--warning); color: #1a1a1a; }
    .challan-offence { font-size: 0.8125rem; color: var(--text-secondary); margin: 0 0 0.35rem; }
    .challan-row-meta { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); }
    .challan-row-meta .amount { font-weight: 700; color: var(--error); }
    .challan-empty-hint { font-size: 0.9rem; color: var(--text-secondary); margin: 0.5rem 0 0; }
    .spinner { width: 20px; height: 20px; border: 2px solid var(--border-light); border-top-color: var(--primary-500); border-radius: 50%; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
  `],
})
export class ChallanShellComponent implements OnInit {
  private fb = inject(FormBuilder);
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private notification = inject(NotificationService);

  searchForm = this.fb.group({
    vehicleNumber: ['', Validators.required],
    state: [''],
  });

  challans = signal<Challan[]>([]);
  searchLoading = signal(false);
  searched = signal(false);

  ngOnInit() {
    const vehicleNumber = this.route.snapshot.queryParams['vehicleNumber'] ?? this.router.getCurrentNavigation()?.extras?.state?.['vehicleNumber'];
    if (vehicleNumber && typeof vehicleNumber === 'string' && vehicleNumber.trim()) {
      this.searchForm.patchValue({ vehicleNumber: vehicleNumber.trim() });
    }
  }

  hasDetailOrPayRoute(): boolean {
    const u = this.router.url;
    return u.includes('/challan/detail/') || u.includes('/challan/pay/');
  }

  searchChallans() {
    if (this.searchForm.invalid) return;
    this.searchLoading.set(true);
    this.searched.set(true);
    const req = {
      vehicleNumber: this.searchForm.value.vehicleNumber ?? '',
      state: this.searchForm.value.state ?? undefined,
    };
    this.api.searchChallans(req).subscribe({
      next: (list) => {
        this.challans.set(list ?? []);
        this.searchLoading.set(false);
      },
      error: () => {
        this.notification.showError('Search failed');
        this.searchLoading.set(false);
      },
    });
  }
}
