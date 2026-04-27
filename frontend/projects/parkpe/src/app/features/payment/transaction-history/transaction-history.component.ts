import { Component, inject, input, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { Transaction } from 'shared';

const TXN_TYPE_LABELS: Record<string, string> = {
  bbps: 'BBPS',
  voucher_purchase: 'Voucher Purchase',
  rc_view: 'RC Data',
  fastag: 'FASTag',
  parking: 'Parking',
  challan: 'Challan',
  rollback: 'Rollback',
  other: 'Other',
};

@Component({
  selector: 'app-transaction-history',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './transaction-history.component.html',
  styleUrl: './transaction-history.component.scss',
})
export class TransactionHistoryComponent implements OnInit {
  private paymentService = inject(PaymentGatewayService);
  private cdr = inject(ChangeDetectorRef);

  embedded = input<boolean>(false);
  transactions: Transaction[] = [];
  total = 0;
  page = 1;
  pageSize = 20;
  loading = true;
  loadError = false;
  filterType = '';
  filterStatus = '';
  filterDateFrom = '';
  filterDateTo = '';

  get startRow(): number {
    return this.total === 0 ? 0 : (this.page - 1) * this.pageSize + 1;
  }
  get endRow(): number {
    return Math.min(this.page * this.pageSize, this.total);
  }

  /** Human-readable label for transaction type (e.g. rc_view → "RC Data"). */
  txnTypeLabel(type: string): string {
    return TXN_TYPE_LABELS[type?.toLowerCase()] ?? (type ? type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : '—');
  }

  /** Credit/Debit column: Refund for BBPS rollback rows when API sends creditDebitLabel. */
  creditDebitDisplay(txn: Transaction): string {
    if (txn.creditDebitLabel?.trim()) {
      return txn.creditDebitLabel.trim();
    }
    const d = txn.transactionTypeDirection;
    if (!d) {
      return '—';
    }
    return d.charAt(0).toUpperCase() + d.slice(1).toLowerCase();
  }

  ngOnInit() {
    this.load();
  }

  load() {
    this.loading = true;
    const params: {
      page: number;
      limit: number;
      type?: string;
      status?: string;
      dateFrom?: string;
      dateTo?: string;
    } = {
      page: this.page,
      limit: this.pageSize,
    };
    if (this.filterType) params.type = this.filterType;
    if (this.filterStatus) params.status = this.filterStatus;
    if (this.filterDateFrom) params.dateFrom = this.filterDateFrom;
    if (this.filterDateTo) params.dateTo = this.filterDateTo;
    this.loadError = false;
    this.paymentService.getTransactionHistory(params).subscribe({
      next: (data) => {
        this.transactions = data.transactions ?? [];
        this.total = data.total ?? 0;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.loading = false;
        this.loadError = true;
        this.cdr.markForCheck();
      },
    });
  }

  onFilterChange(key: string, value: string) {
    if (key === 'type') this.filterType = value;
    if (key === 'status') this.filterStatus = value;
    this.page = 1;
    this.load();
  }

  onDateChange() {
    this.page = 1;
    this.load();
  }

  clearDates() {
    this.filterDateFrom = '';
    this.filterDateTo = '';
    this.page = 1;
    this.load();
  }

  goPage(delta: number) {
    this.page = this.page + delta;
    this.load();
  }

  receiptLink(txn: Transaction): string[] {
    return ['/payment/receipt', txn.transactionId];
  }
}
