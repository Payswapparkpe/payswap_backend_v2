import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../core/constants';
import type { FleetInterestStatus } from '../../core/api/api-backend.interface';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-fleet-interest',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './fleet-interest.component.html',
  styleUrl: './fleet-interest.component.scss',
})
export class FleetInterestComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private auth = inject(AuthService);
  private notify = inject(NotificationService);
  private router = inject(Router);
  private fb = inject(FormBuilder);

  loading = signal(true);
  submitting = signal(false);
  status = signal<FleetInterestStatus | null>(null);

  form = this.fb.group({
    companyName: ['', [Validators.maxLength(200)]],
    message: ['', [Validators.maxLength(2000)]],
  });

  ngOnInit(): void {
    this.loadStatus();
  }

  loadStatus(): void {
    this.loading.set(true);
    this.api.getFleetInterestStatus().subscribe({
      next: (s) => {
        this.status.set(s);
        this.loading.set(false);
        if (s.status === 'approved') {
          void this.auth.getProfile().subscribe({
            error: () => {},
          });
        }
      },
      error: () => {
        this.loading.set(false);
        this.notify.showError('Could not load fleet interest status.');
      },
    });
  }

  submit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    this.submitting.set(true);
    this.api
      .submitFleetInterest({
        companyName: String(this.form.value.companyName || '').trim(),
        message: String(this.form.value.message || '').trim(),
      })
      .subscribe({
        next: () => {
          this.submitting.set(false);
          this.notify.showSuccess('Request submitted. Our team will review it shortly.');
          this.loadStatus();
        },
        error: (err: { error?: { detail?: string } }) => {
          this.submitting.set(false);
          this.notify.showError(err?.error?.detail || 'Could not submit request.');
        },
      });
  }

  goFleetHome(): void {
    this.auth.getProfile().subscribe({
      next: () => {
        void this.router.navigate(['/fleet/control-center']);
      },
      error: () => {
        this.notify.showWarning('Profile refresh failed. Sign out and sign in again to use Fleet.');
      },
    });
  }
}
