import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-parking-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './parking-login.component.html',
  styleUrl: './parking-login.component.scss',
})
export class ParkingLoginComponent {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private notification = inject(NotificationService);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  loading = false;
  showPassword = false;
  errorMsg = '';

  form = this.fb.group({
    email: ['', [Validators.required]],
    password: ['', [Validators.required, Validators.minLength(6)]],
  });

  readonly features = [
    { icon: '📍', label: 'Live Slot Map' },
    { icon: '📷', label: 'QR Scanner' },
    { icon: '💳', label: 'UPI & Voucher Pay' },
    { icon: '📊', label: 'Revenue Analytics' },
    { icon: '🔔', label: 'Real-time Alerts' },
    { icon: '🔐', label: 'HMAC-secured QR' },
  ];

  onSubmit(): void {
    this.form.markAllAsTouched();
    this.errorMsg = '';
    if (this.form.invalid) return;
    this.loading = true;
    this.authService
      .parkingLogin({
        email: String(this.form.value.email || '').trim(),
        password: String(this.form.value.password || ''),
      })
      .subscribe({
        next: () => {
          this.loading = false;
          this.notification.showSuccess('Welcome to Parking Hub!');
          this.router.navigate(['/hub/parking/dashboard']);
        },
        error: (err) => {
          this.loading = false;
          const msg =
            err?.error?.detail ||
            err?.error?.message ||
            'Login failed. Check your credentials and try again.';
          // Avoid NG0100 in dev mode when auth errors resolve during same change cycle.
          setTimeout(() => {
            this.errorMsg = msg;
            this.cdr.detectChanges();
          }, 0);
        },
      });
  }
}
