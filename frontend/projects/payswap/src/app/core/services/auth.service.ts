import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, BehaviorSubject, tap, catchError, throwError } from 'rxjs';
import { API_BACKEND_TOKEN } from '../constants';
import { LoggerService } from './logger.service';
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

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);
  private logger = inject(LoggerService);

  private userSubject = new BehaviorSubject<User | null>(null);
  private tokenSubject = new BehaviorSubject<string | null>(null);

  user$ = this.userSubject.asObservable();
  token$ = this.tokenSubject.asObservable();

  // Signals for reactive state
  userSignal = signal<User | null>(null);
  isAuthenticatedSignal = signal(false);

  constructor() {
    this.restoreSessionFromStorage();
  }

  /** Restore token and user from localStorage so reload keeps user logged in */
  private restoreSessionFromStorage(): void {
    try {
      const token = localStorage.getItem(PARKPE_TOKEN_KEY);
      const userJson = localStorage.getItem(PARKPE_USER_KEY);
      if (token && token.length > 0) {
        this.tokenSubject.next(token);
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

  partnerLogin(credentials: LoginRequest): Observable<LoginResponse> {
    this.logger.info('partner_login_start', { service: 'auth', action: 'partner_login_start' });
    return this.api.partnerLogin(credentials).pipe(
      tap((response) => {
        this.setSession(response);
        this.logger.info('partner_login_success', { service: 'auth', action: 'partner_login_success', userId: response.user?.id });
      }),
      catchError((err) => {
        this.logger.warn('partner_login_error', { service: 'auth', action: 'partner_login_error', status: err?.status });
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

  /** Clear session (memory + localStorage). Call on logout and on 401. */
  clearSession(): void {
    this.tokenSubject.next(null);
    this.userSubject.next(null);
    this.userSignal.set(null);
    this.isAuthenticatedSignal.set(false);
    try {
      localStorage.removeItem(PARKPE_TOKEN_KEY);
      localStorage.removeItem(PARKPE_REFRESH_TOKEN_KEY);
      localStorage.removeItem(PARKPE_USER_KEY);
    } catch {
      // ignore
    }
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

  isAuthenticated(): boolean {
    return !!this.tokenSubject.value;
  }

  isPartnerUser(user: User | null | undefined = this.userSubject.value): boolean {
    const roleCode = String((user as unknown as { roleCode?: string })?.roleCode || '').toLowerCase();
    const role = String((user as unknown as { role?: string })?.role || '').toLowerCase();
    return role === 'partner' || ['super_distributor', 'distributor', 'retailer'].includes(roleCode);
  }

  getPostLoginRoute(user: User | null | undefined = this.userSubject.value): string {
    if (this.isPartnerUser(user)) return '/dashboard';
    return '/dashboard';
  }

  private setSession(response: LoginResponse): void {
    this.tokenSubject.next(response.token);
    this.userSubject.next(response.user);
    this.userSignal.set(response.user);
    this.isAuthenticatedSignal.set(true);
    try {
      localStorage.setItem(PARKPE_TOKEN_KEY, response.token);
      localStorage.setItem(PARKPE_USER_KEY, JSON.stringify(response.user));
      if (response.refreshToken) {
        localStorage.setItem(PARKPE_REFRESH_TOKEN_KEY, response.refreshToken);
      }
    } catch {
      // localStorage full or disabled – session will be lost on reload
    }
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
