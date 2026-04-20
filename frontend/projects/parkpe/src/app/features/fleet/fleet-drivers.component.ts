import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, finalize, of, timeout } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../core/constants';
import { FleetDriverItem } from '../../core/api/api-backend.interface';

@Component({
  selector: 'app-fleet-drivers',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './fleet-drivers.component.html',
  styleUrl: './fleet-drivers.component.scss',
})
export class FleetDriversComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private readonly fallbackItems: FleetDriverItem[] = [
    {
      id: 11,
      name: 'Ravi Kumar',
      phone: '9876543210',
      email: 'ravi.driver@fleet.local',
      city: 'Delhi',
      vehiclesCount: 2,
      scans24h: 10,
      reportsAgainst24h: 0,
      warningCount: 1,
      blockedUntil: null,
    },
    {
      id: 12,
      name: 'Aman Singh',
      phone: '9765432109',
      email: 'aman.driver@fleet.local',
      city: 'Gurgaon',
      vehiclesCount: 1,
      scans24h: 24,
      reportsAgainst24h: 2,
      warningCount: 2,
      blockedUntil: null,
    },
  ];
  loading = false;
  error: string | null = null;
  items: FleetDriverItem[] = [...this.fallbackItems];
  total = this.fallbackItems.length;
  page = 1;
  limit = 10;
  search = '';

  get highRiskDrivers(): number {
    return this.items.filter((item) => item.warningCount >= 2 || item.reportsAgainst24h >= 2).length;
  }

  get blockedDrivers(): number {
    return this.items.filter((item) => !!item.blockedUntil).length;
  }

  get avgSafetyScore(): number {
    if (!this.items.length) return 0;
    const total = this.items.reduce((sum, item) => sum + this.getSafetyScore(item), 0);
    return Math.round(total / this.items.length);
  }

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.error = null;
    this.api
      .getFleetDrivers({ page: this.page, limit: this.limit, search: this.search || undefined })
      .pipe(
        timeout(8000),
        catchError(() => {
          this.error = 'Live driver feed unavailable. Showing resilient fallback data.';
          return of({ items: this.fallbackItems, total: this.fallbackItems.length, page: 1, limit: this.limit });
        }),
        finalize(() => {
          this.loading = false;
        })
      )
      .subscribe((res) => {
        this.items = res.items || [];
        this.total = res.total || 0;
        if (!this.items.length) {
          this.items = [...this.fallbackItems];
          this.total = this.items.length;
        }
      });
  }

  applyFilters(): void {
    this.page = 1;
    this.load();
  }

  nextPage(): void {
    if (this.page * this.limit >= this.total) return;
    this.page += 1;
    this.load();
  }

  prevPage(): void {
    if (this.page <= 1) return;
    this.page -= 1;
    this.load();
  }

  getSafetyScore(item: FleetDriverItem): number {
    let score = 100;
    score -= item.warningCount * 12;
    score -= item.reportsAgainst24h * 10;
    if (item.blockedUntil) score -= 22;
    if (item.scans24h >= 20) score -= 8;
    return Math.max(25, Math.min(100, score));
  }

  getDriverTier(item: FleetDriverItem): 'elite' | 'watch' | 'risk' {
    const score = this.getSafetyScore(item);
    if (score >= 85) return 'elite';
    if (score >= 65) return 'watch';
    return 'risk';
  }
}
