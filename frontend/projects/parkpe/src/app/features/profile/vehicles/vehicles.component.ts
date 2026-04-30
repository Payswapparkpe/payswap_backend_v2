import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { ApiBackend } from '../../../core/api/api-backend.interface';
import { SavedVehicle } from '../../../core/models/challan.model';
import { VehicleFastagMapping } from '../../../core/models/parking.model';
import { ParkingService } from '../../parking/services/parking.service';

@Component({
  selector: 'app-profile-vehicles',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './vehicles.component.html',
  styleUrl: './vehicles.component.scss',
})
export class VehiclesComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN) as ApiBackend;
  private parking = inject(ParkingService);

  loading = signal(true);
  error = signal('');
  rows = signal<{ vehicle: SavedVehicle; mapping?: VehicleFastagMapping }[]>([]);

  ngOnInit(): void {
    forkJoin({
      saved: this.api.getSavedVehicles(),
      fastag: this.parking.getFastagMappings(),
    }).subscribe({
      next: ({ saved, fastag }) => {
        const maps = new Map(
          fastag.mappings.map((m) => [m.vehicleNumber.toUpperCase().replace(/\s/g, ''), m])
        );
        this.rows.set(
          saved.map((v) => ({
            vehicle: v,
            mapping: maps.get(v.registrationNumber.toUpperCase().replace(/\s/g, '')),
          }))
        );
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not load vehicles.');
        this.loading.set(false);
      },
    });
  }

  chipLabel(mapping?: VehicleFastagMapping): string {
    if (!mapping) return 'Not linked';
    if (!mapping.isActive) return 'Inactive';
    if (mapping.isVerified) return 'Linked';
    return 'Pending';
  }

  chipClass(mapping?: VehicleFastagMapping): string {
    if (!mapping) return 'chip-warn';
    if (!mapping.isActive) return 'chip-muted';
    if (mapping.isVerified) return 'chip-ok';
    return 'chip-warn';
  }
}
