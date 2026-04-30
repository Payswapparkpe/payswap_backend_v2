import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { createActor } from 'xstate';
import { API_BACKEND_TOKEN } from '../../../../core/constants';
import { ApiBackend } from '../../../../core/api/api-backend.interface';
import { SavedVehicle } from '../../../../core/models/challan.model';
import { ParkingService } from '../../../parking/services/parking.service';
import { fastagLinkMachine } from '../../../../core/machines/fastag-link.machine';

@Component({
  selector: 'app-fastag-link',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './fastag-link.component.html',
  styleUrl: './fastag-link.component.scss',
})
export class FastagLinkComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private api = inject(API_BACKEND_TOKEN) as ApiBackend;
  private parking = inject(ParkingService);

  vehicle = signal<SavedVehicle | null>(null);
  fastagId = '';
  issuer = 'npci';
  walletId = '';
  loading = signal(true);
  saving = signal(false);
  message = signal('');
  error = signal('');

  private actor = createActor(fastagLinkMachine).start();

  ngOnInit(): void {
    const vid = this.route.snapshot.paramMap.get('vehicleId');
    if (!vid) return;
    this.api.getSavedVehicles().subscribe({
      next: (list) => {
        const v = list.find((x) => String(x.id) === vid) ?? null;
        this.vehicle.set(v);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not load vehicle.');
        this.loading.set(false);
      },
    });
  }

  submit(): void {
    const v = this.vehicle();
    if (!v || !this.fastagId.trim()) return;
    this.saving.set(true);
    this.message.set('');
    this.error.set('');
    this.actor.send({
      type: 'SUBMIT',
      fastagId: this.fastagId.trim(),
      issuer: this.issuer,
      vehicleId: String(v.id),
    });

    this.parking
      .linkFastag({
        vehicleNumber: v.registrationNumber,
        fastagId: this.fastagId.trim(),
        issuer: this.issuer,
        fastagWalletId: this.walletId.trim() || undefined,
      })
      .subscribe({
        next: () => {
          this.actor.send({ type: 'VERIFY_SUCCESS' });
          this.saving.set(false);
          this.message.set('FASTag linked successfully.');
        },
        error: (e: { error?: { detail?: string } }) => {
          this.actor.send({ type: 'VERIFY_FAILED', reason: e?.error?.detail || 'Link failed' });
          this.saving.set(false);
          this.error.set(e?.error?.detail || 'Could not link FASTag.');
        },
      });
  }
}
