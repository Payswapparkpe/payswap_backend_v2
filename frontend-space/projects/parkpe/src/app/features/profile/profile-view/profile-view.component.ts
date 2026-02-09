import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { User } from '../../../core/models/auth.model';

@Component({
  selector: 'app-profile-view',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="profile-container">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="profile-title">My Profile</h1>

      @if (loading) {
        <div class="loading-state"><div class="spinner"></div></div>
      } @else if (user) {
        <div class="profile-card card">
          <div class="profile-header">
            <div class="avatar">
              <span class="material-icons">person</span>
            </div>
            <div class="profile-info">
              <h2>{{ user.name }}</h2>
              <p>{{ user.email }}</p>
            </div>
          </div>

          <div class="profile-details">
            <div class="detail-row">
              <span class="label">Name</span>
              <span class="value">{{ user.name }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Email</span>
              <span class="value">{{ user.email }}</span>
            </div>
            <div class="detail-row">
              <span class="label">Phone</span>
              <span class="value">{{ user.phone }}</span>
            </div>
            @if (user.createdAt) {
              <div class="detail-row">
                <span class="label">Member Since</span>
                <span class="value">{{ user.createdAt | date:'mediumDate' }}</span>
              </div>
            }
          </div>

          <button class="btn btn-primary btn-block" routerLink="/profile/edit">
            <span class="material-icons">edit</span> Edit Profile
          </button>
        </div>
      }
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
    .profile-card { padding: 2rem; }
    .profile-header {
      display: flex;
      align-items: center;
      gap: 1.5rem;
      margin-bottom: 2rem;
      padding-bottom: 2rem;
      border-bottom: 2px solid var(--border-light);
    }
    .avatar {
      width: 100px;
      height: 100px;
      border-radius: 50%;
      background: var(--primary-100);
      display: flex;
      align-items: center;
      justify-content: center;

      .material-icons { font-size: 50px; color: var(--primary-600); }
    }
    .profile-info h2 { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; }
    .profile-info p { color: var(--text-secondary); }
    .profile-details { margin-bottom: 2rem; }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 1rem 0;
      border-bottom: 1px solid var(--border-light);
    }
    .label { color: var(--text-secondary); }
    .value { font-weight: 600; }
    .btn-block {
      width: 100%;
      padding: 1rem;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
    }
  `],
})
export class ProfileViewComponent implements OnInit {
  private authService = inject(AuthService);

  user: User | null = null;
  loading = true;

  ngOnInit() {
    this.authService.getProfile().subscribe({
      next: (data) => {
        this.user = data;
        this.loading = false;
      },
      error: () => this.loading = false,
    });
  }
}
