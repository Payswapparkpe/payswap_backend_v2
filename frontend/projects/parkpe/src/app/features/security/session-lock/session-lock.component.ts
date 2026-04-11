import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { SessionLockService } from '../../../core/services/session-lock.service';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';

type View = 'lock' | 'reset-confirm' | 'reset-form';

@Component({
  selector: 'app-session-lock',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="sl-wrap">
      <div class="sl-card">

        <!-- ── LOCK VIEW ── -->
        @if (view() === 'lock') {
          <div class="sl-view">
            <div class="sl-icon-wrap">
              <span class="material-icons sl-icon">lock</span>
            </div>
            <h1 class="sl-title">Session Locked</h1>
            <p class="sl-sub">For your security, unlock with your 4–6 digit PIN.</p>

            <div class="sl-field">
              <label for="lock-pin" class="sl-label">PIN</label>
              <input
                id="lock-pin"
                class="sl-input"
                type="password"
                inputmode="numeric"
                maxlength="6"
                autocomplete="current-password"
                [(ngModel)]="pin"
                placeholder="Enter PIN"
                (keyup.enter)="unlock()"
                autofocus
              />
            </div>
            @if (error()) {
              <p class="sl-error" role="alert">{{ error() }}</p>
            }
            <button class="sl-btn sl-btn--primary" type="button" (click)="unlock()" [disabled]="!pin.trim()">
              Unlock
            </button>
            <button class="sl-btn-link" type="button" (click)="goToReset()">
              Forgot PIN? Reset via OTP
            </button>
          </div>
        }

        <!-- ── RESET STEP 1: CONFIRM send OTP ── -->
        @if (view() === 'reset-confirm') {
          <div class="sl-view">
            <div class="sl-icon-wrap sl-icon-wrap--reset">
              <span class="material-icons sl-icon sl-icon--reset">lock_reset</span>
            </div>
            <h1 class="sl-title">Reset PIN</h1>
            <p class="sl-sub">
              We'll send a one-time code to your registered mobile number to verify your identity.
            </p>
            @if (error()) {
              <p class="sl-error" role="alert">{{ error() }}</p>
            }
            <button class="sl-btn sl-btn--primary" type="button" (click)="sendOtp()" [disabled]="sendingOtp()">
              @if (sendingOtp()) { Sending… } @else { Send OTP to mobile }
            </button>
            <button class="sl-btn-link" type="button" (click)="back()">
              ← Back to unlock
            </button>
          </div>
        }

        <!-- ── RESET STEP 2: OTP + new PIN ── -->
        @if (view() === 'reset-form') {
          <div class="sl-view">
            <div class="sl-icon-wrap sl-icon-wrap--reset">
              <span class="material-icons sl-icon sl-icon--reset">key</span>
            </div>
            <h1 class="sl-title">Set New PIN</h1>
            <p class="sl-sub">Enter the OTP sent to your mobile, then choose a new PIN.</p>

            <div class="sl-field">
              <label for="sl-otp" class="sl-label">OTP</label>
              <input id="sl-otp" class="sl-input" type="text" inputmode="numeric"
                maxlength="6" autocomplete="one-time-code" [(ngModel)]="otp" placeholder="6-digit OTP" />
            </div>
            <div class="sl-field">
              <label for="sl-new-pin" class="sl-label">New PIN</label>
              <input id="sl-new-pin" class="sl-input" type="password" inputmode="numeric"
                maxlength="6" autocomplete="new-password" [(ngModel)]="newPin" placeholder="4–6 digit PIN" />
            </div>
            <div class="sl-field">
              <label for="sl-confirm-pin" class="sl-label">Confirm PIN</label>
              <input id="sl-confirm-pin" class="sl-input" type="password" inputmode="numeric"
                maxlength="6" autocomplete="new-password" [(ngModel)]="confirmPin" placeholder="Re-enter new PIN"
                (keyup.enter)="verifyOtpAndReset()" />
            </div>
            @if (error()) {
              <p class="sl-error" role="alert">{{ error() }}</p>
            }
            <button class="sl-btn sl-btn--primary" type="button"
              (click)="verifyOtpAndReset()" [disabled]="verifyingOtp() || !otp.trim() || !newPin.trim() || !confirmPin.trim()">
              @if (verifyingOtp()) { Verifying… } @else { Verify & Reset PIN }
            </button>
            <button class="sl-btn-link" type="button" (click)="resendOtp()" [disabled]="sendingOtp()">
              {{ sendingOtp() ? 'Sending…' : 'Resend OTP' }}
            </button>
          </div>
        }

      </div>
    </div>
  `,
  styles: [`
    .sl-wrap {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(160deg, #f8fafc 0%, #eef2ff 100%);
      padding: 1rem;
    }

    .sl-card {
      width: min(420px, 100%);
      background: #fff;
      border: 1px solid #e2e8f0;
      border-radius: 20px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08), 0 2px 8px rgba(0, 74, 173, 0.06);
      padding: 2rem 2rem 1.75rem;
      overflow: hidden;
    }

    .sl-view {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0;
    }

    .sl-icon-wrap {
      width: 64px;
      height: 64px;
      border-radius: 18px;
      background: rgba(0, 74, 173, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 1.1rem;
    }

    .sl-icon-wrap--reset {
      background: rgba(124, 58, 237, 0.1);
    }

    .sl-icon {
      font-size: 30px !important;
      color: var(--primary-600, #004aad);
    }

    .sl-icon--reset {
      color: #7c3aed;
    }

    .sl-title {
      font-size: 1.4rem;
      font-weight: 800;
      color: var(--text-primary, #0f172a);
      margin: 0 0 0.4rem;
      text-align: center;
      letter-spacing: -0.02em;
    }

    .sl-sub {
      font-size: 0.875rem;
      color: var(--text-secondary, #64748b);
      text-align: center;
      margin: 0 0 1.5rem;
      line-height: 1.5;
      max-width: 30ch;
    }

    .sl-field {
      width: 100%;
      margin-bottom: 0.85rem;
    }

    .sl-label {
      display: block;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-primary, #0f172a);
      margin-bottom: 0.35rem;
    }

    .sl-input {
      width: 100%;
      box-sizing: border-box;
      padding: 0.75rem 1rem;
      border: 1.5px solid #e2e8f0;
      border-radius: 10px;
      font-size: 1rem;
      color: var(--text-primary, #0f172a);
      transition: border-color 0.15s;
      outline: none;
      background: #fafafa;

      &:focus {
        border-color: var(--primary-500, #3b82f6);
        background: #fff;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
      }
    }

    .sl-error {
      width: 100%;
      font-size: 0.825rem;
      color: #b91c1c;
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 8px;
      padding: 0.55rem 0.75rem;
      margin-bottom: 0.85rem;
      text-align: left;
    }

    .sl-btn {
      width: 100%;
      padding: 0.8rem 1rem;
      border-radius: 10px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      border: none;
      transition: background 0.15s, opacity 0.15s, transform 0.1s;
      margin-bottom: 0.5rem;

      &:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }

      &:not(:disabled):active {
        transform: scale(0.99);
      }
    }

    .sl-btn--primary {
      background: var(--primary-600, #004aad);
      color: #fff;

      &:not(:disabled):hover {
        background: var(--primary-700, #003175);
      }
    }

    .sl-btn-link {
      background: transparent;
      border: none;
      color: var(--primary-600, #004aad);
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      padding: 0.4rem 0;
      margin-top: 0.25rem;
      width: 100%;
      text-align: center;

      &:hover { text-decoration: underline; }
      &:disabled { opacity: 0.5; cursor: not-allowed; }
    }
  `],
})
export class SessionLockComponent {
  private lock = inject(SessionLockService);
  private auth = inject(AuthService);
  private notify = inject(NotificationService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  view = signal<View>('lock');
  pin = '';
  otp = '';
  newPin = '';
  confirmPin = '';
  error = signal<string | null>(null);
  sendingOtp = signal(false);
  verifyingOtp = signal(false);

  goToReset(): void {
    this.error.set(null);
    this.view.set('reset-confirm');
  }

  back(): void {
    this.error.set(null);
    this.view.set('lock');
  }

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
      this.error.set('Phone number not found. Please log in again.');
      return;
    }
    this.error.set(null);
    this.sendingOtp.set(true);
    this.auth.requestLoginOtp(phone).subscribe({
      next: () => {
        this.sendingOtp.set(false);
        this.notify.showSuccess('OTP sent to your mobile.');
        this.view.set('reset-form');
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.sendingOtp.set(false);
        this.error.set(err?.error?.detail || err?.message || 'Failed to send OTP.');
      },
    });
  }

  resendOtp(): void {
    this.otp = '';
    this.sendOtp();
  }

  verifyOtpAndReset(): void {
    const phone = this.getUserPhone();
    if (!phone) { this.error.set('Phone number not found.'); return; }
    if (!/^\d{4,6}$/.test(this.otp.trim())) { this.error.set('Enter a valid OTP.'); return; }
    if (!/^\d{4,6}$/.test(this.newPin.trim())) { this.error.set('PIN must be 4–6 digits.'); return; }
    if (this.newPin.trim() !== this.confirmPin.trim()) { this.error.set('PINs do not match.'); return; }

    this.error.set(null);
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
