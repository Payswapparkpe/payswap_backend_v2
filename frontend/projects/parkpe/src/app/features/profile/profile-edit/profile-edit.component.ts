import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-profile-edit',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="profile-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="profile-title">Edit Profile</h1>

      <form [formGroup]="profileForm" (ngSubmit)="onSubmit()" class="profile-form card">
        <div class="form-group">
          <label for="profile-name">Name</label>
          <input
            id="profile-name"
            type="text"
            formControlName="name"
            class="form-control"
            [class.error]="nameControl?.invalid && nameControl?.touched"
            [attr.aria-invalid]="nameControl?.invalid && nameControl?.touched"
            aria-describedby="name-error"
            placeholder="Your full name"
          />
          @if (nameControl?.invalid && nameControl?.touched) {
            <span id="name-error" class="error-message" role="alert">Name is required</span>
          }
        </div>

        <div class="form-group">
          <label for="profile-email">Email</label>
          <input
            id="profile-email"
            type="email"
            formControlName="email"
            class="form-control"
            [disabled]="true"
          />
          <p class="form-hint">Email cannot be changed</p>
        </div>

        <div class="form-group">
          <label for="profile-phone">Phone</label>
          <input
            id="profile-phone"
            type="tel"
            formControlName="phone"
            class="form-control"
            [class.error]="phoneControl?.invalid && phoneControl?.touched"
            [attr.aria-invalid]="phoneControl?.invalid && phoneControl?.touched"
            aria-describedby="phone-error"
            placeholder="10-digit mobile number"
          />
          @if (phoneControl?.invalid && phoneControl?.touched) {
            <span id="phone-error" class="error-message" role="alert">Phone is required</span>
          }
        </div>

        <div class="form-actions">
          <button type="button" class="btn btn-outline" (click)="cancel()">Cancel</button>
          <button type="submit" class="btn btn-primary" [disabled]="loading">
            @if (loading) {
              <span class="spinner"></span> Saving...
            } @else {
              Save Changes
            }
          </button>
        </div>
      </form>
    </div>
  `,
  styles: [`
    .profile-container { padding: 2rem; max-width: 700px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1.5rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .profile-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .profile-form { padding: 2rem; }
    .form-group { margin-bottom: 1.5rem; }
    .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
    .form-control {
      width: 100%;
      padding: 0.75rem 1rem;
      border: 2px solid var(--border-light);
      border-radius: var(--radius-md);
      font-size: 1rem;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;

      &:focus {
        outline: none;
        border-color: var(--primary-500);
        box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
      }
      &.error { border-color: var(--error); }
      &:disabled { background: var(--surface); cursor: not-allowed; }
    }
    .error-message {
      color: var(--error);
      font-size: 0.875rem;
      margin-top: 0.25rem;
      display: block;
    }
    .form-hint { font-size: 0.875rem; color: var(--text-secondary); margin-top: 0.5rem; }
    .form-actions {
      display: flex;
      gap: 1rem;
      justify-content: flex-end;
      margin-top: 2rem;
      flex-wrap: wrap;
    }
  `],
})
export class ProfileEditComponent implements OnInit {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private router = inject(Router);
  private notification = inject(NotificationService);

  profileForm!: FormGroup;
  loading = false;

  get nameControl() {
    return this.profileForm?.get('name');
  }
  get phoneControl() {
    return this.profileForm?.get('phone');
  }

  ngOnInit() {
    this.authService.getProfile().subscribe({
      next: (user) => {
        this.profileForm = this.fb.group({
          name: [user.name, Validators.required],
          email: [{ value: user.email, disabled: true }],
          phone: [user.phone, Validators.required],
        });
      },
    });
  }

  onSubmit() {
    if (this.profileForm.invalid) {
      this.profileForm.markAllAsTouched();
      return;
    }

    this.loading = true;
    const { name, phone } = this.profileForm.getRawValue();
    this.authService.updateProfile({ name, phone }).subscribe({
      next: () => {
        this.loading = false;
        this.notification.showSuccess('Profile updated successfully!');
        this.router.navigate(['/profile/view']);
      },
      error: (err) => {
        this.loading = false;
        const msg = err?.error?.detail || 'Failed to update profile. Please try again.';
        this.notification.showError(msg);
      },
    });
  }

  cancel() {
    this.router.navigate(['/profile/view']);
  }
}
