import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { SessionLockService } from '../../../core/services/session-lock.service';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-session-lock',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="lock-wrap">
      <div class="lock-card card">
        <span class="material-icons lock-icon">lock</span>
        <h1>Session Locked</h1>
        <p>For your security, unlock with your 4-6 digit PIN.</p>
        <label for="lock-pin">PIN</label>
        <input
          id="lock-pin"
          type="password"
          maxlength="6"
          inputmode="numeric"
          [(ngModel)]="pin"
          placeholder="Enter PIN"
          (keyup.enter)="unlock()"
        />
        @if (error()) {
          <p class="error">{{ error() }}</p>
        }
        <button class="btn btn-primary" type="button" (click)="unlock()">Unlock</button>
        <button class="btn btn-link" type="button" (click)="showForgot.set(!showForgot())">
          Forgot PIN? Reset via OTP
        </button>

        @if (showForgot()) {
          <div class="forgot-wrap">
            <p class="forgot-note">Registered mobile par OTP aayega.</p>
            <button class="btn btn-outline" type="button" (click)="sendOtp()" [disabled]="sendingOtp()">
              {{ sendingOtp() ? 'Sending OTP…' : 'Send OTP' }}
            </button>
            @if (otpSent()) {
              <label for="otp">OTP</label>
              <input
                id="otp"
                type="text"
                maxlength="6"
                inputmode="numeric"
                [(ngModel)]="otp"
                placeholder="Enter OTP"
              />
              <label for="new-pin">New PIN</label>
              <input
                id="new-pin"
                type="password"
                maxlength="6"
                inputmode="numeric"
                [(ngModel)]="newPin"
                placeholder="New 4-6 digit PIN"
              />
              <label for="confirm-pin">Confirm PIN</label>
              <input
                id="confirm-pin"
                type="password"
                maxlength="6"
                inputmode="numeric"
                [(ngModel)]="confirmPin"
                placeholder="Re-enter new PIN"
              />
              <button class="btn btn-primary" type="button" (click)="verifyOtpAndReset()" [disabled]="verifyingOtp()">
                {{ verifyingOtp() ? 'Verifying…' : 'Verify OTP & Reset PIN' }}
              </button>
            }
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .lock-wrap { min-height: 100vh; display:flex; align-items:center; justify-content:center; padding:1rem; }
    .lock-card { width:min(420px, 100%); padding:1.5rem; text-align:center; }
    .lock-icon { font-size:42px; color:var(--primary-600); margin-bottom:0.35rem; }
    h1 { margin:0 0 0.4rem; font-size:1.35rem; }
    p { margin:0 0 1rem; color:var(--text-secondary); }
    label { display:block; text-align:left; font-size:0.85rem; font-weight:600; margin-bottom:0.3rem; }
    input { width:100%; box-sizing:border-box; padding:0.75rem; border:1px solid var(--border-default); border-radius:0.6rem; margin-bottom:0.8rem; }
    .error { color:var(--error, #b91c1c); margin:0 0 0.6rem; font-size:0.85rem; text-align:left; }
    button { width:100%; }
    .btn-link { background:transparent; border:none; color:var(--primary-600); margin-top:0.4rem; font-weight:600; cursor:pointer; }
    .forgot-wrap { margin-top:0.8rem; border-top:1px solid var(--border-light); padding-top:0.8rem; text-align:left; }
    .forgot-note { margin:0 0 0.6rem; font-size:0.8rem; }
    .forgot-wrap .btn { margin-bottom:0.6rem; }
  `],
})
export class SessionLockComponent {
  private lock = inject(SessionLockService);
  private auth = inject(AuthService);
  private notify = inject(NotificationService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  pin = '';
  otp = '';
  newPin = '';
  confirmPin = '';
  error = signal<string | null>(null);
  showForgot = signal(false);
  otpSent = signal(false);
  sendingOtp = signal(false);
  verifyingOtp = signal(false);

  unlock(): void {
    if (!this.lock.verifyAndUnlock(this.pin.trim())) {
      this.error.set('Invalid PIN. Please try again.');
      return;
    }
    const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || '/dashboard';
    this.router.navigateByUrl(returnUrl);
  }

  sendOtp(): void {
    const phone = this.getUserPhone();
    if (!phone) {
      this.error.set('Phone number not found. Please login again.');
      return;
    }
    this.sendingOtp.set(true);
    this.auth.requestLoginOtp(phone).subscribe({
      next: () => {
        this.sendingOtp.set(false);
        this.otpSent.set(true);
        this.error.set(null);
        this.notify.showSuccess('OTP sent to your mobile.');
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.sendingOtp.set(false);
        this.error.set(err?.error?.detail || err?.message || 'Failed to send OTP.');
      },
    });
  }

  verifyOtpAndReset(): void {
    const phone = this.getUserPhone();
    if (!phone) {
      this.error.set('Phone number not found. Please login again.');
      return;
    }
    if (!/^\d{4,6}$/.test(this.otp.trim())) {
      this.error.set('Enter valid OTP.');
      return;
    }
    if (!/^\d{4,6}$/.test(this.newPin.trim())) {
      this.error.set('PIN must be 4-6 digits.');
      return;
    }
    if (this.newPin.trim() !== this.confirmPin.trim()) {
      this.error.set('PIN and confirm PIN must match.');
      return;
    }
    this.verifyingOtp.set(true);
    this.auth.verifyLoginOtp(phone, this.otp.trim()).subscribe({
      next: () => {
        this.verifyingOtp.set(false);
        if (!this.lock.setPin(this.newPin.trim())) {
          this.error.set('OTP verified but PIN could not be saved.');
          return;
        }
        this.lock.unlock();
        this.notify.showSuccess('PIN reset successful.');
        const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || '/dashboard';
        this.router.navigateByUrl(returnUrl);
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.verifyingOtp.set(false);
        this.error.set(err?.error?.detail || err?.message || 'OTP verification failed.');
      },
    });
  }

  private getUserPhone(): string {
    const u = this.auth.userSignal();
    if (!u) return '';
    const anyUser = u as { phone?: string; mobile?: string; mobileNumber?: string };
    return (anyUser.phone || anyUser.mobile || anyUser.mobileNumber || '').trim();
  }
}
