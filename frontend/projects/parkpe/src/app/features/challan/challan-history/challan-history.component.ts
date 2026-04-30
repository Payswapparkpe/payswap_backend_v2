import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { ChallanHistoryItem } from '../../../core/models/challan.model';

@Component({
  selector: 'app-challan-history',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <h2>Payment History</h2>
      @if (!items.length) {
        <p>No challan payments yet.</p>
      } @else {
        <div class="list">
          @for (row of items; track row.id) {
            <div class="card row">
              <div>
                <strong>{{ row.challanNumber }}</strong> · {{ row.vehicleNumber }}
                <p>{{ row.transactionId }}</p>
              </div>
              <div>
                <p>₹{{ row.amount }}</p>
                @if (row.status === 'success') {
                  <a [routerLink]="['/challan/receipt', row.challanId]">Receipt</a>
                }
              </div>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`.row{display:flex;justify-content:space-between;align-items:center;padding:1rem}.list{display:flex;flex-direction:column;gap:.75rem}`],
})
export class ChallanHistoryComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  items: ChallanHistoryItem[] = [];

  ngOnInit(): void {
    this.api.getChallanHistory({ limit: 50 }).subscribe({
      next: (res) => (this.items = res.items || []),
    });
  }
}
