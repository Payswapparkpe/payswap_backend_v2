import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, BehaviorSubject, tap, catchError, throwError, map, of } from 'rxjs';
import { take, timeout } from 'rxjs/operators';
import { API_BACKEND_TOKEN } from '../constants';
import { LoggerService } from './logger.service';
import { NotificationService } from './notification.service';
import { SessionLockService } from './session-lock.service';
import { environment } from '../../../environments/environment';
import {
  User,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterVerifyRequest,
  ForgotPasswordRequest,
} from 'shared';

/** Storage keys for session persistence (reload keeps user logged in). See docs/AUTH_STORAGE_SECURITY.md for production safety. */
const PARKPE_TOKEN_KEY = 'parkpe_auth_token';
const PARKPE_REFRESH_TOKEN_KEY = 'parkpe_refresh_token';
const PARKPE_USER_KEY = 'parkpe_auth_user';

/** Inactivity timeout window for session lock. */
const INACTIVITY_MS = 15 * 60 * 1000;

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private api = inject(API_BACKEND_TOKEN);
  private http = inject(HttpClient);
  private router = inject(Router);
  private logger = inject(LoggerService);
  private notification = inject(NotificationService);
  private sessionLock = inject(SessionLockService);

  private userSubject = new BehaviorSubject<User | null>(null);
  private tokenSubject = new BehaviorSubject<string | null>(null);
  private refreshTokenSubject = new BehaviorSubject<string | null>(null);
  private inactivityTimer: ReturnType<typeof setTimeout> | null = null;

  user$ = this.userSubject.asObservable();
  token$ = this.tokenSubject.asObservable();

  // Signals for reactive state
  userSignal = signal<User | null>(null);
  isAuthenticatedSignal = signal(false);

  constructor() {
    this.restoreSessionFromStorage();
  }

  /** Restore token, refresh token and user from localStorage so reload keeps user logged in */
  private restoreSessionFromStorage(): void {
    try {
      const token = localStorage.getItem(PARKPE_TOKEN_KEY);
      const refreshToken = localStorage.getItem(PARKPE_REFRESH_TOKEN_KEY);
      const userJson = localStorage.getItem(PARKPE_USER_KEY);
      if (token && token.length > 0) {
        this.tokenSubject.next(token);
        if (refreshToken && refreshToken.length > 0) {
          this.refreshTokenSubject.next(refreshToken);
        }
        this.isAuthenticatedSignal.set(true);
        if (userJson) {
          try {
            const user = JSON.parse(userJson) as User;
            this.userSubject.next(user);
            this.userSignal.set(user);
          } catch {
            // Invalid user JSON – keep token only; profile can be refetched
          }
        }
      }
    } catch {
      // localStorage not available or disabled
    }
  }

  login(credentials: LoginRequest): Observable<LoginResponse> {
    this.logger.info('login_start', { service: 'auth', action: 'login_start' });
    return this.api.login(credentials).pipe(
      tap((response) => {
        this.setSession(response);
        this.logger.info('login_success', { service: 'auth', action: 'login_success', userId: response.user?.id });
      }),
      catchError((err) => {
        this.logger.warn('login_error', { service: 'auth', action: 'login_error', status: err?.status });
        return throwError(() => err);
      })
    );
  }

  fleetLogin(credentials: LoginRequest): Observable<LoginResponse> {
    this.logger.info('fleet_login_start', { service: 'auth', action: 'fleet_login_start' });
    return this.api.fleetLogin(credentials).pipe(
      tap((response) => {
        this.setSession(response);
        this.logger.info('fleet_login_success', {
          service: 'auth',
          action: 'fleet_login_success',
          userId: response.user?.id,
        });
      }),
      catchError((err) => {
        this.logger.warn('fleet_login_error', {
          service: 'auth',
          action: 'fleet_login_error',
          status: err?.status,
        });
        return throwError(() => err);
      })
    );
  }

  parkingLogin(credentials: LoginRequest): Observable<LoginResponse> {
    this.logger.info('parking_login_start', { service: 'auth', action: 'parking_login_start' });
    return this.api.parkingLogin(credentials).pipe(
      tap((response) => {
        this.setSession(response);
        this.logger.info('parking_login_success', {
          service: 'auth',
          action: 'parking_login_success',
          userId: response.user?.id,
        });
      }),
      catchError((err) => {
        this.logger.warn('parking_login_error', {
          service: 'auth',
          action: 'parking_login_error',
          status: err?.status,
        });
        return throwError(() => err);
      })
    );
  }

  requestLoginOtp(phone: string): Observable<{ message: string; expires_in: number }> {
    this.logger.info('login_otp_request', { service: 'auth', action: 'login_otp_request' });
    return this.api.requestLoginOtp(phone).pipe(
      tap(() => this.logger.info('login_otp_sent', { service: 'auth', action: 'login_otp_sent' })),
      catchError((err) => {
        this.logger.warn('login_otp_request_error', { service: 'auth', action: 'login_otp_request_error', status: err?.status });
        return throwError(() => err);
      })
    );
  }

  verifyLoginOtp(phone: string, otp: string): Observable<LoginResponse> {
    this.logger.info('login_otp_verify', { service: 'auth', action: 'login_otp_verify' });
    return this.api.verifyLoginOtp(phone, otp).pipe(
      tap((response) => {
        this.setSession(response);
        this.logger.info('login_otp_success', { service: 'auth', action: 'login_otp_success', userId: response.user?.id });
      }),
      catchError((err) => {
        this.logger.warn('login_otp_verify_error', { service: 'auth', action: 'login_otp_verify_error', status: err?.status });
        return throwError(() => err);
      })
    );
  }

  register(payload: RegisterRequest) {
    this.logger.info('register_start', { service: 'auth', action: 'register_start' });
    return this.api.register(payload).pipe(
      tap(() => this.logger.info('register_success', { service: 'auth', action: 'register_success' })),
      catchError((err) => {
        this.logger.warn('register_error', { service: 'auth', action: 'register_error', status: err?.status });
        return throwError(() => err);
      })
    );
  }

  registerSendOtp(payload: RegisterRequest) {
    this.logger.info('register_send_otp', { service: 'auth', action: 'register_send_otp' });
    return this.api.registerSendOtp(payload).pipe(
      tap(() => this.logger.info('register_otp_sent', { service: 'auth', action: 'register_otp_sent' })),
      catchError((err) => {
        this.logger.warn('register_send_otp_error', { service: 'auth', action: 'register_send_otp_error', status: err?.status });
        return throwError(() => err);
      })
    );
  }

  registerVerify(payload: RegisterVerifyRequest) {
    this.logger.info('register_verify', { service: 'auth', action: 'register_verify' });
    return this.api.registerVerify(payload).pipe(
      tap((response) => {
        this.setSession(response);
        this.logger.info('register_verify_success', { service: 'auth', action: 'register_verify_success', userId: response.user?.id });
      }),
      catchError((err) => {
        this.logger.warn('register_verify_error', { service: 'auth', action: 'register_verify_error', status: err?.status });
        return throwError(() => err);
      })
    );
  }

  lookupPincode(pincode: string) {
    return this.api.lookupPincode(pincode);
  }

  logout(): void {
    this.logger.info('logout', { service: 'auth', action: 'logout' });
    this.api.logout().subscribe({
      next: () => {
        this.clearSession();
        this.router.navigate(['/auth/login']);
      },
      error: () => {
        this.clearSession();
        this.router.navigate(['/auth/login']);
      },
    });
  }

  /** Clear session (memory + localStorage). Call on logout and on 401 when refresh fails. */
  clearSession(): void {
    this.stopInactivityTimer();
    this.tokenSubject.next(null);
    this.refreshTokenSubject.next(null);
    this.userSubject.next(null);
    this.userSignal.set(null);
    this.isAuthenticatedSignal.set(false);
    this.sessionLock.unlock();
    try {
      localStorage.removeItem(PARKPE_TOKEN_KEY);
      localStorage.removeItem(PARKPE_REFRESH_TOKEN_KEY);
      localStorage.removeItem(PARKPE_USER_KEY);
    } catch {
      // ignore
    }
  }

  /** Start inactivity timer; on timeout lock session (do not logout). */
  startInactivityTimer(): void {
    this.stopInactivityTimer();
    if (!this.isAuthenticated()) return;
    this.inactivityTimer = setTimeout(() => {
      this.inactivityTimer = null;
      this.sessionLock.lock('idle');
      this.notification.showInfo('Session locked due to inactivity. Enter your PIN to continue.');
      this.logger.info('inactivity_lock', { service: 'auth', action: 'inactivity_lock' });
    }, INACTIVITY_MS);
  }

  /** Stop inactivity timer (e.g. on logout). */
  stopInactivityTimer(): void {
    if (this.inactivityTimer != null) {
      clearTimeout(this.inactivityTimer);
      this.inactivityTimer = null;
    }
  }

  /** Reset inactivity timer on user activity (click, API call). Keeps session alive. */
  resetInactivityTimer(): void {
    if (this.isAuthenticated()) {
      this.startInactivityTimer();
      this.sessionLock.markActivity();
    }
  }

  /** Get stored refresh token (for 401 retry). */
  getRefreshToken(): string | null {
    return this.refreshTokenSubject.value;
  }

  /**
   * On page load/reload: if we have a refresh token, get a fresh access token so first API call doesn't 401.
   * Used by APP_INITIALIZER so token is refreshed before app renders.
   */
  refreshTokenIfStored(): Observable<boolean> {
    const refresh = this.getRefreshToken();
    if (!refresh || refresh.length === 0) {
      return of(false);
    }
    return this.refreshToken().pipe(
      map(() => true),
      catchError(() => of(false)),
      take(1)
    );
  }

  /**
   * Refresh access token using refresh token. On success updates stored access token and returns it.
   * Used when a request returns 401 so active users stay logged in (session extends on activity).
   */
  refreshToken(): Observable<string | null> {
    const refresh = this.getRefreshToken();
    if (!refresh || refresh.length === 0) {
      return throwError(() => new Error('No refresh token'));
    }
    const url = `${environment.apiUrl ?? '/api'}/v1/auth/token/refresh/`;
    return this.http.post<{ access: string }>(url, { refresh }).pipe(
      timeout(10000),
      map((res) => res?.access ?? null),
      tap((access) => {
        if (access) {
          this.tokenSubject.next(access);
          try {
            localStorage.setItem(PARKPE_TOKEN_KEY, access);
          } catch {
            // ignore
          }
          this.logger.info('token_refreshed', { service: 'auth', action: 'token_refresh_success' });
        }
      }),
      catchError((err) => {
        this.logger.warn('token_refresh_failed', { service: 'auth', action: 'token_refresh_failed', status: err?.status });
        return throwError(() => err);
      })
    );
  }

  forgotPassword(email: string) {
    this.logger.info('forgot_password_request', { service: 'auth', action: 'forgot_password_request' });
    return this.api.forgotPassword({ email }).pipe(
      tap(() => this.logger.info('forgot_password_sent', { service: 'auth', action: 'forgot_password_sent' })),
      catchError((err) => {
        this.logger.warn('forgot_password_error', { service: 'auth', action: 'forgot_password_error', status: err?.status });
        return throwError(() => err);
      })
    );
  }

  getProfile() {
    return this.api.getProfile().pipe(
      tap((user) => {
        this.userSubject.next(user);
        this.userSignal.set(user);
        try {
          localStorage.setItem(PARKPE_USER_KEY, JSON.stringify(user));
        } catch {
          // ignore
        }
      })
    );
  }

  updateProfile(payload: Partial<User>) {
    return this.api.updateProfile(payload).pipe(
      tap((user) => {
        this.userSubject.next(user);
        this.userSignal.set(user);
        try {
          localStorage.setItem(PARKPE_USER_KEY, JSON.stringify(user));
        } catch {
          // ignore
        }
      })
    );
  }

  getPinStatus() {
    return this.api.getPinStatus();
  }

  setSessionPin(payload: { pin: string; currentPin?: string; forceReset?: boolean }) {
    return this.api.setSessionPin(payload);
  }

  verifySessionPin(pin: string) {
    return this.api.verifySessionPin(pin);
  }

  getPasskeyStatus() {
    return this.api.getPasskeyStatus();
  }

  getPasskeyRegisterOptions() {
    return this.api.getPasskeyRegisterOptions();
  }

  verifyPasskeyRegistration(credential: Record<string, unknown>) {
    return this.api.verifyPasskeyRegistration(credential);
  }

  getPasskeyAuthOptions() {
    return this.api.getPasskeyAuthOptions();
  }

  verifyPasskeyAuth(credential: Record<string, unknown>) {
    return this.api.verifyPasskeyAuth(credential);
  }

  disablePasskey() {
    return this.api.disablePasskey();
  }

  getSecurityOverview() {
    return this.api.getSecurityOverview();
  }

  revokeSessions(payload?: { device_id?: number }) {
    return this.api.revokeSessions(payload);
  }

  getSecurityActivity() {
    return this.api.getSecurityActivity();
  }

  getPasskeyCredentials() {
    return this.api.getPasskeyCredentials();
  }

  updatePasskeyCredential(credentialId: number, label: string) {
    return this.api.updatePasskeyCredential(credentialId, label);
  }

  deletePasskeyCredential(credentialId: number) {
    return this.api.deletePasskeyCredential(credentialId);
  }

  requestPasskeyRecoveryOtp() {
    return this.api.requestPasskeyRecoveryOtp();
  }

  verifyPasskeyRecoveryOtp(otp: string) {
    return this.api.verifyPasskeyRecoveryOtp(otp);
  }

  isAuthenticated(): boolean {
    return !!this.tokenSubject.value;
  }

  isFleetUser(user: User | null | undefined = this.userSubject.value): boolean {
    const roleCode = String((user as unknown as { roleCode?: string })?.roleCode || '').toLowerCase();
    const role = String((user as unknown as { role?: string })?.role || '').toLowerCase();
    return roleCode.startsWith('fleet_') || role === 'fleet';
  }

  isParkingUser(user: User | null | undefined = this.userSubject.value): boolean {
    const roleCode = String((user as unknown as { roleCode?: string })?.roleCode || '').toLowerCase();
    const role = String((user as unknown as { role?: string })?.role || '').toLowerCase();
    return roleCode.startsWith('parking_') || role === 'parking';
  }

  getPostLoginRoute(user: User | null | undefined = this.userSubject.value): string {
    if (this.isFleetUser(user)) return '/fleet/control-center';
    if (this.isParkingUser(user)) return '/parking/dashboard';
    return '/dashboard';
  }

  private setSession(response: LoginResponse): void {
    this.tokenSubject.next(response.token);
    const refreshToken = response.refreshToken;
    if (refreshToken) {
      this.refreshTokenSubject.next(refreshToken);
    }
    this.userSubject.next(response.user);
    this.userSignal.set(response.user);
    this.isAuthenticatedSignal.set(true);
    this.sessionLock.unlock();
    try {
      localStorage.setItem(PARKPE_TOKEN_KEY, response.token);
      if (refreshToken) {
        localStorage.setItem(PARKPE_REFRESH_TOKEN_KEY, refreshToken);
      }
      localStorage.setItem(PARKPE_USER_KEY, JSON.stringify(response.user));
    } catch {
      // localStorage full or disabled – session will be lost on reload
    }
    this.startInactivityTimer();
  }

  /** Set session from Connect scanner verify-otp (same shape as login). */
  setSessionFromConnectScanner(response: { token: string; refreshToken?: string; user: User }): void {
    this.setSession({
      token: response.token,
      refreshToken: response.refreshToken,
      user: response.user,
    });
  }

  getToken(): string | null {
    return this.tokenSubject.value;
  }
}
