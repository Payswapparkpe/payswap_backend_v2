import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, finalize, of, timeout, TimeoutError } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../core/constants';
import { FleetTripItem, FleetTrendPoint, FleetVehicleItem } from '../../core/api/api-backend.interface';

@Component({
  selector: 'app-fleet-trips',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './fleet-trips.component.html',
  styleUrl: './fleet-trips.component.scss',
})
export class FleetTripsComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);

  loading = false;
  /** Set after first trips API response (success or handled error). */
  tripsLoaded = false;
  /** Trips list error; empty table when set (no fake rows). */
  error: string | null = null;
  trendsError: string | null = null;

  items: FleetTripItem[] = [];
  trendSeries: FleetTrendPoint[] = [];
  total = 0;
  page = 1;
  limit = 10;
  dateFrom = '';
  dateTo = '';

  fleetVehicles: FleetVehicleItem[] = [];
  vehiclesLoading = false;
  vehiclesLoaded = false;

  manualVehicleId: number | null = null;
  manualNotes = '';
  manualSubmitting = false;
  manualSubmitError: string | null = null;
  manualSuccessMessage: string | null = null;

  get totalScans7d(): number {
    return this.trendSeries.reduce((sum, point) => sum + (point.scans || 0), 0);
  }

  get avgCallSuccessRate(): number {
    if (!this.trendSeries.length) return 0;
    const sum = this.trendSeries.reduce((acc, point) => acc + (point.callSuccessRate || 0), 0);
    return Math.round((sum / this.trendSeries.length) * 10) / 10;
  }

  get anomalyTrips(): number {
    return this.items.filter((row) => !row.scannedBy || !row.registrationNumber || !row.ipAddress).length;
  }

  ngOnInit(): void {
    this.loadFleetVehicles();
    this.load();
  }

  loadFleetVehicles(): void {
    this.vehiclesLoading = true;
    this.api
      .getFleetVehicles({ page: 1, limit: 200 })
      .pipe(
        timeout(10000),
        catchError(() => of({ items: [] as FleetVehicleItem[], total: 0, page: 1, limit: 200 })),
        finalize(() => {
          this.vehiclesLoading = false;
          this.vehiclesLoaded = true;
        })
      )
      .subscribe((res) => {
        this.fleetVehicles = res.items ?? [];
      });
  }

  load(): void {
    this.loading = true;
    this.error = null;
    this.trendsError = null;
    this.manualSuccessMessage = null;

    this.api
      .getFleetTrips({
        page: this.page,
        limit: this.limit,
        dateFrom: this.dateFrom || undefined,
        dateTo: this.dateTo || undefined,
      })
      .pipe(
        timeout(8000),
        catchError((err: unknown) => {
          this.error = this.describeTripsHttpError(err);
          this.items = [];
          this.total = 0;
          return of({ items: [] as FleetTripItem[], total: 0, page: this.page, limit: this.limit });
        }),
        finalize(() => {
          this.loading = false;
          this.tripsLoaded = true;
        })
      )
      .subscribe({
        next: (res) => {
          if (!this.error) {
            this.items = res.items ?? [];
            this.total = res.total ?? 0;
          }
        },
      });

    this.api
      .getFleetTrends({ days: 7 })
      .pipe(
        timeout(6000),
        catchError((err: unknown) => {
          this.trendsError = this.describeTrendsHttpError(err);
          return of({ series: [] as FleetTrendPoint[], days: 7 });
        })
      )
      .subscribe((res) => {
        this.trendSeries = res.series?.length ? res.series : [];
      });
  }

  submitManualVisit(): void {
    this.manualSubmitError = null;
    this.manualSuccessMessage = null;
    if (this.manualVehicleId == null) {
      this.manualSubmitError = 'Select a fleet vehicle.';
      return;
    }
    this.manualSubmitting = true;
    const notes = this.manualNotes.trim();
    this.api
      .createFleetTripManual({
        vehicleId: this.manualVehicleId,
        notes: notes || undefined,
      })
      .pipe(
        timeout(8000),
        catchError((err: unknown) => {
          this.manualSubmitError = this.describeManualHttpError(err);
          return of(null);
        }),
        finalize(() => {
          this.manualSubmitting = false;
        })
      )
      .subscribe((created) => {
        if (created) {
          this.manualSuccessMessage = `Visit recorded for ${created.registrationNumber || 'vehicle #' + created.vehicleId}.`;
          this.manualNotes = '';
          this.manualVehicleId = null;
          this.page = 1;
          this.load();
        }
      });
  }

  isManualTrip(item: FleetTripItem): boolean {
    return item.entrySource === 'manual';
  }

  private describeTripsHttpError(err: unknown): string {
    if (err instanceof TimeoutError) {
      return 'Trips request timed out. Check your network and API, then retry.';
    }
    if (err instanceof HttpErrorResponse) {
      if (err.status === 401 || err.status === 403) {
        return 'Fleet workspace access required. Ask your admin to approve your fleet role.';
      }
      if (err.status === 0) {
        return 'Cannot reach the API from this browser (network or CORS). Verify API URL and server.';
      }
      const detail = err.error?.detail;
      if (typeof detail === 'string' && detail.trim()) {
        return detail;
      }
    }
    return 'Could not load trips. Try again in a moment.';
  }

  private describeManualHttpError(err: unknown): string {
    if (err instanceof TimeoutError) {
      return 'Request timed out. Try again.';
    }
    if (err instanceof HttpErrorResponse) {
      const detail = err.error?.detail;
      if (typeof detail === 'string' && detail.trim()) {
        return detail;
      }
      if (err.status === 400) {
        return 'Invalid request. Check the selected vehicle is in your fleet.';
      }
    }
    return 'Could not record visit. Try again.';
  }

  private describeTrendsHttpError(err: unknown): string {
    if (err instanceof TimeoutError) {
      return 'Trends request timed out.';
    }
    if (err instanceof HttpErrorResponse && (err.status === 401 || err.status === 403)) {
      return 'Trends unavailable — fleet access required.';
    }
    return 'Could not load trend data.';
  }

  applyFilters(): void {
    this.page = 1;
    this.load();
  }

  clearDateFilters(): void {
    this.dateFrom = '';
    this.dateTo = '';
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

  getTripRisk(item: FleetTripItem): 'normal' | 'watch' | 'critical' {
    if (!item.scannedBy || !item.scannerPhone) return 'critical';
    if (!item.ipAddress) return 'watch';
    return 'normal';
  }
}
