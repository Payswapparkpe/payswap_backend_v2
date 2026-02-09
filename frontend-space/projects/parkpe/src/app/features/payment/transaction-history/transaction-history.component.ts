import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { Transaction } from '../../../core/models/payment.model';

@Component({
  selector: 'app-transaction-history',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  template: `
    <div class="feature-container">
      <div class="feature-header">
        <a routerLink="/dashboard" class="back-link">
          <span class="material-icons">arrow_back</span> Back to Dashboard
        </a>
        <a routerLink="/payment/reports" class="reports-link">Reports</a>
      </div>
      <h1 class="feature-title">Transaction History</h1>
      <p class="feature-subtitle">All your payments and transactions. Use filters to narrow down.</p>

      <div class="filters-bar card">
        <div class="filter-group">
          <label for="filterType">Type</label>
          <select id="filterType" [ngModel]="filterType" (ngModelChange)="onFilterChange('type', $event)">
            <option value="">All</option>
            <option value="bbps">BBPS</option>
            <option value="voucher_purchase">Voucher purchase</option>
            <option value="parking">Parking</option>
            <option value="fastag">FASTag</option>
            <option value="challan">Challan</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div class="filter-group">
          <label for="filterStatus">Status</label>
          <select id="filterStatus" [ngModel]="filterStatus" (ngModelChange)="onFilterChange('status', $event)">
            <option value="">All</option>
            <option value="success">Success</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      @if (loading) {
        <div class="loading-state"><div class="spinner"></div></div>
      } @else if (transactions.length === 0) {
        <div class="empty-state card">
          <span class="material-icons">receipt_long</span>
          <h3>No Transactions</h3>
          <p>You haven't made any payments yet, or no results match your filters.</p>
          <a routerLink="/payment/reports" class="btn btn-outline">View Reports</a>
        </div>
      } @else {
        <div class="transactions-list">
          @for (txn of transactions; track txn.id) {
            <div class="transaction-card card">
              <div class="txn-header">
                <div class="txn-main">
                  <h3>{{ txn.description }}</h3>
                  <p class="txn-date">{{ txn.timestamp | date:'medium' }}</p>
                </div>
                <span class="txn-amount">₹{{ txn.amount }}</span>
              </div>
              <div class="txn-details">
                <span class="txn-type">{{ txn.transactionType | titlecase }}</span>
                <span class="txn-gateway">{{ txn.gateway | titlecase }}</span>
                <span class="txn-status" [class.success]="txn.status === 'success'">
                  {{ txn.status | titlecase }}
                </span>
                <a [routerLink]="['/payment/receipt', txn.transactionId]" class="txn-receipt">View receipt</a>
              </div>
            </div>
          }
        </div>
        @if (total > pageSize) {
          <div class="pagination card">
            <span class="pagination-info">Showing {{ startRow }}–{{ endRow }} of {{ total }}</span>
            <div class="pagination-btns">
              <button type="button" class="btn btn-outline" [disabled]="page <= 1" (click)="goPage(-1)">Previous</button>
              <button type="button" class="btn btn-outline" [disabled]="page * pageSize >= total" (click)="goPage(1)">Next</button>
            </div>
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 1rem; max-width: 900px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .feature-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 1.5rem; }
    .txn-receipt {
      color: var(--primary-600); font-weight: 600; text-decoration: none; font-size: 0.75rem;
    }
    @media (min-width: 768px) {
      .feature-container { padding: 2rem; }
      .feature-title { font-size: 2rem; margin-bottom: 2rem; }
    }
    .empty-state {
      text-align: center;
      padding: 2rem 1rem;
    }
    @media (min-width: 768px) {
      .empty-state { padding: 4rem 2rem; }
    }
    .empty-state .material-icons { font-size: 64px; color: var(--text-muted); margin-bottom: 1rem; }
    @media (min-width: 768px) {
      .empty-state .material-icons { font-size: 80px; }
    }
    .transactions-list { display: flex; flex-direction: column; gap: 1rem; }
    .transaction-card { padding: 1rem; }
    @media (min-width: 768px) {
      .transaction-card { padding: 1.5rem; }
    }
    .txn-header {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      margin-bottom: 1rem;
    }
    @media (min-width: 640px) {
      .txn-header {
        flex-direction: row;
        justify-content: space-between;
        align-items: flex-start;
      }
    }
    .txn-main { flex: 1; min-width: 0; }
    .txn-header h3 { font-size: 1rem; font-weight: 600; word-break: break-word; }
    @media (min-width: 768px) {
      .txn-header h3 { font-size: 1.125rem; }
    }
    .txn-date { font-size: 0.8125rem; color: var(--text-secondary); margin-top: 0.25rem; }
    .txn-amount {
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--primary-700);
      flex-shrink: 0;
    }
    @media (min-width: 768px) {
      .txn-amount { font-size: 1.5rem; }
    }
    .txn-details {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }
    .txn-type, .txn-gateway, .txn-status {
      padding: 0.25rem 0.75rem;
      border-radius: var(--radius-full);
      font-size: 0.75rem;
      font-weight: 600;
      background: var(--surface-dark);
    }
    .txn-status.success { background: var(--success); color: white; }
    .feature-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
    .reports-link { color: var(--primary-600); font-weight: 600; text-decoration: none; font-size: 0.9375rem; }
    .feature-subtitle { color: var(--text-secondary); margin-bottom: 1.5rem; font-size: 0.9375rem; }
    .filters-bar { display: flex; gap: 1rem; flex-wrap: wrap; padding: 1rem; margin-bottom: 1.5rem; }
    .filter-group label { display: block; font-size: 0.75rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 0.25rem; }
    .filter-group select { padding: 0.5rem 0.75rem; border-radius: var(--radius-md); border: 1px solid var(--border-light); min-width: 140px; }
    .pagination { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; padding: 1rem; margin-top: 1.5rem; }
    .pagination-info { font-size: 0.875rem; color: var(--text-secondary); }
    .pagination-btns { display: flex; gap: 0.5rem; }
  `],
})
export class TransactionHistoryComponent implements OnInit {
  private paymentService = inject(PaymentGatewayService);

  transactions: Transaction[] = [];
  total = 0;
  page = 1;
  pageSize = 20;
  loading = true;
  filterType = '';
  filterStatus = '';

  get startRow(): number {
    return this.total === 0 ? 0 : (this.page - 1) * this.pageSize + 1;
  }
  get endRow(): number {
    return Math.min(this.page * this.pageSize, this.total);
  }

  ngOnInit() {
    this.load();
  }

  load() {
    this.loading = true;
    const params: { page: number; limit: number; type?: string; status?: string } = {
      page: this.page,
      limit: this.pageSize,
    };
    if (this.filterType) params.type = this.filterType;
    if (this.filterStatus) params.status = this.filterStatus;
    this.paymentService.getTransactionHistory(params).subscribe({
      next: (data) => {
        this.transactions = data.transactions ?? [];
        this.total = data.total ?? 0;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  onFilterChange(_key: string, _value: string) {
    if (_key === 'type') this.filterType = _value;
    if (_key === 'status') this.filterStatus = _value;
    this.page = 1;
    this.load();
  }

  goPage(delta: number) {
    this.page = this.page + delta;
    this.load();
  }
}
