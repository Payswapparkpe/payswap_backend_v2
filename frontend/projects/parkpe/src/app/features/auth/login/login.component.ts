import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';

/** Indian mobile: 10 digits starting with 6–9 */
const MOBILE_PATTERN = /^[6-9]\d{9}$/;
/** OTP: 6 digits */
const OTP_PATTERN = /^\d{6}$/;

/**
 * Login Component
 * User authentication – email + password, or mobile + OTP (sent via Kaleyra SMS)
 */
@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private notification = inject(NotificationService);
  private cdr = inject(ChangeDetectorRef);

  loginForm: FormGroup;
  loading = false;
  sendingOtp = false;
  showPassword = false;
  /** 'email' | 'mobile' – mobile is primary (default), email secondary */
  loginMode: 'email' | 'mobile' = 'mobile';
  /** After Send OTP success, show OTP input and Verify button */
  otpSent = false;

  constructor() {
    this.loginForm = this.fb.group({
      email: ['', []],
      phone: ['', []],
      password: ['', []],
      otp: ['', []],
      rememberMe: [false],
    });
    this.setLoginMode('mobile');
  }

  get email() {
    return this.loginForm.get('email');
  }

  get phone() {
    return this.loginForm.get('phone');
  }

  get password() {
    return this.loginForm.get('password');
  }

  get otp() {
    return this.loginForm.get('otp');
  }

  setLoginMode(mode: 'email' | 'mobile') {
    this.loginMode = mode;
    this.otpSent = false;
    this.loginForm.get('email')?.setErrors(null);
    this.loginForm.get('phone')?.setErrors(null);
    this.loginForm.get('otp')?.setValue('');
    this.loginForm.get('otp')?.clearValidators();
    this.loginForm.get('email')?.updateValueAndValidity();
    this.loginForm.get('phone')?.updateValueAndValidity();
    this.loginForm.get('otp')?.updateValueAndValidity();
    if (mode === 'email') {
      this.loginForm.get('email')?.setValidators([Validators.required, Validators.email]);
      this.loginForm.get('phone')?.clearValidators();
      this.loginForm.get('phone')?.setValue('');
      this.loginForm.get('password')?.setValidators([Validators.required, Validators.minLength(6)]);
    } else {
      this.loginForm.get('email')?.clearValidators();
      this.loginForm.get('email')?.setValue('');
      this.loginForm.get('phone')?.setValidators([Validators.required, Validators.pattern(MOBILE_PATTERN)]);
      this.loginForm.get('password')?.clearValidators();
    }
    this.loginForm.get('email')?.updateValueAndValidity();
    this.loginForm.get('phone')?.updateValueAndValidity();
  }

  togglePasswordVisibility() {
    this.showPassword = !this.showPassword;
  }

  /** Normalize phone to 91XXXXXXXXXX for API */
  private normalizePhone(value: string): string {
    const digits = value.replace(/\D/g, '');
    if (digits.length === 10 && /^[6-9]/.test(digits)) return '91' + digits;
    if (digits.length === 12 && digits.startsWith('91')) return digits;
    return value;
  }

  /** Send OTP to mobile (mobile tab, step 1). Uses Kaleyra on backend. */
  sendOtp() {
    this.loginForm.get('phone')?.markAsTouched();
    if (!this.loginForm.get('phone')?.value?.trim()) {
      this.loginForm.get('phone')?.setErrors({ required: true });
      return;
    }
    if (this.phone?.invalid) {
      this.loginForm.get('phone')?.markAsTouched();
      return;
    }
    const phoneNorm = this.normalizePhone(this.loginForm.get('phone')?.value || '');
    this.sendingOtp = true;
    this.authService.requestLoginOtp(phoneNorm).subscribe({
      next: () => {
        this.sendingOtp = false;
        this.otpSent = true;
        this.loginForm.get('otp')?.setValidators([Validators.required, Validators.pattern(OTP_PATTERN)]);
        this.cdr.detectChanges();
        this.notification.showSuccess('OTP sent to your mobile. Enter it below.');
      },
      error: (err) => {
        this.sendingOtp = false;
        this.cdr.detectChanges();
        const msg = err?.error?.detail || err?.error?.message || err?.message || 'Failed to send OTP. Try again.';
        this.notification.showError(msg);
      },
    });
  }

  /** Masked phone for display (e.g. 98****3210) */
  getMaskedPhone(): string {
    const v = this.loginForm.get('phone')?.value as string;
    if (!v || v.length < 6) return 'your number';
    return v.slice(0, 2) + '****' + v.slice(-4);
  }

  /**
   * After login: deep-link if auth guard stored returnUrl, else customer dashboard
   * (or fleet control center for fleet accounts — see AuthService.getPostLoginRoute).
   */
  private navigateAfterLogin(): void {
    const raw = this.route.snapshot.queryParamMap.get('returnUrl')?.trim() ?? '';
    if (
      raw.length > 0 &&
      raw.startsWith('/') &&
      !raw.startsWith('//') &&
      !raw.includes('://')
    ) {
      void this.router.navigateByUrl(raw);
      return;
    }
    void this.router.navigateByUrl(this.authService.getPostLoginRoute());
  }

  /** Back from OTP step to change mobile number */
  backToMobileInput() {
    this.otpSent = false;
    this.loginForm.get('otp')?.setValue('');
    this.loginForm.get('otp')?.clearValidators();
    this.loginForm.get('otp')?.updateValueAndValidity();
    this.cdr.detectChanges();
  }

  onSubmit() {
    if (this.loginMode === 'mobile') {
      if (!this.otpSent) {
        this.sendOtp();
        return;
      }
      this.loginForm.get('phone')?.markAsTouched();
      this.loginForm.get('otp')?.markAsTouched();
      if (this.loginForm.get('otp')?.invalid || !this.loginForm.get('otp')?.value?.trim()) {
        this.loginForm.get('otp')?.setErrors(this.loginForm.get('otp')?.errors || { required: true });
        return;
      }
      const phoneNorm = this.normalizePhone(this.loginForm.get('phone')?.value || '');
      const otp = (this.loginForm.get('otp')?.value || '').trim();
      this.loading = true;
      this.authService.verifyLoginOtp(phoneNorm, otp).subscribe({
        next: () => {
          this.loading = false;
          this.cdr.detectChanges();
          this.notification.showSuccess('Login successful!');
          this.navigateAfterLogin();
        },
        error: (err) => {
          this.loading = false;
          this.cdr.detectChanges();
          const msg = err?.error?.detail || err?.error?.message || err?.message || 'Invalid or expired OTP. Try again.';
          this.notification.showError(msg);
        },
      });
      return;
    }

    this.loginForm.get('email')?.markAsTouched();
    this.loginForm.get('password')?.markAsTouched();
    if (this.loginForm.invalid) {
      Object.keys(this.loginForm.controls).forEach(key => {
        this.loginForm.get(key)?.markAsTouched();
      });
      return;
    }

    this.loading = true;
    const raw = this.loginForm.value;
    const credentials = {
      email: raw.email?.trim(),
      password: raw.password,
      rememberMe: raw.rememberMe,
    };

    const login$ = this.authService.login(credentials);

    login$.subscribe({
      next: () => {
        this.loading = false;
        this.cdr.detectChanges();
        this.notification.showSuccess('Login successful!');
        this.navigateAfterLogin();
      },
      error: (error) => {
        this.loading = false;
        this.cdr.detectChanges();
        const msg = error?.error?.detail || error?.error?.message || error?.message || 'Login failed. Please try again.';
        this.notification.showError(msg);
      },
    });
  }
}
