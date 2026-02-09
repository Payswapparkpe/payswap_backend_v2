import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ConnectService, ConnectVehicleCreate } from '../services/connect.service';

@Component({
  selector: 'app-connect-vehicle-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './connect-vehicle-form.component.html',
  styleUrl: './connect-vehicle-form.component.scss',
})
export class ConnectVehicleFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private connect = inject(ConnectService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  isEdit = signal(false);
  vehicleId = signal<number | null>(null);
  loading = signal(false);
  error = signal<string | null>(null);

  form = this.fb.nonNullable.group({
    registration_number: ['', [Validators.required, Validators.maxLength(32)]],
    brand: [''],
    model: [''],
    year: [null as number | null, []],
    is_primary: [false],
  });

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      const n = parseInt(id, 10);
      if (!isNaN(n)) {
        this.isEdit.set(true);
        this.vehicleId.set(n);
        this.connect.getVehicle(n).subscribe({
          next: (v) => {
            this.form.patchValue({
              registration_number: v.registration_number,
              brand: v.brand || '',
              model: v.model || '',
              year: v.year,
              is_primary: v.is_primary,
            });
          },
          error: () => this.error.set('Vehicle not found'),
        });
      }
    }
  }

  submit() {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    const payload: ConnectVehicleCreate = {
      registration_number: this.form.getRawValue().registration_number.trim(),
      brand: this.form.getRawValue().brand || undefined,
      model: this.form.getRawValue().model || undefined,
      year: this.form.getRawValue().year ?? undefined,
      is_primary: this.form.getRawValue().is_primary,
    };

    const id = this.vehicleId();
    if (this.isEdit() && id != null) {
      this.connect.updateVehicle(id, payload).subscribe({
        next: () => {
          this.loading.set(false);
          this.router.navigate(['/connect/vehicles']);
        },
        error: (err) => {
          this.error.set(err?.error?.detail || 'Update failed');
          this.loading.set(false);
        },
      });
    } else {
      this.connect.createVehicle(payload).subscribe({
        next: (v) => {
          this.loading.set(false);
          this.router.navigate(['/connect/vehicles', v.id]);
        },
        error: (err) => {
          this.error.set(err?.error?.detail || 'Create failed');
          this.loading.set(false);
        },
      });
    }
  }
}
