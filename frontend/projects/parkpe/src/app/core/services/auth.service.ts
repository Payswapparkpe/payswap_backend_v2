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

/** Consumer / parking-operator / fleet sessions are stored separately so one role never overwrites another. */
export type AuthPortal = 'consumer' | 'parking' | 'fleet';

const STORAGE: Record<AuthPortal, { token: string; refresh: string; user: string }> = {
  consumer: { token: 'parkpe_c_token', refresh: 'parkpe_c_refresh', user: 'parkpe_c_user' },
  parking: { token: 'parkpe_p_token', refresh: 'parkpe_p_refresh', user: 'parkpe_p_user' },
  fleet: { token: 'parkpe_f_token', refresh: 'parkpe_f_refresh', user: 'parkpe_f_user' },
};

/** Legacy single-namespace keys (migrated once into STORAGE.consumer). */
const LEGACY = {
  token: 'parkpe_auth_token',
  refresh: 'parkpe_refresh_token',
  user: 'parkpe_auth_user',
  portal: 'parkpe_auth_portal',
} as const;

const ACTIVE_PORTAL_KEY = 'parkpe_active_portal';
/** Which login screen started this session — drives consumer vs operator shell (`consumerGuard`). */
const PARKPE_AUTH_PORTAL_KEY = 'parkpe_auth_portal';

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

  /** Restore the last active portal’s session; migrates legacy single-key storage once. */
  private restoreSessionFromStorage(): void {
    try {
      this.migrateLegacyStorageIfNeeded();
      const active = this.getActivePortalFromStorage();
      this.loadPortalIntoMemory(active);
    } catch {
      // localStorage not available or disabled
    }
  }

  private migrateLegacyStorageIfNeeded(): void {
    try {
      const legTok = localStorage.getItem(LEGACY.token);
      if (!legTok) return;
      if (localStorage.getItem(STORAGE.consumer.token)) {
        localStorage.removeItem(LEGACY.token);
        localStorage.removeItem(LEGACY.refresh);
        localStorage.removeItem(LEGACY.user);
        return;
      }
      const p = (localStorage.getItem(LEGACY.portal) as AuthPortal) || 'consumer';
      const portal: AuthPortal = p === 'parking' || p === 'fleet' ? p : 'consumer';
      const k = STORAGE[portal];
      localStorage.setItem(k.token, legTok);
      const r = localStorage.getItem(LEGACY.refresh);
      if (r) localStorage.setItem(k.refresh, r);
      const u = localStorage.getItem(LEGACY.user);
      if (u) localStorage.setItem(k.user, u);
      if (!localStorage.getItem(ACTIVE_PORTAL_KEY)) {
        localStorage.setItem(ACTIVE_PORTAL_KEY, portal);
      }
      localStorage.removeItem(LEGACY.token);
      localStorage.removeItem(LEGACY.refresh);
      localStorage.removeItem(LEGACY.user);
    } catch {
      // ignore
    }
  }

  private getActivePortalFromStorage(): AuthPortal {
    try {
      const a = localStorage.getItem(ACTIVE_PORTAL_KEY) as AuthPortal;
      if (a === 'parking' || a === 'fleet' || a === 'consumer') return a;
    } catch {
      // ignore
    }
    return 'consumer';
  }

  /** Load a namespace into in-memory subjects (e.g. when opening /hub with a stored parking session). */
  activatePortal(portal: AuthPortal): void {
    this.loadPortalIntoMemory(portal);
  }

  private loadPortalIntoMemory(portal: AuthPortal): void {
    try {
      const k = STORAGE[portal];
      const token = localStorage.getItem(k.token);
      const refreshToken = localStorage.getItem(k.refresh);
      const userJson = localStorage.getItem(k.user);
      if (token && token.length > 0) {
        this.tokenSubject.next(token);
        this.refreshTokenSubject.next(refreshToken && refreshToken.length > 0 ? refreshToken : null);
        this.isAuthenticatedSignal.set(true);
        if (userJson) {
          try {
            const user = JSON.parse(userJson) as User;
            this.userSubject.next(user);
            this.userSignal.set(user);
          } catch {
            this.userSubject.next(null);
            this.userSignal.set(null);
          }
        } else {
          this.userSubject.next(null);
          this.userSignal.set(null);
        }
        localStorage.setItem(ACTIVE_PORTAL_KEY, portal);
        localStorage.setItem(PARKPE_AUTH_PORTAL_KEY, portal);
        this.startInactivityTimer();
      } else {
        this.tokenSubject.next(null);
        this.refreshTokenSubject.next(null);
        this.userSubject.next(null);
        this.userSignal.set(null);
        this.isAuthenticatedSignal.set(false);
      }
    } catch {
      // ignore
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
        this.setSession(response, 'fleet');
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
        // Parking login endpoint already authorizes parking access on backend.
        // Normalize user payload so frontend guards always route to parking area.
        const normalizedUser = this.normalizeParkingUser(response.user);
        this.setSession({ ...response, user: normalizedUser }, 'parking');
        this.logger.info('parking_login_success', {
          service: 'auth',
          action: 'parking_login_success',
          userId: normalizedUser?.id,
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
    const portal = this.getAuthPortal();
    this.api.logout().subscribe({
      next: () => {
        this.clearSession();
        this.router.navigate([this.getLoginPathForPortal(portal)]);
      },
      error: () => {
        this.clearSession();
        this.router.navigate([this.getLoginPathForPortal(portal)]);
      },
    });
  }

  getLoginPathForPortal(portal: AuthPortal): string {
    if (portal === 'parking') return '/auth/parking';
    if (portal === 'fleet') return '/fleet/login';
    return '/auth/login';
  }

  /** Remove one portal’s stored tokens (e.g. after 403). If it was active, clear in-memory session too. */
  clearSessionForPortal(portal: AuthPortal): void {
    try {
      const k = STORAGE[portal];
      localStorage.removeItem(k.token);
      localStorage.removeItem(k.refresh);
      localStorage.removeItem(k.user);
    } catch {
      // ignore
    }
    if (this.getActivePortalFromStorage() === portal) {
      this.clearSession();
    }
  }

  parkingLogout(): void {
    this.clearSession();
    this.router.navigate(['/auth/parking']);
  }

  /**
   * Clear the active portal session (memory + that namespace in localStorage).
   * Call on logout and on 401 when refresh fails.
   */
  clearSession(): void {
    this.stopInactivityTimer();
    const portal = this.getActivePortalFromStorage();
    this.tokenSubject.next(null);
    this.refreshTokenSubject.next(null);
    this.userSubject.next(null);
    this.userSignal.set(null);
    this.isAuthenticatedSignal.set(false);
    this.sessionLock.unlock();
    try {
      const k = STORAGE[portal];
      localStorage.removeItem(k.token);
      localStorage.removeItem(k.refresh);
      localStorage.removeItem(k.user);
      localStorage.removeItem(ACTIVE_PORTAL_KEY);
      localStorage.removeItem(PARKPE_AUTH_PORTAL_KEY);
    } catch {
      // ignore
    }
  }

  /**
   * `consumer` = `/auth/login` (or register/OTP).
   * `parking` = `/auth/parking` — `consumerGuard` redirects away from AppLayout.
   * `fleet` = `/fleet/login`.
   */
  getAuthPortal(): AuthPortal {
    try {
      const p = localStorage.getItem(PARKPE_AUTH_PORTAL_KEY);
      if (p === 'parking' || p === 'fleet') return p;
    } catch {
      // ignore
    }
    return 'consumer';
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
    const v = this.refreshTokenSubject.value;
    if (v) return v;
    try {
      const portal = this.getActivePortalFromStorage();
      return localStorage.getItem(STORAGE[portal].refresh);
    } catch {
      return null;
    }
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
            const portal = this.getActivePortalFromStorage();
            localStorage.setItem(STORAGE[portal].token, access);
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
          const portal = this.getActivePortalFromStorage();
          localStorage.setItem(STORAGE[portal].user, JSON.stringify(user));
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
          const portal = this.getActivePortalFromStorage();
          localStorage.setItem(STORAGE[portal].user, JSON.stringify(user));
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
    const roleCode = String((user as unknown as { roleCode?: string; role_code?: string })?.roleCode || (user as unknown as { role_code?: string })?.role_code || '').toLowerCase();
    const role = String((user as unknown as { role?: string })?.role || '').toLowerCase();
    const parkingRole = String((user as unknown as { parkingRole?: string })?.parkingRole || '').toLowerCase();
    return roleCode.startsWith('parking_') || role === 'parking' || ['owner', 'manager', 'attendant'].includes(parkingRole);
  }

  /**
   * Default landing for guards / “already logged in” redirects.
   * Uses auth portal: parking sessions → hub; others → consumer dashboard (unless fleet).
   */
  getPostLoginRoute(user: User | null | undefined = this.userSubject.value): string {
    if (this.isFleetUser(user)) return '/fleet/control-center';
    if (this.getAuthPortal() === 'fleet') return '/fleet/control-center';
    if (this.getAuthPortal() === 'parking') return '/hub/parking/dashboard';
    return '/dashboard';
  }

  getParkingRole(user: User | null | undefined = this.userSubject.value): 'owner' | 'manager' | 'attendant' | null {
    const role = String((user as unknown as { parkingRole?: string })?.parkingRole || '').toLowerCase();
    if (role === 'owner' || role === 'manager' || role === 'attendant') return role;
    return null;
  }

  private setSession(response: LoginResponse, portal: AuthPortal = 'consumer'): void {
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
      const k = STORAGE[portal];
      localStorage.setItem(k.token, response.token);
      if (refreshToken) {
        localStorage.setItem(k.refresh, refreshToken);
      }
      localStorage.setItem(k.user, JSON.stringify(response.user));
      localStorage.setItem(PARKPE_AUTH_PORTAL_KEY, portal);
      localStorage.setItem(ACTIVE_PORTAL_KEY, portal);
    } catch {
      // localStorage full or disabled – session will be lost on reload
    }
    this.startInactivityTimer();
  }

  private normalizeParkingUser(user: User): User {
    const anyUser = user as User & { role_code?: string; roleCode?: string; parkingRole?: 'owner' | 'manager' | 'attendant' | null };
    const existingRoleCode = String(anyUser.roleCode || anyUser.role_code || '').trim();
    const normalizedRoleCode = existingRoleCode || 'parking_operator';
    return {
      ...user,
      role: 'parking',
      roleCode: normalizedRoleCode,
    };
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

  /** JWT for the request: picks the namespace matching route + URL so hub/fleet APIs get the right token. */
  getTokenForHttpRequest(requestUrl: string, routerUrl: string): string | null {
    const portal = this.inferPortalFromUrls(requestUrl, routerUrl);
    try {
      const t = localStorage.getItem(STORAGE[portal].token);
      if (t) return t;
    } catch {
      // ignore
    }
    return this.tokenSubject.value;
  }

  inferPortalFromUrls(requestUrl: string, routerUrl: string): AuthPortal {
    const path = (routerUrl || '').split('?')[0];
    if (path.startsWith('/hub') || path.startsWith('/auth/parking')) return 'parking';
    if (path.startsWith('/fleet')) return 'fleet';
    const u = requestUrl.toLowerCase();
    if (u.includes('/parking/owner') || u.includes('/owner/locations') || u.includes('/owner/revenue') || u.includes('/owner/bookings')) {
      return 'parking';
    }
    if (u.includes('/dashboard/fleet') || u.includes('/auth/fleet') || u.includes('fleet/vehicles') || u.includes('fleet/drivers')) {
      return 'fleet';
    }
    return 'consumer';
  }
}
