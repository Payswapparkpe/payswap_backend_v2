import { Component, inject, input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ConnectService, ConnectVehicle, ConnectVehiclesMeta } from '../services/connect.service';
import { ConnectVehicleCardComponent } from '../connect-vehicle-card/connect-vehicle-card.component';

@Component({
  selector: 'app-connect-vehicles-list',
  standalone: true,
  imports: [CommonModule, RouterLink, ConnectVehicleCardComponent],
  templateUrl: './connect-vehicles-list.component.html',
  styleUrl: './connect-vehicles-list.component.scss',
})
export class ConnectVehiclesListComponent implements OnInit {
  private connect = inject(ConnectService);
  /** When true, used inside vehicles shell (no back link, fits in left column). */
  embedded = input<boolean>(false);
  vehicles = signal<ConnectVehicle[]>([]);
  meta = signal<ConnectVehiclesMeta | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);

  ngOnInit() {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.error.set(null);
    this.connect.getVehicles().subscribe({
      next: (res) => {
        this.vehicles.set(res.results ?? []);
        this.meta.set(res.meta ?? null);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to load vehicles');
        this.loading.set(false);
      },
    });
  }
}
