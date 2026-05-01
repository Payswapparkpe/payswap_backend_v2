import { Injectable, signal } from '@angular/core';
import { Challan } from '../../../core/models/challan.model';

type SavedState = {
  vehicleNumber: string;
  state?: string;
  challanNumber?: string;
  updatedAt: string;
  items: Challan[];
};

@Injectable({ providedIn: 'root' })
export class ChallanSessionService {
  private readonly key = 'parkpe:challan:last-results:v1';
  results = signal<Challan[]>([]);
  vehicleNumber = signal('');
  challanNumber = signal('');
  state = signal('');
  updatedAt = signal<string | null>(null);

  constructor() {
    this.restore();
  }

  save(params: { vehicleNumber: string; state?: string; challanNumber?: string; items: Challan[] }): void {
    this.vehicleNumber.set(params.vehicleNumber);
    this.state.set(params.state ?? '');
    this.challanNumber.set(params.challanNumber ?? '');
    this.results.set(params.items ?? []);
    const now = new Date().toISOString();
    this.updatedAt.set(now);
    try {
      const payload: SavedState = {
        vehicleNumber: params.vehicleNumber,
        state: params.state,
        challanNumber: params.challanNumber,
        updatedAt: now,
        items: params.items ?? [],
      };
      localStorage.setItem(this.key, JSON.stringify(payload));
    } catch {
      // ignore localStorage issues
    }
  }

  private restore(): void {
    try {
      const raw = localStorage.getItem(this.key);
      if (!raw) return;
      const payload = JSON.parse(raw) as SavedState;
      this.vehicleNumber.set(payload.vehicleNumber ?? '');
      this.state.set(payload.state ?? '');
      this.challanNumber.set(payload.challanNumber ?? '');
      this.results.set(Array.isArray(payload.items) ? payload.items : []);
      this.updatedAt.set(payload.updatedAt ?? null);
    } catch {
      // ignore restore issues
    }
  }
}
