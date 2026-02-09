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
        <div class="loading-state"><div class="spinner"></div></div>
      } @else if (challan) {
        <div class="challan-detail card">
          <h1>Challan Details</h1>
          <div class="detail-row"><span>Challan Number:</span><span>{{ challan.challanNumber }}</span></div>
          <div class="detail-row"><span>Vehicle:</span><span>{{ challan.vehicleNumber }}</span></div>
          <div class="detail-row"><span>Offence:</span><span>{{ challan.offence }}</span></div>
          <div class="detail-row"><span>Date:</span><span>{{ challan.offenceDate | date }}</span></div>
          <div class="detail-row"><span>Location:</span><span>{{ challan.location }}</span></div>
          <div class="detail-row highlight">
            <span>Total Amount:</span><span class="amount">₹{{ challan.totalAmount }}</span>
          </div>
          
          @if (challan.status === 'pending') {
            <button class="btn btn-primary btn-block" (click)="payChallan()">
              Pay ₹{{ challan.totalAmount }}
            </button>
          }
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
    .challan-detail { padding: 2rem; }
    h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 1.5rem; }
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
    this.challanId = this.route.snapshot.params['id'];
    this.api.getChallan(this.challanId).subscribe({
      next: (data) => {
        this.challan = data;
        this.loading = false;
      },
      error: () => this.loading = false,
    });
  }

  payChallan() {
    this.router.navigate(['/challan/pay', this.challanId]);
  }
}
