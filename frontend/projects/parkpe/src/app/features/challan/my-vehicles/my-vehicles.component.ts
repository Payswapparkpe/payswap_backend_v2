import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { SavedVehicle } from '../../../core/models/challan.model';

@Component({
  selector: 'app-my-vehicles',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="feature-container">
      <h2>My Vehicles</h2>
      <div class="card add-form">
        <input [(ngModel)]="registrationNumber" placeholder="Registration number" />
        <input [(ngModel)]="nickname" placeholder="Nickname (optional)" />
        <label><input type="checkbox" [(ngModel)]="isPrimary" /> Primary</label>
        <button class="btn btn-primary" (click)="add()">Save Vehicle</button>
      </div>
      <div class="list">
        @for (v of vehicles; track v.id) {
          <div class="card row">
            <div>
              <strong>{{ v.registrationNumber }}</strong>
              <p>{{ v.nickname || '-' }}</p>
            </div>
            <div class="actions">
              @if (v.isPrimary) { <span class="badge">Primary</span> }
              <button class="btn btn-outline" (click)="remove(v.id)">Delete</button>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`.add-form{display:grid;gap:.5rem;padding:1rem}.row{display:flex;justify-content:space-between;align-items:center;padding:1rem}.list{display:flex;flex-direction:column;gap:.75rem}.badge{padding:.2rem .5rem;border-radius:999px;background:var(--primary-50);}`],
})
export class MyVehiclesComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  vehicles: SavedVehicle[] = [];
  registrationNumber = '';
  nickname = '';
  isPrimary = false;

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.api.getSavedVehicles().subscribe({ next: (rows) => (this.vehicles = rows || []) });
  }

  add(): void {
    const reg = this.registrationNumber.trim().toUpperCase();
    if (!reg) return;
    this.api.addSavedVehicle({ registrationNumber: reg, nickname: this.nickname.trim(), isPrimary: this.isPrimary }).subscribe({
      next: () => {
        this.registrationNumber = '';
        this.nickname = '';
        this.isPrimary = false;
        this.reload();
      },
    });
  }

  remove(id: number): void {
    this.api.removeSavedVehicle(id).subscribe({ next: () => this.reload() });
  }
}
