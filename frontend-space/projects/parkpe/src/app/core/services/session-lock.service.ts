import { Injectable, computed, signal } from '@angular/core';
import { Router } from '@angular/router';

const PIN_KEY = 'parkpe:session-lock:pin';
const LAST_ACTIVE_KEY = 'parkpe:session-lock:last-active';
const DEFAULT_IDLE_LOCK_MS = 5 * 60 * 1000;

@Injectable({ providedIn: 'root' })
export class SessionLockService {
  private idleMs = DEFAULT_IDLE_LOCK_MS;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private started = false;
  private _locked = signal(false);
  readonly locked = this._locked.asReadonly();
  readonly hasPin = computed(() => !!this.readPin());

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

  setPin(pin: string): boolean {
    if (!/^\d{4,6}$/.test(pin)) return false;
    try {
      localStorage.setItem(PIN_KEY, pin);
      return true;
    } catch {
      return false;
    }
  }

  ensurePinFromHint(hint: string | null | undefined): void {
    if (this.hasPin()) return;
    const digits = String(hint || '').replace(/\D/g, '');
    const candidate = digits.slice(-4);
    if (candidate.length === 4) this.setPin(candidate);
  }

  verifyAndUnlock(pin: string): boolean {
    const stored = this.readPin();
    if (!stored || String(pin) !== stored) return false;
    this.unlock();
    return true;
  }

  verifyPin(pin: string): boolean {
    const stored = this.readPin();
    if (!stored) return false;
    return String(pin) === stored;
  }

  lock(reason: 'idle' | 'manual' = 'manual'): void {
    this._locked.set(true);
    this.clearTimer();
    if (reason === 'idle') {
      this.router.navigate(['/unlock'], { queryParams: { reason: 'idle' } });
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

  private readPin(): string | null {
    try {
      return localStorage.getItem(PIN_KEY);
    } catch {
      return null;
    }
  }
}
