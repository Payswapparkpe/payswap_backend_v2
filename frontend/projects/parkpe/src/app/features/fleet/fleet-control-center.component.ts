import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, finalize, of, timeout } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../core/constants';
import { FleetControlCenterKpi, FleetControlCenterModule } from '../../core/api/api-backend.interface';

@Component({
  selector: 'app-fleet-control-center',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './fleet-control-center.component.html',
  styleUrl: './fleet-control-center.component.scss',
})
export class FleetControlCenterComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private readonly defaultKpis: FleetControlCenterKpi[] = [
    { label: 'Active Vehicles', value: 0, trend: 'live' },
    { label: 'Trips Today', value: 0, trend: 'today' },
    { label: 'On-time Rate', value: '0%', trend: '24h' },
    { label: 'Open Alerts', value: 0, trend: 'live' },
  ];
  private readonly defaultModules: FleetControlCenterModule[] = [
    { title: 'Fleet Ops', description: 'Dispatch board, trip monitoring, and route adherence.', route: '/fleet/trips', cta: 'Open Fleet Ops' },
    { title: 'Vehicles', description: 'Vehicle master, RC health, and uptime readiness.', route: '/fleet/vehicles', cta: 'Manage Vehicles' },
    { title: 'Drivers', description: 'Driver roster, risk behavior, and performance snapshot.', route: '/fleet/drivers', cta: 'Open Driver Hub' },
    { title: 'Compliance & Governance', description: 'Policies, approvals, and operational audit controls.', route: '/fleet/compliance', cta: 'Open Settings' },
  ];
  private readonly defaultAlerts: string[] = ['Fleet dashboard is syncing latest data...'];

  loading = false;
  error: string | null = null;
  kpis: FleetControlCenterKpi[] = [...this.defaultKpis];
  modules: FleetControlCenterModule[] = [...this.defaultModules];
  priorityAlerts: string[] = [...this.defaultAlerts];
  lastSyncedAt: Date | null = null;

  ngOnInit(): void {
    this.loadFleetData();
  }

  refreshNow(): void {
    this.loadFleetData();
  }

  getKpiIcon(label: string): string {
    const key = (label || '').toLowerCase();
    if (key.includes('vehicle')) return 'local_shipping';
    if (key.includes('trip')) return 'route';
    if (key.includes('time')) return 'speed';
    if (key.includes('alert')) return 'warning_amber';
    return 'monitoring';
  }

  getModuleIcon(title: string): string {
    const key = (title || '').toLowerCase();
    if (key.includes('ops')) return 'hub';
    if (key.includes('vehicle')) return 'directions_car';
    if (key.includes('driver')) return 'badge';
    if (key.includes('compliance') || key.includes('governance')) return 'verified_user';
    if (key.includes('payment')) return 'account_balance_wallet';
    if (key.includes('notification')) return 'notifications_active';
    return 'apps';
  }

  loadFleetData(): void {
    this.loading = true;
    this.error = null;
    try {
      this.api
        .getFleetControlCenter()
        .pipe(
          timeout(10000),
          catchError(() => {
            this.error = 'Could not load fleet control center data. Please retry.';
            return of({ kpis: [], modules: [], priorityAlerts: [] });
          }),
          finalize(() => {
            this.loading = false;
          })
        )
        .subscribe((res) => {
          this.kpis = Array.isArray(res?.kpis) && res.kpis.length ? res.kpis : [...this.defaultKpis];
          this.modules = Array.isArray(res?.modules) && res.modules.length ? res.modules : [...this.defaultModules];
          this.priorityAlerts = Array.isArray(res?.priorityAlerts) && res.priorityAlerts.length
            ? res.priorityAlerts
            : [...this.defaultAlerts];
          this.lastSyncedAt = new Date();
        });
    } catch {
      this.error = 'Fleet dashboard service is currently unavailable.';
      this.loading = false;
    }
  }
}
