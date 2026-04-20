import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
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
      <div class="sl-bg-icons" aria-hidden="true">
        <span class="material-icons sl-bg-icon sl-bg-icon--a">toll</span>
        <span class="material-icons sl-bg-icon sl-bg-icon--b">receipt_long</span>
        <span class="material-icons sl-bg-icon sl-bg-icon--c">qr_code_2</span>
        <span class="material-icons sl-bg-icon sl-bg-icon--d">card_giftcard</span>
        <span class="material-icons sl-bg-icon sl-bg-icon--e">local_parking</span>
        <span class="material-icons sl-bg-icon sl-bg-icon--f">payments</span>
      </div>
      <div class="sl-card">

        <!-- ── LOCK VIEW ── -->
        @if (view() === 'lock') {
          <div class="sl-view">
            <div class="sl-icon-wrap">
              <span class="material-icons sl-icon">lock</span>
            </div>
            <h1 class="sl-title">Session Locked</h1>
            <p class="sl-sub">For your security, unlock with your 4–6 digit PIN.</p>
            <div class="sl-service-strip" aria-label="Protected services">
              <span class="sl-service-chip">
                <span class="material-icons" aria-hidden="true">toll</span> FASTag
              </span>
              <span class="sl-service-chip">
                <span class="material-icons" aria-hidden="true">receipt_long</span> BBPS
              </span>
              <span class="sl-service-chip">
                <span class="material-icons" aria-hidden="true">qr_code_2</span> Connect
              </span>
              <span class="sl-service-chip">
                <span class="material-icons" aria-hidden="true">card_giftcard</span> Vouchers
              </span>
            </div>

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
            @if (biometricSupported() && hasBiometricEnabled()) {
              <button
                class="sl-btn sl-btn--secondary"
                type="button"
                (click)="unlockWithBiometric()"
                [disabled]="biometricBusy()"
              >
                @if (biometricBusy()) { Verifying… } @else { Use Passkey / Face / Fingerprint }
              </button>
            }
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
      position: relative;
      overflow: hidden;
      isolation: isolate;
      background:
        radial-gradient(900px 460px at 8% 0%, rgba(0, 74, 173, 0.22), transparent 62%),
        radial-gradient(760px 420px at 92% 8%, rgba(124, 58, 237, 0.2), transparent 62%),
        linear-gradient(155deg, #f6f8ff 0%, #eef2ff 45%, #e7ecff 100%);
      padding: 1rem;
    }

    .sl-wrap::before,
    .sl-wrap::after {
      content: '';
      position: absolute;
      border-radius: 999px;
      pointer-events: none;
      filter: blur(2px);
      z-index: 0;
    }

    .sl-wrap::before {
      width: 440px;
      height: 440px;
      left: -130px;
      top: 12%;
      background: radial-gradient(circle at 35% 35%, rgba(59, 130, 246, 0.28), rgba(59, 130, 246, 0.05) 62%, transparent 78%);
      box-shadow: inset 18px 18px 34px rgba(255, 255, 255, 0.35);
    }

    .sl-wrap::after {
      width: 360px;
      height: 360px;
      right: -100px;
      bottom: 10%;
      background: radial-gradient(circle at 35% 35%, rgba(139, 92, 246, 0.24), rgba(139, 92, 246, 0.06) 62%, transparent 78%);
      box-shadow: inset 14px 14px 28px rgba(255, 255, 255, 0.28);
    }

    .sl-bg-icons {
      position: absolute;
      inset: 0;
      pointer-events: none;
      z-index: 0;
    }

    .sl-bg-icon {
      position: absolute;
      color: rgba(37, 99, 235, 0.16);
      background: rgba(255, 255, 255, 0.34);
      border: 1px solid rgba(191, 219, 254, 0.55);
      box-shadow: 0 8px 20px rgba(37, 99, 235, 0.08);
      border-radius: 14px;
      padding: 0.45rem;
      font-size: 1.45rem;
      backdrop-filter: blur(2px);
      animation: sl-float 6s ease-in-out infinite;
    }

    .sl-bg-icon--a { left: 10%; top: 18%; animation-delay: 0s; }
    .sl-bg-icon--b { right: 13%; top: 20%; animation-delay: 1.2s; }
    .sl-bg-icon--c { left: 14%; bottom: 22%; animation-delay: 0.8s; }
    .sl-bg-icon--d { right: 10%; bottom: 17%; animation-delay: 2s; }
    .sl-bg-icon--e { left: 30%; top: 9%; animation-delay: 1.6s; }
    .sl-bg-icon--f { right: 30%; bottom: 9%; animation-delay: 2.6s; }

    @keyframes sl-float {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-8px); }
    }

    @media (max-width: 640px) {
      .sl-bg-icon {
        font-size: 1.15rem;
        padding: 0.35rem;
        border-radius: 12px;
      }
      .sl-bg-icon--e,
      .sl-bg-icon--f {
        display: none;
      }
    }

    .sl-card {
      width: min(420px, 100%);
      position: relative;
      z-index: 1;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.97) 0%, rgba(247, 250, 255, 0.93) 100%);
      border: 1px solid rgba(226, 232, 240, 0.9);
      border-radius: 22px;
      box-shadow:
        0 30px 60px rgba(15, 23, 42, 0.12),
        0 10px 24px rgba(0, 74, 173, 0.12),
        inset 0 1px 0 rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(10px);
      padding: 2rem 2rem 1.75rem;
      overflow: hidden;
    }

    .sl-card::before {
      content: '';
      position: absolute;
      inset: 0;
      border-radius: inherit;
      pointer-events: none;
      background: linear-gradient(145deg, rgba(255, 255, 255, 0.6), transparent 55%);
      z-index: 0;
    }

    .sl-view {
      position: relative;
      z-index: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0;
    }

    .sl-icon-wrap {
      width: 64px;
      height: 64px;
      border-radius: 18px;
      background: linear-gradient(145deg, rgba(0, 74, 173, 0.16), rgba(59, 130, 246, 0.08));
      border: 1px solid rgba(0, 74, 173, 0.18);
      box-shadow: 0 10px 20px rgba(0, 74, 173, 0.16);
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 1.1rem;
    }

    .sl-icon-wrap--reset {
      background: linear-gradient(145deg, rgba(124, 58, 237, 0.16), rgba(139, 92, 246, 0.08));
      border-color: rgba(124, 58, 237, 0.2);
      box-shadow: 0 10px 20px rgba(124, 58, 237, 0.16);
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
      margin: 0 0 0.9rem;
      line-height: 1.5;
      max-width: 30ch;
    }

    .sl-service-strip {
      width: 100%;
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 0.4rem;
      margin: 0 0 1rem;
      padding: 0.55rem;
      border: 1px solid rgba(148, 163, 184, 0.28);
      border-radius: 12px;
      background: linear-gradient(180deg, rgba(239, 246, 255, 0.7), rgba(238, 242, 255, 0.55));
    }

    .sl-service-chip {
      display: inline-flex;
      align-items: center;
      gap: 0.22rem;
      padding: 0.22rem 0.5rem;
      border-radius: 999px;
      font-size: 0.66rem;
      font-weight: 700;
      color: #1e3a8a;
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid rgba(191, 219, 254, 0.95);
      letter-spacing: 0.01em;
      white-space: nowrap;
    }

    .sl-service-chip .material-icons {
      font-size: 0.82rem;
      color: #1d4ed8;
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
      background: linear-gradient(135deg, var(--primary-600, #004aad), #2563eb);
      color: #fff;

      &:not(:disabled):hover {
        background: linear-gradient(135deg, var(--primary-700, #003175), #1d4ed8);
      }
    }

    .sl-btn--secondary {
      background: rgba(37, 99, 235, 0.08);
      color: #1d4ed8;
      border: 1px solid rgba(37, 99, 235, 0.25);
      margin-top: -0.15rem;
      margin-bottom: 0.55rem;

      &:not(:disabled):hover {
        background: rgba(37, 99, 235, 0.14);
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
  biometricSupported = signal(false);
  biometricBusy = signal(false);
  hasBiometricEnabled = this.lock.hasBiometric;

  view = signal<View>('lock');
  pin = '';
  otp = '';
  newPin = '';
  confirmPin = '';
  error = signal<string | null>(null);
  sendingOtp = signal(false);
  verifyingOtp = signal(false);

  constructor() {
    void this.initBiometricSupport();
  }

  goToReset(): void {
    this.error.set(null);
    this.view.set('reset-confirm');
  }

  back(): void {
    this.error.set(null);
    this.view.set('lock');
  }

  unlock(): void {
    if (!this.lock.hasPin()) {
      this.error.set('No PIN is configured for this account. Reset PIN via OTP or set it in Settings.');
      return;
    }
    this.auth.verifySessionPin(this.pin.trim()).subscribe({
      next: () => {
        this.lock.unlock();
        const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || this.auth.getPostLoginRoute();
        this.router.navigateByUrl(returnUrl);
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.error.set(err?.error?.detail || err?.message || 'Invalid PIN. Please try again.');
      },
    });
  }

  async unlockWithBiometric(): Promise<void> {
    this.error.set(null);
    this.biometricBusy.set(true);
    try {
      const optionsResp = await firstValueFrom(this.auth.getPasskeyAuthOptions());
      const publicKey = this.mapAuthenticationOptions(optionsResp.publicKey);
      const assertion = await navigator.credentials.get({ publicKey });
      if (!assertion || assertion.type !== 'public-key') {
        this.error.set('Passkey verification was cancelled.');
        return;
      }
      const serialized = this.serializeAuthenticationCredential(assertion as PublicKeyCredential);
      await firstValueFrom(this.auth.verifyPasskeyAuth(serialized));
      this.lock.unlock();
      const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || this.auth.getPostLoginRoute();
      this.router.navigateByUrl(returnUrl);
    } catch (err: unknown) {
      const apiErr = err as { error?: { detail?: string }; message?: string };
      this.error.set(apiErr?.error?.detail || apiErr?.message || 'Passkey verification failed.');
    } finally {
      this.biometricBusy.set(false);
    }
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
        this.auth.setSessionPin({ pin: this.newPin.trim(), forceReset: true }).subscribe({
          next: () => {
            this.verifyingOtp.set(false);
            this.lock.setHasPin(true);
            this.lock.unlock();
            this.notify.showSuccess('PIN reset successful.');
            const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || this.auth.getPostLoginRoute();
            this.router.navigateByUrl(returnUrl);
          },
          error: (pinErr: { error?: { detail?: string }; message?: string }) => {
            this.verifyingOtp.set(false);
            this.error.set(pinErr?.error?.detail || pinErr?.message || 'OTP verified but PIN update failed.');
          },
        });
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

  private async initBiometricSupport(): Promise<void> {
    this.biometricSupported.set(await this.lock.canUsePasskey());
    this.auth.getPinStatus().subscribe({
      next: (res) => this.lock.setHasPin(!!res.hasPin),
      error: () => this.lock.setHasPin(false),
    });
    this.auth.getPasskeyStatus().subscribe({
      next: (res) => this.lock.setPasskeyEnabled(!!res.enabled),
      error: () => this.lock.setPasskeyEnabled(false),
    });
  }

  private mapAuthenticationOptions(raw: Record<string, unknown>): PublicKeyCredentialRequestOptions {
    const options = { ...(raw as Record<string, unknown>) };
    options['challenge'] = this.base64UrlToBuffer(String(options['challenge'] || ''));
    const allow = Array.isArray(options['allowCredentials']) ? options['allowCredentials'] : [];
    options['allowCredentials'] = allow.map((item) => ({
      ...(item as Record<string, unknown>),
      id: this.base64UrlToBuffer(String((item as Record<string, unknown>)['id'] || '')),
    }));
    return options as unknown as PublicKeyCredentialRequestOptions;
  }

  private serializeAuthenticationCredential(credential: PublicKeyCredential): Record<string, unknown> {
    const response = credential.response as AuthenticatorAssertionResponse;
    return {
      id: credential.id,
      rawId: this.bufferToBase64Url(credential.rawId),
      type: credential.type,
      response: {
        authenticatorData: this.bufferToBase64Url(response.authenticatorData),
        clientDataJSON: this.bufferToBase64Url(response.clientDataJSON),
        signature: this.bufferToBase64Url(response.signature),
        userHandle: response.userHandle ? this.bufferToBase64Url(response.userHandle) : null,
      },
      clientExtensionResults: credential.getClientExtensionResults(),
    };
  }

  private base64UrlToBuffer(input: string): ArrayBuffer {
    const padded = input.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(input.length / 4) * 4, '=');
    const raw = atob(padded);
    const bytes = Uint8Array.from(raw, (c) => c.charCodeAt(0));
    return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  }

  private bufferToBase64Url(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  }
}
