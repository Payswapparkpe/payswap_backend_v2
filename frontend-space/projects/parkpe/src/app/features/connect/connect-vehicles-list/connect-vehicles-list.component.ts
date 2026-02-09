import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ConnectService, ConnectVehicle } from '../services/connect.service';

@Component({
  selector: 'app-connect-vehicles-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-vehicles-list.component.html',
  styleUrl: './connect-vehicles-list.component.scss',
})
export class ConnectVehiclesListComponent implements OnInit {
  private connect = inject(ConnectService);
  vehicles = signal<ConnectVehicle[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  ngOnInit() {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.error.set(null);
    this.connect.getVehicles().subscribe({
      next: (list) => {
        this.vehicles.set(list);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to load vehicles');
        this.loading.set(false);
      },
    });
  }
}
