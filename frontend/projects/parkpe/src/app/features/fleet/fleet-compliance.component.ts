import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, finalize, of, timeout } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../core/constants';
import { FleetComplianceItem } from '../../core/api/api-backend.interface';

@Component({
  selector: 'app-fleet-compliance',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './fleet-compliance.component.html',
  styleUrl: './fleet-compliance.component.scss',
})
export class FleetComplianceComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private readonly fallbackItems: FleetComplianceItem[] = [
    {
      vehicleId: 1,
      registrationNumber: 'DL01AB4012',
      ownerName: 'Fleet Pilot 1',
      ownerPhone: '9898989898',
      insuranceUpto: '2027-02-15',
      pucUpto: '2026-11-20',
      complianceState: 'compliant',
    },
    {
      vehicleId: 2,
      registrationNumber: 'HR26CD9921',
      ownerName: 'Fleet Pilot 2',
      ownerPhone: '9765432109',
      insuranceUpto: '2026-05-08',
      pucUpto: '2026-04-30',
      complianceState: 'expiring',
    },
  ];
  loading = false;
  error: string | null = null;
  items: FleetComplianceItem[] = [...this.fallbackItems];
  total = this.fallbackItems.length;
  page = 1;
  limit = 10;
  status = '';
  summary = { compliant: 1, expiring: 1, expired: 0, missing_rc: 0 };

  get complianceScore(): number {
    const total = this.summary.compliant + this.summary.expiring + this.summary.expired + this.summary.missing_rc;
    if (!total) return 0;
    const weighted = (this.summary.compliant * 100) + (this.summary.expiring * 70) + (this.summary.expired * 30);
    return Math.round(weighted / total);
  }

  get actionRequired(): number {
    return this.summary.expiring + this.summary.expired + this.summary.missing_rc;
  }

  get expiryRiskBand(): 'good' | 'watch' | 'critical' {
    if (this.actionRequired === 0) return 'good';
    if (this.summary.expired + this.summary.missing_rc > this.summary.compliant) return 'critical';
    return 'watch';
  }

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.error = null;
    this.api
      .getFleetCompliance({ page: this.page, limit: this.limit, status: this.status || undefined })
      .pipe(
        timeout(8000),
        catchError(() => {
          this.error = 'Compliance feed unavailable. Showing resilient fallback data.';
          return of({
            items: this.fallbackItems,
            total: this.fallbackItems.length,
            page: 1,
            limit: this.limit,
            summary: { compliant: 1, expiring: 1, expired: 0, missing_rc: 0 },
          });
        }),
        finalize(() => {
          this.loading = false;
        })
      )
      .subscribe((res) => {
        this.items = res.items || [];
        this.total = res.total || 0;
        this.summary = res.summary || this.summary;
        if (!this.items.length) {
          this.items = [...this.fallbackItems];
          this.total = this.items.length;
          this.summary = { compliant: 1, expiring: 1, expired: 0, missing_rc: 0 };
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
}
