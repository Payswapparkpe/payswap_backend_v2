import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, finalize, of, timeout } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../core/constants';
import { AuthService } from '../../core/services/auth.service';
import { FleetRosterDriverItem, FleetVehicleItem } from '../../core/api/api-backend.interface';

@Component({
  selector: 'app-fleet-vehicles',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './fleet-vehicles.component.html',
  styleUrl: './fleet-vehicles.component.scss',
})
export class FleetVehiclesComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private auth = inject(AuthService);

  readonly maxModelYear = new Date().getFullYear() + 1;

  loading = false;
  error: string | null = null;
  items: FleetVehicleItem[] = [];
  total = 0;
  page = 1;
  limit = 10;
  search = '';
  vehicleType = '';

  canDelegateToDrivers = false;
  rosterDrivers: FleetRosterDriverItem[] = [];

  showAddDialog = false;
  addSubmitting = false;
  addError: string | null = null;
  /** null = register under own account; otherwise roster driver user id */
  addOwnerUserId: number | null = null;
  addForm = {
    registrationNumber: '',
    vehicleType: 'commercial',
    brand: '',
    model: '',
    year: '' as number | '' | null,
    acceptOwnershipDeclaration: false,
  };

  rosterUsername = '';
  rosterPhone = '';
  rosterSubmitting = false;
  rosterError: string | null = null;

  /** Logged-in ParkPe user id (string in client model; compare loosely to API numbers). */
  get currentUserIdStr(): string | null {
    return this.auth.userSignal()?.id ?? null;
  }

  get compliantVehicles(): number {
    return this.items.filter((item) => item.complianceState === 'compliant').length;
  }

  get criticalVehicles(): number {
    return this.items.filter((item) => ['expired', 'missing_rc'].includes(item.complianceState)).length;
  }

  get avgHealthIndex(): number {
    if (!this.items.length) return 0;
    const total = this.items.reduce((sum, item) => sum + this.getHealthIndex(item), 0);
    return Math.round(total / this.items.length);
  }

  get predictiveMaintenanceCount(): number {
    return this.items.filter((item) => item.calls24h >= 6 || item.scans24h >= 20).length;
  }

  ngOnInit(): void {
    this.load();
  }

  ownerLabel(item: FleetVehicleItem): string {
    if (!this.canDelegateToDrivers) return '—';
    const uid = item.ownerUserId;
    if (uid == null) return '—';
    if (this.currentUserIdStr != null && String(uid) === this.currentUserIdStr) return 'You (fleet account)';
    const d = this.rosterDrivers.find((r) => r.userId === uid);
    return d ? `${d.name}` : `User #${uid}`;
  }

  load(): void {
    this.loading = true;
    this.error = null;
    this.api
      .getFleetVehicles({
        page: this.page,
        limit: this.limit,
        search: this.search.trim() || undefined,
        vehicleType: this.vehicleType || undefined,
      })
      .pipe(
        timeout(8000),
        catchError(() => {
          this.error = 'Could not load fleet vehicles. Check your connection and try again.';
          return of({
            items: [] as FleetVehicleItem[],
            total: 0,
            page: this.page,
            limit: this.limit,
            canDelegateToDrivers: false,
            rosterDrivers: [] as FleetRosterDriverItem[],
          });
        }),
        finalize(() => {
          this.loading = false;
        })
      )
      .subscribe({
        next: (res) => {
          this.items = res.items || [];
          this.total = res.total ?? 0;
          this.canDelegateToDrivers = !!res.canDelegateToDrivers;
          this.rosterDrivers = res.rosterDrivers ?? [];
        },
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

  openAdd(): void {
    this.addError = null;
    this.addOwnerUserId = null;
    this.addForm = {
      registrationNumber: '',
      vehicleType: 'commercial',
      brand: '',
      model: '',
      year: '',
      acceptOwnershipDeclaration: false,
    };
    this.showAddDialog = true;
  }

  closeAdd(): void {
    if (this.addSubmitting) return;
    this.showAddDialog = false;
  }

  submitAdd(): void {
    const reg = this.addForm.registrationNumber.trim();
    if (!reg) {
      this.addError = 'Enter the registration number.';
      return;
    }
    if (!this.addForm.acceptOwnershipDeclaration) {
      this.addError = 'You must confirm that you are authorised to register this vehicle.';
      return;
    }
    const yearVal = this.addForm.year;
    let yearNum: number | null = null;
    if (yearVal !== '' && yearVal != null) {
      const n = Number(yearVal);
      if (!Number.isFinite(n) || n < 1950 || n > new Date().getFullYear() + 1) {
        this.addError = 'Enter a valid model year, or leave it blank.';
        return;
      }
      yearNum = Math.floor(n);
    }

    this.addSubmitting = true;
    this.addError = null;
    const payload = {
      vehicleType: this.addForm.vehicleType,
      registrationNumber: reg,
      brand: this.addForm.brand,
      model: this.addForm.model,
      year: yearNum,
      acceptOwnershipDeclaration: true,
      ownerUserId:
        this.canDelegateToDrivers && this.addOwnerUserId != null ? this.addOwnerUserId : undefined,
    };

    this.api
      .createFleetVehicle(payload)
      .pipe(
        finalize(() => {
          this.addSubmitting = false;
        })
      )
      .subscribe({
        next: () => {
          this.showAddDialog = false;
          this.page = 1;
          this.load();
        },
        error: (err: unknown) => {
          if (err instanceof HttpErrorResponse) {
            const body = err.error as { detail?: string; non_field_errors?: string[] } | null;
            const d = body?.detail ?? body?.non_field_errors?.[0];
            this.addError = typeof d === 'string' ? d : 'Could not add vehicle. Try again.';
          } else {
            this.addError = 'Could not add vehicle. Try again.';
          }
        },
      });
  }

  submitRosterLink(): void {
    this.rosterError = null;
    const u = this.rosterUsername.trim();
    const p = this.rosterPhone.trim();
    const filled = (u ? 1 : 0) + (p ? 1 : 0);
    if (filled !== 1) {
      this.rosterError = 'Enter exactly one of username or phone.';
      return;
    }
    this.rosterSubmitting = true;
    this.api
      .linkFleetRosterDriver(u ? { username: u } : { phone: p })
      .pipe(
        finalize(() => {
          this.rosterSubmitting = false;
        })
      )
      .subscribe({
        next: () => {
          this.rosterUsername = '';
          this.rosterPhone = '';
          this.page = 1;
          this.load();
        },
        error: (err: unknown) => {
          if (err instanceof HttpErrorResponse) {
            const body = err.error as { detail?: string } | null;
            const d = body?.detail;
            this.rosterError = typeof d === 'string' ? d : 'Could not add driver.';
          } else {
            this.rosterError = 'Could not add driver.';
          }
        },
      });
  }

  removeRosterDriver(userId: number): void {
    this.rosterError = null;
    this.rosterSubmitting = true;
    this.api
      .unlinkFleetRosterDriver(userId)
      .pipe(
        finalize(() => {
          this.rosterSubmitting = false;
        })
      )
      .subscribe({
        next: () => {
          this.page = 1;
          this.load();
        },
        error: (err: unknown) => {
          if (err instanceof HttpErrorResponse) {
            const body = err.error as { detail?: string } | null;
            const d = body?.detail;
            this.rosterError = typeof d === 'string' ? d : 'Could not remove driver.';
          } else {
            this.rosterError = 'Could not remove driver.';
          }
        },
      });
  }

  getHealthIndex(item: FleetVehicleItem): number {
    let score = 100;
    if (item.complianceState === 'expiring') score -= 12;
    if (item.complianceState === 'expired') score -= 35;
    if (item.complianceState === 'missing_rc') score -= 45;
    if (item.calls24h >= 8) score -= 10;
    if (item.scans24h >= 25) score -= 8;
    return Math.max(20, Math.min(100, score));
  }

  getHealthBand(score: number): 'good' | 'watch' | 'critical' {
    if (score >= 80) return 'good';
    if (score >= 60) return 'watch';
    return 'critical';
  }

  getRecommendation(item: FleetVehicleItem): string {
    if (item.complianceState === 'expired') return 'Immediate compliance intervention';
    if (item.complianceState === 'missing_rc') return 'RC document onboarding required';
    if (item.complianceState === 'expiring') return 'Renewal workflow in next 7-15 days';
    if (item.calls24h >= 8) return 'Investigate high distress call volume';
    return 'Stable operational profile';
  }
}
