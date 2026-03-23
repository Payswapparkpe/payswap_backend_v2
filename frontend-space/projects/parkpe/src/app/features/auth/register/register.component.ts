import { Component, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AbstractControl, FormBuilder, FormGroup, ValidationErrors, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';
import type { RegisterRequest, RegisterVerifyRequest, PincodeAddress } from 'shared';

function passwordsMatchValidator(control: AbstractControl): ValidationErrors | null {
  const password = control.get('password')?.value;
  const confirmPassword = control.get('confirmPassword')?.value;
  if (!password || !confirmPassword) return null;
  return password === confirmPassword ? null : { passwordsMismatch: true };
}

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './register.component.html',
  styleUrl: './register.component.scss',
})
export class RegisterComponent {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private router = inject(Router);
  private notification = inject(NotificationService);
  private cdr = inject(ChangeDetectorRef);

  registerForm: FormGroup;
  otpForm: FormGroup;
  loading = false;
  showPassword = false;
  showConfirmPassword = false;

  /** Current step: 1 = details form, 2 = OTP verification */
  step = 1;
  /** Pending registration payload (set after step 1) for verify call */
  pendingPayload: RegisterRequest | null = null;
  /** Masked phone for display on step 2 */
  maskedPhone = '';
  /** Resend OTP countdown seconds (0 = can resend) */
  resendCountdown = 0;
  private resendTimer: ReturnType<typeof setInterval> | null = null;

  /** Loading state for pincode lookup only */
  pincodeLoading = false;
  /** Addresses from pincode lookup – show in dropdown for user to choose */
  pincodeAddresses: PincodeAddress[] = [];
  /** Selected address index from dropdown (-1 = none selected) */
  selectedPincodeAddressIndex: number = -1;

