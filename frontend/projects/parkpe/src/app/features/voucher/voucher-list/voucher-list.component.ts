import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { VoucherService } from '../services/voucher.service';
import type { VoucherListItem } from '../../../core/models/voucher.model';

@Component({
  selector: 'app-voucher-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="feature-title">My Vouchers</h1>
      <p class="feature-subtitle">Vouchers you have purchased. Tap to view details and PIN.</p>

      @if (loading) {
        <div class="loading-state"><div class="spinner"></div></div>
      } @else if (vouchers.length === 0) {
        <div class="empty-state card">
          <span class="material-icons">card_giftcard</span>
          <h3>No Vouchers Yet</h3>
          <p>Buy a voucher to pay bills (e.g. BBPS) without Card/UPI.</p>
          <a routerLink="/payment/buy-voucher" class="btn btn-primary">Buy Voucher</a>
        </div>
      } @else {
        <div class="vouchers-grid">
          @for (v of vouchers; track v.id) {
            <a [routerLink]="['/vouchers', v.id]" class="voucher-card card">
              <div class="voucher-header">
                <span class="voucher-code">{{ v.voucherCode }}</span>
                <span class="status-badge" [class]="v.status.toLowerCase()">{{ v.status | titlecase }}</span>
              </div>
              <div class="voucher-amounts">
                <div class="amount-row">
                  <span class="label">Balance</span>
                  <span class="value highlight">₹{{ v.currentBalance }}</span>
                </div>
                <div class="amount-row">
                  <span class="label">Original</span>
                  <span class="value">₹{{ v.originalAmount }}</span>
                </div>
              </div>
              <p class="voucher-date">{{ v.issuedAt | date:'mediumDate' }}</p>
              @if (v.linkedUserPhone) {
                <p class="voucher-linked">Linked: {{ v.linkedUserPhone }}</p>
              } @else if (v.parkpeLinked === false) {
                <p class="voucher-linked not-linked">Not linked</p>
              }
              <span class="material-icons chevron">chevron_right</span>
            </a>
          }
        </div>
        @if (total > vouchers.length) {
          <p class="pagination-hint">Showing {{ vouchers.length }} of {{ total }}</p>
        }
      }

      <div class="actions-footer">
        <a routerLink="/payment/buy-voucher" class="btn btn-primary">Buy New Voucher</a>
      </div>
    </div>
  `,
  styles: [`
    .feature-container { padding: 1rem; max-width: 960px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .feature-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.5rem; }
    .feature-subtitle { color: var(--text-secondary); margin-bottom: 1.5rem; font-size: 0.9375rem; }
    .loading-state { display: flex; justify-content: center; padding: 3rem; }
    .spinner { width: 40px; height: 40px; border: 3px solid var(--border-light); border-top-color: var(--primary-500); border-radius: 50%; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .empty-state { text-align: center; padding: 2rem 1rem; }
    .empty-state .material-icons { font-size: 64px; color: var(--text-muted); margin-bottom: 1rem; }
    .empty-state h3 { margin-bottom: 0.5rem; }
    .empty-state p { color: var(--text-secondary); margin-bottom: 1.5rem; }
    .vouchers-grid { display: grid; grid-template-columns: 1fr; gap: 1rem; }
    @media (min-width: 640px) { .vouchers-grid { grid-template-columns: repeat(2, 1fr); } }
    .voucher-card {
      display: block; text-decoration: none; color: inherit; padding: 1.25rem; position: relative;
      transition: box-shadow 0.2s, transform 0.2s;
    }
    .voucher-card:hover { box-shadow: 0 8px 24px rgba(0,0,0,0.08); transform: translateY(-2px); }
    .voucher-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
    .voucher-code { font-family: monospace; font-size: 1rem; font-weight: 600; }
    .status-badge {
      padding: 0.25rem 0.75rem; border-radius: var(--radius-full); font-size: 0.75rem; font-weight: 600;
    }
    .status-badge.active { background: var(--success); color: white; }
    .status-badge.partially_redeemed { background: var(--warning); color: #1a1a1a; }
    .status-badge.fully_redeemed { background: var(--text-muted); color: white; }
    .voucher-amounts { margin-bottom: 0.75rem; }
    .amount-row { display: flex; justify-content: space-between; padding: 0.25rem 0; }
    .amount-row .label { color: var(--text-secondary); font-size: 0.875rem; }
    .amount-row .value.highlight { font-weight: 700; color: var(--primary-700); font-size: 1.25rem; }
    .voucher-date { font-size: 0.8125rem; color: var(--text-muted); margin: 0; }
    .voucher-linked { font-size: 0.72rem; color: var(--text-secondary); margin: 0.35rem 0 0; }
    .voucher-linked.not-linked { color: var(--text-muted); }
    .chevron { position: absolute; right: 1rem; bottom: 1rem; color: var(--text-muted); font-size: 24px; }
    .pagination-hint { font-size: 0.875rem; color: var(--text-muted); margin-top: 1rem; }
    .actions-footer { margin-top: 2rem; }
  `],
})
export class VoucherListComponent implements OnInit {
  private voucherService = inject(VoucherService);

  vouchers: VoucherListItem[] = [];
  total = 0;
  loading = true;

  ngOnInit() {
    this.voucherService.getVouchers({ limit: 50 }).subscribe({
      next: (res) => {
        this.vouchers = res.vouchers ?? [];
        this.total = res.total ?? 0;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }
}
