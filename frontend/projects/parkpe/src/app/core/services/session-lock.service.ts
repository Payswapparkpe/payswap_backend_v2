import { Injectable, computed, signal } from '@angular/core';
import { Router } from '@angular/router';

const PIN_KEY = 'parkpe:session-lock:pin';
const LAST_ACTIVE_KEY = 'parkpe:session-lock:last-active';
const DEFAULT_IDLE_LOCK_MS = 5 * 60 * 1000;

/**
 * Simple one-way obfuscation for localStorage PIN storage.
 * PIN is XOR-scrambled + base64 so it's not readable plain text.
 * NOTE: This is NOT cryptographic security — it's obfuscation only.
 * The session lock is a convenience feature (idle screen lock), not
 * a replacement for backend authentication.
 */
function encodePin(pin: string): string {
  const salt = 'pkpe-sl-2025';
  let out = '';
  for (let i = 0; i < pin.length; i++) {
    out += String.fromCharCode(pin.charCodeAt(i) ^ salt.charCodeAt(i % salt.length));
  }
  return btoa(out);
}

function decodePin(encoded: string): string | null {
  try {
    const raw = atob(encoded);
    const salt = 'pkpe-sl-2025';
    let out = '';
    for (let i = 0; i < raw.length; i++) {
      out += String.fromCharCode(raw.charCodeAt(i) ^ salt.charCodeAt(i % salt.length));
    }
    return out;
  } catch {
    return null;
  }
}

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
      localStorage.setItem(PIN_KEY, encodePin(pin));
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
      const raw = localStorage.getItem(PIN_KEY);
      if (!raw) return null;
      // Support both encoded (new) and legacy plain-text (old) storage
      const decoded = decodePin(raw);
      // If decoded looks like a PIN (all digits, 4-6 chars), use it; else treat as legacy plain text
      if (decoded && /^\d{4,6}$/.test(decoded)) return decoded;
      // Legacy: plain text was a valid PIN — migrate to encoded
      if (/^\d{4,6}$/.test(raw)) {
        this.setPin(raw); // re-save encoded
        return raw;
      }
      return null;
    } catch {
      return null;
    }
  }
}