  constructor() {
    this.registerForm = this.fb.group(
      {
        name: ['', Validators.required],
        email: ['', [Validators.required, Validators.email]],
        phone: ['', [Validators.required, Validators.minLength(10), Validators.pattern(/^\d{10}$/)]],
        password: ['', [Validators.required, Validators.minLength(6)]],
        confirmPassword: ['', Validators.required],
        acceptTerms: [false, Validators.requiredTrue],
        pincode: ['', [Validators.pattern(/^\d{6}$/)]],
        addressLine1: [''],
        addressLine2: [''],
        city: [''],
        state: [''],
      },
      { validators: passwordsMatchValidator }
    );
    this.otpForm = this.fb.group({
      otp: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(6), Validators.pattern(/^\d{6}$/)]],
    });
  }

  get name() { return this.registerForm.get('name'); }
  get email() { return this.registerForm.get('email'); }
  get phone() { return this.registerForm.get('phone'); }
  get password() { return this.registerForm.get('password'); }
  get confirmPassword() { return this.registerForm.get('confirmPassword'); }
  get acceptTerms() { return this.registerForm.get('acceptTerms'); }
  get pincode() { return this.registerForm.get('pincode'); }
  get addressLine1() { return this.registerForm.get('addressLine1'); }
  get city() { return this.registerForm.get('city'); }
  get state() { return this.registerForm.get('state'); }
  get otp() { return this.otpForm.get('otp'); }

  togglePasswordVisibility() {
    this.showPassword = !this.showPassword;
  }

  toggleConfirmPasswordVisibility() {
    this.showConfirmPassword = !this.showConfirmPassword;
  }

  /** Fetch addresses from pincode (data.gov.in) and show in dropdown */
  fetchAddressByPincode() {
    const pin = (this.pincode?.value ?? '').toString().trim();
    if (!pin || pin.length !== 6) {
      this.notification.showError('Enter a valid 6-digit pincode.');
      this.pincode?.markAsTouched();
      return;
    }
    this.pincodeLoading = true;
    this.pincodeAddresses = [];
    this.selectedPincodeAddressIndex = -1;
    this.authService.lookupPincode(pin).subscribe({
      next: (res) => {
        this.setPincodeLoadingFalse();
        if (!res.addresses?.length) {
          this.notification.showWarning('No address found for this pincode.');
          return;
        }
        this.pincodeAddresses = res.addresses;
        this.registerForm.patchValue({
          pincode: pin,
          addressLine1: '',
          city: '',
          state: '',
        });
        this.notification.showSuccess(
          `Found ${res.addresses.length} area(s). Select your area / post office from the list below.`
        );
      },
      error: (err) => {
        this.setPincodeLoadingFalse();
        const msg = err?.error?.detail || err?.error?.message || 'Could not fetch address.';
        this.notification.showError(msg);
      },
    });
  }

  /** Display label for one address in dropdown (e.g. "Post Office Name, District, State") */
  getPincodeAddressLabel(addr: PincodeAddress, index: number): string {
    const parts: string[] = [];
    if (addr.officename) parts.push(addr.officename);
    if (addr.district && addr.district !== addr.officename) parts.push(addr.district);
    if (addr.state) parts.push(addr.state);
    if (parts.length === 0) return `Address ${index + 1}`;
    return parts.join(', ');
  }

  /** User selected an address from dropdown – fill form (Address line 1 = area/post office from API; saved in DB) */
  selectPincodeAddress(index: number) {
    if (index < 0 || index >= this.pincodeAddresses.length) return;
    this.selectedPincodeAddressIndex = index;
    const addr = this.pincodeAddresses[index];
    const areaOrPostOffice = addr.officename || addr.area || addr.taluk || '';
    this.registerForm.patchValue({
      addressLine1: areaOrPostOffice,
      state: addr.state || '',
      city: addr.city || addr.district || '',
    });
    this.cdr.detectChanges();
  }

  /** Defer loading state update and run CD in next tick to avoid ExpressionChangedAfterItHasBeenCheckedError */
  private setPincodeLoadingFalse() {
    setTimeout(() => {
      this.pincodeLoading = false;
      this.cdr.detectChanges();
    }, 0);
  }

  /** Step 1: Send OTP to mobile */
  onSubmitDetails() {
    if (this.registerForm.invalid) {
      Object.keys(this.registerForm.controls).forEach(key => {
        this.registerForm.get(key)?.markAsTouched();
      });
      return;
    }

    const payload: RegisterRequest = this.registerForm.value;
    this.loading = true;
    this.authService.registerSendOtp(payload).subscribe({
      next: () => {
        this.loading = false;
        this.pendingPayload = payload;
        this.maskedPhone = this.maskPhone(payload.phone);
        this.step = 2;
        this.otpForm.reset();
        this.startResendCountdown();
        this.notification.showSuccess('OTP sent to your mobile number.');
      },
      error: (err) => {
        this.loading = false;
        const msg = err?.error?.message || err?.error?.detail || 'Failed to send OTP.';
        this.notification.showError(msg);
      },
    });
  }

  /** Step 2: Verify OTP and create account */
  onSubmitOtp() {
    if (!this.pendingPayload || this.otpForm.invalid) {
      this.otp?.markAsTouched();
      return;
    }

    const verifyPayload: RegisterVerifyRequest = {
      ...this.pendingPayload,
      otp: this.otpForm.value.otp,
    };
    this.loading = true;
    this.authService.registerVerify(verifyPayload).subscribe({
      next: () => {
        this.loading = false;
        this.notification.showSuccess('Account created successfully!');
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.loading = false;
        const msg = err?.error?.message || err?.error?.detail || 'Verification failed.';
        this.notification.showError(msg);
      },
    });
  }

  backToDetails() {
    this.step = 1;
    this.stopResendCountdown();
  }

  resendOtp() {
    if (!this.pendingPayload || this.resendCountdown > 0) return;
    this.loading = true;
    this.authService.registerSendOtp(this.pendingPayload).subscribe({
      next: () => {
        this.loading = false;
        this.startResendCountdown();
        this.notification.showSuccess('OTP sent again.');
      },
      error: (err) => {
        this.loading = false;
        const msg = err?.error?.message || err?.error?.detail || 'Failed to resend OTP.';
        this.notification.showError(msg);
      },
    });
  }

  private maskPhone(phone: string): string {
    if (!phone || phone.length < 4) return '****';
    return phone.slice(0, 2) + '****' + phone.slice(-4);
  }

  private startResendCountdown() {
    this.stopResendCountdown();
    this.resendCountdown = 60;
    this.resendTimer = setInterval(() => {
      this.resendCountdown--;
      if (this.resendCountdown <= 0) this.stopResendCountdown();
    }, 1000);
  }

  private stopResendCountdown() {
    if (this.resendTimer) {
      clearInterval(this.resendTimer);
      this.resendTimer = null;
    }
    this.resendCountdown = 0;
  }
}
