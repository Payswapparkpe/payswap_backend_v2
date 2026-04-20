import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-fleet-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './fleet-login.component.html',
  styleUrl: './fleet-login.component.scss',
})
export class FleetLoginComponent {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private notification = inject(NotificationService);
  private router = inject(Router);

  loading = false;
  form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
  });

  onSubmit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    this.loading = true;
    this.authService
      .fleetLogin({
        email: String(this.form.value.email || '').trim(),
        password: String(this.form.value.password || ''),
      })
      .subscribe({
        next: () => {
          this.loading = false;
          this.notification.showSuccess('Fleet login successful.');
          this.router.navigate(['/fleet/control-center']);
        },
        error: (err) => {
          this.loading = false;
          const msg = err?.error?.detail || err?.error?.message || 'Fleet login failed.';
          this.notification.showError(msg);
        },
      });
  }
}
