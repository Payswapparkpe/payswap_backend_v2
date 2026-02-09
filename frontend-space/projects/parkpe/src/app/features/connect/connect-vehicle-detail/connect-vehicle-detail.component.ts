import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ConnectService, ConnectVehicle, VehicleQRResponse } from '../services/connect.service';

@Component({
  selector: 'app-connect-vehicle-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-vehicle-detail.component.html',
  styleUrl: './connect-vehicle-detail.component.scss',
})
export class ConnectVehicleDetailComponent implements OnInit {
  private connect = inject(ConnectService);
  private route = inject(ActivatedRoute);

  vehicle = signal<ConnectVehicle | null>(null);
  qr = signal<VehicleQRResponse | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);

  qrImageUrl = computed(() => {
    const q = this.qr();
    const url = q?.scan_path
      ? `${window.location.origin}${q.scan_path}`
      : q?.scan_url;
    if (!url) return null;
    return `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(url)}`;
  });

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      this.error.set('Invalid vehicle');
      this.loading.set(false);
      return;
    }
    const n = parseInt(id, 10);
    if (isNaN(n)) {
      this.error.set('Invalid vehicle');
      this.loading.set(false);
      return;
    }
    this.connect.getVehicle(n).subscribe({
      next: (v) => {
        this.vehicle.set(v);
        this.connect.getVehicleQr(n).subscribe({
          next: (qrData) => this.qr.set(qrData),
          error: () => {},
        });
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Vehicle not found');
        this.loading.set(false);
      },
    });
  }

}
