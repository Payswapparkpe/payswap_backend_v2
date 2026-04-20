import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { User } from 'shared';

@Component({
  selector: 'app-profile-view',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="profile-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>

      @if (loading) {
        <div class="loading-state card">
          <div class="spinner"></div>
          <p>Loading your profile...</p>
        </div>
      } @else if (errorMessage) {
        <div class="error-state card">
          <span class="material-icons">error_outline</span>
          <h2>Could not load profile</h2>
          <p>{{ errorMessage }}</p>
          <button class="btn btn-primary" type="button" (click)="reload()">Try Again</button>
        </div>
      } @else if (user) {
        <section class="profile-hero card">
          <div class="profile-hero__left">
            <div class="avatar" aria-hidden="true">
              <span>{{ userInitials() }}</span>
            </div>
            <div class="profile-meta">
              <h1>{{ displayName() }}</h1>
              <p>{{ displayEmail() }}</p>
              <div class="chip-row">
                <span class="chip">Verified account</span>
                <span class="chip chip--neutral">ParkPe user</span>
              </div>
            </div>
          </div>
          <div class="profile-hero__actions">
            <a class="btn btn-primary" routerLink="/profile/edit">
              <span class="material-icons">edit</span>
              Edit Profile
            </a>
            <a class="btn btn-outline" routerLink="/settings">
              <span class="material-icons">lock</span>
              Security Settings
            </a>
          </div>
        </section>

        <section class="profile-card card">
          <h2 class="section-title">Profile Details</h2>
          <div class="detail-grid">
            <div class="detail-row">
              <span class="label">Full Name</span>
              <span class="value">{{ displayName() }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Email</span>
              <span class="value">{{ displayEmail() }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Phone</span>
              <span class="value">{{ displayPhone() }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Member Since</span>
              <span class="value">{{ user.createdAt ? (user.createdAt | date:'mediumDate') : 'Not available' }}</span>
            </div>
          </div>
        </section>

        <section class="profile-card card profile-footnote">
          <span class="material-icons">info</span>
          <p>Keep your mobile number and PIN up to date for faster OTP recovery and secure unlock.</p>
        </section>
      }
    </div>
  `,
  styles: [`
    .profile-container {
      padding: clamp(1rem, 2vw, 2rem);
      max-width: 980px;
      margin: 0 auto;
      display: grid;
      gap: 1rem;
    }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 600;
    }
    .back-link .material-icons { font-size: 20px; }

    .loading-state,
    .error-state {
      min-height: 220px;
      display: grid;
      place-items: center;
      text-align: center;
      padding: 1.25rem;
      gap: 0.5rem;
    }

    .error-state .material-icons {
      font-size: 2rem;
      color: #dc2626;
    }

    .spinner {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      border: 3px solid rgba(37, 99, 235, 0.2);
      border-top-color: #2563eb;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .profile-hero {
      padding: 1.1rem;
      display: flex;
      justify-content: space-between;
      display: flex;
      align-items: center;
      gap: 1rem;
      border: 1px solid rgba(148, 163, 184, 0.24);
      background:
        radial-gradient(800px 280px at 10% -20%, rgba(37, 99, 235, 0.16), transparent 55%),
        linear-gradient(180deg, #ffffff, #f8fbff);
    }

    .avatar {
      width: 74px;
      height: 74px;
      border-radius: 18px;
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-size: 1.3rem;
      font-weight: 800;
      box-shadow: 0 14px 26px rgba(37, 99, 235, 0.26);
    }

    .profile-hero__left {
      display: flex;
      align-items: center;
      gap: 0.9rem;
    }

    .profile-meta h1 {
      margin: 0;
      font-size: clamp(1.35rem, 2.5vw, 1.7rem);
      letter-spacing: -0.02em;
    }

    .profile-meta p {
      margin: 0.15rem 0 0.45rem;
      color: var(--text-secondary);
      font-size: 0.9rem;
    }

    .chip-row {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.35rem;
    }

    .chip {
      font-size: 0.72rem;
      border-radius: 999px;
      padding: 0.2rem 0.52rem;
      background: rgba(22, 163, 74, 0.13);
      color: #15803d;
      border: 1px solid rgba(22, 163, 74, 0.2);
      font-weight: 700;
    }

    .chip--neutral {
      background: rgba(37, 99, 235, 0.08);
      color: #1d4ed8;
      border-color: rgba(37, 99, 235, 0.2);
    }

    .profile-hero__actions {
      display: grid;
      gap: 0.45rem;
    }

    .profile-hero__actions .btn {
      min-width: 190px;
      justify-content: center;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
    }

    .profile-card {
      padding: 1rem;
    }

    .section-title {
      margin: 0 0 0.75rem;
      font-size: 1.02rem;
      font-weight: 800;
    }

    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.6rem;
    }

    .detail-row {
      border: 1px solid var(--border-light);
      border-radius: 0.75rem;
      padding: 0.7rem 0.75rem;
      background: #fff;
      min-height: 70px;
      display: grid;
      align-content: center;
      gap: 0.15rem;
    }

    .label {
      color: var(--text-secondary);
      font-size: 0.78rem;
    }

    .value {
      font-weight: 700;
      color: var(--text-primary);
      word-break: break-word;
    }

    .profile-footnote {
      display: flex;
      gap: 0.5rem;
      align-items: center;
      color: var(--text-secondary);
      font-size: 0.84rem;
    }

    .profile-footnote p {
      margin: 0;
    }

    @media (max-width: 860px) {
      .profile-hero {
        flex-direction: column;
        align-items: stretch;
      }

      .profile-hero__actions {
        grid-template-columns: 1fr 1fr;
      }

      .profile-hero__actions .btn {
        min-width: 0;
      }
    }

    @media (max-width: 640px) {
      .detail-grid {
        grid-template-columns: 1fr;
      }

      .profile-hero__actions {
        grid-template-columns: 1fr;
      }
    }
  `],
})
export class ProfileViewComponent implements OnInit {
  private authService = inject(AuthService);

  user: User | null = null;
  loading = true;
  errorMessage = '';

  ngOnInit() {
    this.reload();
  }

  reload(): void {
    this.loading = true;
    this.errorMessage = '';
    this.authService.getProfile().subscribe({
      next: (data) => {
        this.user = data;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'Please check your internet and try again.';
      },
    });
  }

  displayName(): string {
    return (this.user?.name || '').trim() || 'ParkPe User';
  }

  displayEmail(): string {
    return (this.user?.email || '').trim() || 'Not available';
  }

  displayPhone(): string {
    const anyUser = this.user as (User & { mobile?: string; mobileNumber?: string }) | null;
    return (
      anyUser?.phone?.trim() ||
      anyUser?.mobile?.trim() ||
      anyUser?.mobileNumber?.trim() ||
      'Not available'
    );
  }

  userInitials(): string {
    const name = this.displayName();
    const parts = name.split(/\s+/).filter(Boolean);
    const initials = parts.slice(0, 2).map((p) => p[0]?.toUpperCase() || '').join('');
    return initials || 'PP';
  }
}
