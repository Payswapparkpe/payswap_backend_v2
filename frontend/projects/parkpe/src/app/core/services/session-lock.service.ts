import { Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';

const LAST_ACTIVE_KEY = 'parkpe:session-lock:last-active';
const PASSKEY_ENABLED_KEY = 'parkpe:session-lock:passkey-enabled';
const DEFAULT_IDLE_LOCK_MS = 5 * 60 * 1000;

@Injectable({ providedIn: 'root' })
export class SessionLockService {
  private idleMs = DEFAULT_IDLE_LOCK_MS;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private started = false;
  private _locked = signal(false);
  private _hasPin = signal(false);
  private _passkeyEnabled = signal(this.readPasskeyEnabledFlag());
  readonly locked = this._locked.asReadonly();
  readonly hasPin = this._hasPin.asReadonly();
  readonly hasPasskey = this._passkeyEnabled.asReadonly();
  readonly hasBiometric = this.hasPasskey;

  constructor(private router: Router) {}

  startMonitoring(): void {
    if (this.started) return;
    this.started = true;
    this.bindActivityListeners();
    this.markActivity();
  }

  configureIdleTimeout(ms: number): void {
    this.idleMs = Math.max(60_000, ms);
    this.scheduleIdleLock();
  }

  setHasPin(hasPin: boolean): void {
    this._hasPin.set(hasPin);
  }

  // Legacy local PIN methods intentionally removed; PIN is server-validated.

  async canUsePasskey(): Promise<boolean> {
    if (typeof window === 'undefined' || typeof navigator === 'undefined') return false;
    if (!('credentials' in navigator) || typeof PublicKeyCredential === 'undefined') return false;
    if (typeof PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable !== 'function') return false;
    try {
      return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch {
      return false;
    }
  }

  async canUseBiometric(): Promise<boolean> {
    return this.canUsePasskey();
  }

  setPasskeyEnabled(enabled: boolean): void {
    try {
      if (enabled) {
        localStorage.setItem(PASSKEY_ENABLED_KEY, '1');
      } else {
        localStorage.removeItem(PASSKEY_ENABLED_KEY);
      }
    } catch {
      // ignore
    }
    this._passkeyEnabled.set(enabled);
  }

  disableBiometric(): void {
    this.setPasskeyEnabled(false);
  }

  lock(reason: 'idle' | 'manual' = 'manual'): void {
    this._locked.set(true);
    this.clearTimer();
    const currentUrl = this.router.url || '/dashboard';
    if (!currentUrl.startsWith('/unlock')) {
      this.router.navigate(['/unlock'], {
        queryParams: {
          reason,
          returnUrl: currentUrl,
        },
      });
    }
  }

  unlock(): void {
    this._locked.set(false);
    this.markActivity();
  }

  markActivity(): void {
    try {
      localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
    } catch {
      // ignore
    }
    if (!this._locked()) this.scheduleIdleLock();
  }

  private bindActivityListeners(): void {
    if (typeof window === 'undefined') return;
    const events = ['click', 'keydown', 'touchstart', 'mousemove', 'scroll'];
    events.forEach((e) =>
      window.addEventListener(e, () => this.markActivity(), { passive: true })
    );
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        this.markActivity();
      } else {
        const last = Number(localStorage.getItem(LAST_ACTIVE_KEY) || Date.now());
        if (Date.now() - last > this.idleMs) {
          this.lock('idle');
        } else {
          this.markActivity();
        }
      }
    });
  }

  private scheduleIdleLock(): void {
    this.clearTimer();
    this.timer = setTimeout(() => this.lock('idle'), this.idleMs);
  }

  private clearTimer(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  private readPasskeyEnabledFlag(): boolean {
    try {
      return localStorage.getItem(PASSKEY_ENABLED_KEY) === '1';
    } catch {
      return false;
    }
  }
}
