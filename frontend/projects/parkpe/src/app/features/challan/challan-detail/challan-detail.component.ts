import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { Challan } from '../../../core/models/challan.model';

@Component({
  selector: 'app-challan-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/challan/list" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Challans
      </a>
      @if (loading) {
        <div class="loading-state card">
          <div class="skeleton-line wide"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line"></div>
        </div>
      } @else if (challan) {
        <div class="challan-detail card">
          <h1>Challan Details</h1>
          <div class="top-status-row">
            <span class="status-pill" [class.pending]="challan.status==='pending'" [class.overdue]="challan.status==='overdue'">{{ challan.status | titlecase }}</span>
            @if (challan.paymentDeadline) {
              <span class="due-pill">{{ dueCountdown(challan.paymentDeadline) }}</span>
            }
          </div>
          <div class="detail-row"><span>Challan Number:</span><span>{{ challan.challanNumber }}</span></div>
          <div class="detail-row"><span>Vehicle:</span><span>{{ challan.vehicleNumber }}</span></div>
          <div class="detail-row"><span>State:</span><span>{{ challan.state || '-' }}</span></div>
          @if (challan.vehicleOwnerName) {
            <div class="detail-row"><span>Owner:</span><span>{{ challan.vehicleOwnerName }}</span></div>
          }
          <div class="detail-row"><span>Offence:</span><span>{{ challan.offence }}</span></div>
          <div class="detail-row"><span>Date:</span><span>{{ formatDate(challan.offenceDate) }}</span></div>
          <div class="detail-row"><span>Location:</span><span>{{ challan.location }}</span></div>
          @if (challan.paymentDeadline) {
            <div class="detail-row"><span>Due In:</span><span>{{ dueCountdown(challan.paymentDeadline) }}</span></div>
          }
          @if (challan.issuingAuthority) {
            <div class="detail-row"><span>Issuing Authority:</span><span>{{ challan.issuingAuthority }}</span></div>
          }
          <div class="detail-row highlight">
            <span>Total Amount:</span><span class="amount">₹{{ challan.totalAmount }}</span>
          </div>

          @if (challan.additionalDetails?.length) {
            <div class="extra-details">
              <h3>Additional Details</h3>
              @for (item of challan.additionalDetails; track $index) {
                <div class="detail-row">
                  <span>{{ item.label }}</span>
                  <span>{{ item.value || '-' }}</span>
                </div>
              }
            </div>
          }
          @if (challan.images?.length) {
            <div class="extra-details">
              <h3>Violation Images</h3>
              <div class="image-grid">
                @for (img of challan.images; track img) {
                  <a [href]="img" target="_blank" rel="noopener">View image</a>
                }
              </div>
            </div>
          }
          
          @if (challan.status === 'pending') {
            <button class="btn btn-primary btn-block pay-cta" (click)="payChallan()">
              Pay ₹{{ challan.totalAmount }}
            </button>
          }
          <a class="btn btn-outline btn-block" [href]="disputeUrl(challan.state)" target="_blank" rel="noopener">Dispute on e-Challan portal</a>
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 700px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .challan-detail { padding: 2rem; border: 1px solid var(--border-light); }
    h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 1.5rem; }
    .top-status-row { display:flex; justify-content:space-between; align-items:center; margin-bottom: .75rem; gap: .5rem; flex-wrap: wrap; }
    .status-pill, .due-pill { border-radius: 999px; font-size: .75rem; font-weight: 600; padding: .25rem .6rem; }
    .status-pill { background: var(--success); color: #fff; }
    .status-pill.pending { background: var(--warning); color: #1a1a1a; }
    .status-pill.overdue { background: var(--error); color: #fff; }
    .due-pill { border: 1px solid var(--border-light); color: var(--text-secondary); }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light);

      &.highlight {
        background: var(--error, #ffebee);
        padding: 1rem;
        border-radius: var(--radius-md);
        margin: 1rem 0;
        border-bottom: none;
      }
    }
    .amount { font-size: 1.5rem; font-weight: 700; color: var(--error); }
    .btn-block { width: 100%; padding: 1rem; margin-top: 1rem; }
    .extra-details h3 { font-size: 1rem; margin: 1.25rem 0 0.5rem; }
    .image-grid { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .loading-state { padding: 1rem; }
    .skeleton-line { height: 12px; border-radius: 8px; background: rgba(0,0,0,.08); margin: .7rem 0; }
    .skeleton-line.wide { width: 65%; height: 18px; }
    @media (max-width: 767px) {
      .feature-container { padding: 1rem; }
      .challan-detail { padding: 1rem; }
      h1 { font-size: 1.3rem; margin-bottom: 1rem; }
      .detail-row { flex-direction: column; gap: .25rem; }
      .pay-cta {
        position: sticky;
        bottom: 8px;
        box-shadow: var(--shadow-md);
      }
    }
  `],
})
export class ChallanDetailComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  challanId = '';
  challan: Challan | null = null;
  loading = true;

  ngOnInit() {
    this.route.paramMap.subscribe({
      next: (params) => {
        const nextId = params.get('id') || '';
        if (!nextId) return;
        this.challanId = nextId;
        this.loading = true;
        this.api.getChallan(this.challanId).subscribe({
          next: (data) => {
            this.challan = data;
            this.loading = false;
          },
          error: () => this.loading = false,
        });
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  payChallan() {
    this.router.navigate(['/challan/pay', this.challanId]);
  }

  formatDate(value: Date | string | undefined): string {
    if (!value) return '-';
    const s = String(value).trim();
    // InstantPay often sends DD-MM-YYYY, which Angular date pipe does not parse reliably.
    const m = s.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (m) return `${m[1]}-${m[2]}-${m[3]}`;
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString('en-IN');
  }

  dueCountdown(value: Date | string): string {
    const d = new Date(String(value));
    if (Number.isNaN(d.getTime())) return String(value);
    const diff = Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    if (diff < 0) return `${Math.abs(diff)} day(s) overdue`;
    if (diff === 0) return 'Due today';
    return `${diff} day(s) left`;
  }

  disputeUrl(state: string | undefined): string {
    const st = (state || '').toUpperCase();
    return st ? `https://echallan.parivahan.gov.in/index/accused-challan?state=${encodeURIComponent(st)}` : 'https://echallan.parivahan.gov.in/';
  }
}
