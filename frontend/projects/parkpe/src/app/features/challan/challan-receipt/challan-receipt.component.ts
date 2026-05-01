import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { ChallanReceipt } from '../../../core/models/challan.model';

@Component({
  selector: 'app-challan-receipt',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <a routerLink="/challan/history" class="back-link">Back to History</a>
      <h1>Challan Receipt</h1>
      @if (receipt) {
        <div class="card">
          <p><strong>Receipt Number:</strong> {{ receipt.receiptNumber }}</p>
          <p><strong>Transaction ID:</strong> {{ receipt.transactionId }}</p>
          <p><strong>Challan:</strong> {{ receipt.challanNumber }}</p>
          <p><strong>Vehicle:</strong> {{ receipt.vehicleNumber }}</p>
          <p><strong>Amount:</strong> ₹{{ receipt.amount }}</p>
          <button class="btn btn-primary" (click)="download()">Download PDF</button>
        </div>
      }
    </div>
  `,
})
export class ChallanReceiptComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private route = inject(ActivatedRoute);
  challanId = '';
  receipt: ChallanReceipt | null = null;

  ngOnInit(): void {
    this.challanId = this.route.snapshot.params['id'];
    this.api.getChallanReceipt(this.challanId).subscribe({ next: (r) => (this.receipt = r) });
  }

  download(): void {
    this.api.downloadChallanReceipt(this.challanId).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `challan-receipt-${this.receipt?.challanNumber || this.challanId}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      },
    });
  }
}
