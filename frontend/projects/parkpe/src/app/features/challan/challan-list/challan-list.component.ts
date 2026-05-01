import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { Challan } from '../../../core/models/challan.model';
import { ChallanSessionService } from '../services/challan-session.service';

@Component({
  selector: 'app-challan-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/challan" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="feature-title">Challan Results</h1>
      <p class="sub-title">Saved recent results. Tap any challan to open the full detail view.</p>
      <div class="filter-row">
        <button class="btn btn-outline btn-sm" [class.active]="filter()==='all'" (click)="filter.set('all')">All</button>
        <button class="btn btn-outline btn-sm" [class.active]="filter()==='pending'" (click)="filter.set('pending')">Pending</button>
        <button class="btn btn-outline btn-sm" [class.active]="filter()==='paid'" (click)="filter.set('paid')">Paid</button>
        <button class="btn btn-outline btn-sm" [class.active]="filter()==='overdue'" (click)="filter.set('overdue')">Overdue</button>
      </div>

      @if (loading()) {
        <div class="skeleton-list">
          @for (n of [1,2,3]; track n) {
            <div class="skeleton-card"></div>
          }
        </div>
      } @else if (visibleRows().length === 0) {
        <div class="empty-state card">
          <span class="material-icons">receipt_long</span>
          <h3>No Challans Found</h3>
          <p>Search by vehicle number to find pending traffic challans.</p>
          <a routerLink="/challan/search" class="btn btn-primary">Search Challans</a>
        </div>
      } @else {
        <div class="challans-list">
          @for (challan of visibleRows(); track challan.id) {
            <div class="challan-card card" (click)="openDetail(challan)">
              <div class="challan-header">
                <h3>{{ challan.challanNumber }}</h3>
                <span class="status-badge" [class.pending]="challan.status === 'pending'" [class.overdue]="challan.status === 'overdue'">
                  {{ challan.status | titlecase }}
                </span>
              </div>
              <p class="challan-offence">{{ challan.offence }}</p>
              <div class="challan-details">
                <span><span class="material-icons">directions_car</span> {{ challan.vehicleNumber }}</span>
                <span><span class="material-icons">location_on</span> {{ challan.location }}</span>
              </div>
              <div class="challan-footer">
                <span class="amount">₹{{ challan.totalAmount }}</span>
                <button class="btn btn-primary btn-sm" (click)="$event.stopPropagation(); openDetail(challan)">Open</button>
              </div>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 800px; margin: 0 auto; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .sub-title { color: var(--text-secondary); margin: -1.25rem 0 1rem; font-size: .95rem; }
    .filter-row { display:flex; gap:.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
    .btn-sm.active { background: var(--primary-50); border-color: var(--primary-500); }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .empty-state {
      text-align: center;
      padding: 4rem 2rem;

      .material-icons { font-size: 80px; color: var(--text-muted); margin-bottom: 1rem; }
      h3 { font-size: 1.5rem; margin-bottom: 0.5rem; }
      p { color: var(--text-secondary); margin-bottom: 1.5rem; }
    }
    .challans-list { display: flex; flex-direction: column; gap: 1rem; }
    .challan-card {
      padding: 1.5rem;
      cursor: pointer;
      transition: all 0.2s ease;
      border: 1px solid var(--border-light);

      &:hover { box-shadow: var(--shadow-lg); transform: translateY(-1px); border-color: var(--primary-200); }
    }
    .challan-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;

      h3 { font-size: 1.125rem; font-weight: 600; }
    }
    .status-badge {
      padding: 0.25rem 0.75rem;
      border-radius: var(--radius-full);
      font-size: 0.75rem;
      font-weight: 600;
      background: var(--success);
      color: white;

      &.pending { background: var(--warning); }
      &.overdue { background: var(--error); }
    }
    .challan-offence { color: var(--text-secondary); margin-bottom: 1rem; }
    .challan-details {
      display: flex;
      gap: 1.5rem;
      margin-bottom: 1rem;
      font-size: 0.875rem;
      color: var(--text-secondary);

      span { display: flex; align-items: center; gap: 0.25rem; }
      .material-icons { font-size: 16px; }
    }
    .challan-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 1rem;
      border-top: 1px solid var(--border-light);
    }
    .amount { font-size: 1.5rem; font-weight: 700; color: var(--error); }
    .skeleton-list { display:flex; flex-direction:column; gap: .75rem; }
    .skeleton-card {
      height: 120px; border-radius: var(--radius-md);
      background: linear-gradient(90deg, rgba(0,0,0,.04), rgba(0,0,0,.08), rgba(0,0,0,.04));
      background-size: 200% 100%;
      animation: shimmer 1.2s linear infinite;
    }
    @keyframes shimmer { to { background-position: -200% 0; } }
    .btn-sm { padding: 0.5rem 1.5rem; }
    @media (max-width: 767px) {
      .feature-container { padding: 1rem; }
      .feature-title { font-size: 1.4rem; margin-bottom: 1rem; }
      .sub-title { margin: -.5rem 0 .75rem; font-size: .86rem; }
      .challan-card { padding: 1rem; }
      .challan-details { flex-direction: column; gap: .35rem; }
      .challan-footer { gap: .5rem; }
      .amount { font-size: 1.1rem; }
    }
  `],
})
export class ChallanListComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private session = inject(ChallanSessionService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  challans = signal<Challan[]>([]);
  filter = signal<'all' | 'pending' | 'paid' | 'overdue'>('all');
  loading = signal(false);

  ngOnInit(): void {
    const cached = this.session.results();
    if (cached.length > 0) {
      this.challans.set(cached);
      return;
    }
    const vehicleFromQuery = (this.route.snapshot.queryParams['vehicleNumber'] || '').trim();
    if (vehicleFromQuery) {
      this.loading.set(true);
      this.api.searchChallans({ vehicleNumber: vehicleFromQuery, forceRefresh: false }).subscribe({
        next: (items) => {
          this.challans.set(items || []);
          this.session.save({ vehicleNumber: vehicleFromQuery, items: items || [] });
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
    }
  }

  visibleRows(): Challan[] {
    const f = this.filter();
    const all = this.challans();
    if (f === 'all') return all;
    return all.filter((c) => c.status === f);
  }

  openDetail(challan: Challan): void {
    this.router.navigate(['/challan/detail', challan.id]);
  }
}
