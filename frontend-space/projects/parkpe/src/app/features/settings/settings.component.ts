import { Component, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ThemeService, Theme } from '../../core/services/theme.service';
import { AuthService } from '../../core/services/auth.service';
import { Router, RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';
import { SettingsLanguageSectionComponent } from './settings-language-section/settings-language-section.component';
import { SettingsNotificationsSectionComponent } from './settings-notifications-section/settings-notifications-section.component';
import { SettingsAccountSectionComponent } from './settings-account-section/settings-account-section.component';
import { SettingsAboutSectionComponent } from './settings-about-section/settings-about-section.component';
import { SessionLockService } from '../../core/services/session-lock.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    SettingsLanguageSectionComponent,
    SettingsNotificationsSectionComponent,
    SettingsAccountSectionComponent,
    SettingsAboutSectionComponent,
  ],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
})
export class SettingsComponent {
  private themeService = inject(ThemeService);
  private authService = inject(AuthService);
  private router = inject(Router);
  private lock = inject(SessionLockService);
  private notify = inject(NotificationService);
  private fb = inject(FormBuilder);

  currentTheme = this.themeService.theme;
  user = this.authService.userSignal;

  selectedLanguage = environment.app.defaultLanguage;
  supportedLanguages = environment.app.supportedLanguages;
  appVersion = environment.appVersion;
  useMockApi = environment.useMockApi;

  pushEnabled = false;
  emailEnabled = true;
  hasSessionPin = this.lock.hasPin;
  pinTitle = computed(() => (this.hasSessionPin() ? 'Reset Session PIN' : 'Set Session PIN'));

  pinForm = this.fb.nonNullable.group({
    currentPin: [''],
    newPin: ['', [Validators.required, Validators.pattern(/^\d{4,6}$/)]],
    confirmPin: ['', [Validators.required]],
  });
  forgotPinForm = this.fb.nonNullable.group({
    otp: ['', [Validators.required, Validators.pattern(/^\d{4,6}$/)]],
    newPin: ['', [Validators.required, Validators.pattern(/^\d{4,6}$/)]],
    confirmPin: ['', [Validators.required]],
  });
  otpSent = false;
  otpSending = false;
  otpVerifying = false;

  setTheme(theme: Theme) {
    this.themeService.setTheme(theme);
  }

  changeLanguage(value: string) {
    this.selectedLanguage = value;
  }

  togglePush() {
    this.pushEnabled = !this.pushEnabled;
  }

  toggleEmail() {
    this.emailEnabled = !this.emailEnabled;
  }

  logout() {
    if (confirm('Are you sure you want to sign out?')) {
      this.authService.logout();
    }
  }

  saveSessionPin() {
    const { currentPin, newPin, confirmPin } = this.pinForm.getRawValue();
    if (this.pinForm.invalid) {
      this.notify.showError('PIN must be 4 to 6 digits.');
      return;
    }
    if (newPin !== confirmPin) {
      this.notify.showError('New PIN and confirm PIN must match.');
      return;
    }
    if (this.hasSessionPin() && !this.lock.verifyPin(currentPin.trim())) {
      this.notify.showError('Current PIN is incorrect.');
      return;
    }
    if (this.lock.setPin(newPin.trim())) {
      this.notify.showSuccess(this.hasSessionPin() ? 'Session PIN updated.' : 'Session PIN set.');
      this.pinForm.reset({ currentPin: '', newPin: '', confirmPin: '' });
      return;
    }
    this.notify.showError('Unable to save PIN. Please try again.');
  }

  requestForgotPinOtp() {
    const phone = this.getUserPhone();
    if (!phone) {
      this.notify.showError('Phone number not found in profile.');
      return;
    }
    this.otpSending = true;
    this.authService.requestLoginOtp(phone).subscribe({
      next: () => {
        this.otpSending = false;
        this.otpSent = true;
        this.notify.showSuccess('OTP sent to your registered mobile.');
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.otpSending = false;
        this.notify.showError(err?.error?.detail || err?.message || 'Failed to send OTP.');
      },
    });
  }

  resetPinWithOtp() {
    if (this.forgotPinForm.invalid) {
      this.notify.showError('Enter valid OTP and 4-6 digit PIN.');
      return;
    }
    const { otp, newPin, confirmPin } = this.forgotPinForm.getRawValue();
    if (newPin !== confirmPin) {
      this.notify.showError('New PIN and confirm PIN must match.');
      return;
    }
    const phone = this.getUserPhone();
    if (!phone) {
      this.notify.showError('Phone number not found in profile.');
      return;
    }

    this.otpVerifying = true;
    this.authService.verifyLoginOtp(phone, otp).subscribe({
      next: () => {
        this.otpVerifying = false;
        if (!this.lock.setPin(newPin.trim())) {
          this.notify.showError('OTP verified, but PIN could not be saved.');
          return;
        }
        this.lock.unlock();
        this.notify.showSuccess('PIN reset successful.');
        this.forgotPinForm.reset({ otp: '', newPin: '', confirmPin: '' });
        this.otpSent = false;
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.otpVerifying = false;
        this.notify.showError(err?.error?.detail || err?.message || 'OTP verification failed.');
      },
    });
  }

  private getUserPhone(): string {
    const u = this.user();
    if (!u) return '';
    const anyUser = u as { phone?: string; mobile?: string; mobileNumber?: string };
    return (anyUser.phone || anyUser.mobile || anyUser.mobileNumber || '').trim();
  }
}
