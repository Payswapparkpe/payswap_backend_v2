import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ThemeService, Theme } from '../../core/services/theme.service';
import { AuthService } from '../../core/services/auth.service';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import type { User, PincodeLookupResponse } from 'shared';
import { API_BACKEND_TOKEN } from '../../core/constants';
import type { PasskeyCredentialItem } from '../../core/api/api-backend.interface';
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
export class SettingsComponent implements OnInit {
  private themeService = inject(ThemeService);
  private authService = inject(AuthService);
  private router = inject(Router);
  private lock = inject(SessionLockService);
  private notify = inject(NotificationService);
  private fb = inject(FormBuilder);
  private api = inject(API_BACKEND_TOKEN);

  currentTheme = this.themeService.theme;
  user = this.authService.userSignal;

  selectedLanguage = environment.app.defaultLanguage;
  selectedTimezone = 'Asia/Kolkata';
  selectedCurrency = 'INR';
  supportedLanguages = environment.app.supportedLanguages;
  appVersion = environment.appVersion;
  useMockApi = environment.useMockApi;

  pushEnabled = false;
  emailEnabled = true;
  hasSessionPin = this.lock.hasPin;
  hasBiometric = this.lock.hasBiometric;
  pinTitle = computed(() => (this.hasSessionPin() ? 'Reset Session PIN' : 'Set Session PIN'));
  biometricSupported = signal(false);
  biometricBusy = signal(false);
  passkeyCredentials = signal<PasskeyCredentialItem[]>([]);
  passkeyLabels = signal<Record<number, string>>({});
  passkeyListBusy = signal(false);
  passkeyRecoveryOtp = '';
  passkeyRecoveryOtpSent = signal(false);
  passkeyRecoveryBusy = signal(false);
  preferencesSaving = signal(false);
  billingSaving = signal(false);
  pincodeLookupBusy = signal(false);

  billingForm = this.fb.nonNullable.group({
    addressLine1: [''],
    addressLine2: [''],
    city: [''],
    state: [''],
    pincode: [''],
    countryOfResidence: ['India'],
    gstNumber: [''],
  });
  securityOverview = signal<{
    mfa?: { enabled: boolean; configured: boolean; method?: string | null };
    passkey?: { enabled: boolean };
    pinLock?: { pinSet: boolean; fullAuthFresh?: boolean };
    connect?: { blockedUntil?: string | null; warningCount: number };
    devices?: Array<{ id: number; device_platform: string; app_platform: string; is_active: boolean }>;
  } | null>(null);
  securityActivity = signal<Array<{ id: number; source: string; action: string; created_at: string }>>([]);

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

  constructor() {
    void this.refreshBiometricSupport();
  }

  ngOnInit(): void {
    this.hydratePreferencesFromUser();
    this.authService.getProfile().subscribe({
      next: (user) => this.hydratePreferencesFromUser(user),
      error: () => {},
    });
    this.loadSecurityOverview();
    this.loadSecurityActivity();
  }

  setTheme(theme: Theme) {
    this.themeService.setTheme(theme);
  }

  changeLanguage(value: string) {
    this.selectedLanguage = value;
    this.persistPreferenceChanges();
  }

  togglePush() {
    this.pushEnabled = !this.pushEnabled;
    this.persistPreferenceChanges();
  }

  toggleEmail() {
    this.emailEnabled = !this.emailEnabled;
    this.persistPreferenceChanges();
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
    this.authService
      .setSessionPin({
        pin: newPin.trim(),
        currentPin: currentPin.trim() || undefined,
        forceReset: false,
      })
      .subscribe({
        next: () => {
          this.lock.setHasPin(true);
          this.notify.showSuccess(this.hasSessionPin() ? 'Session PIN updated.' : 'Session PIN set.');
          this.pinForm.reset({ currentPin: '', newPin: '', confirmPin: '' });
        },
        error: (err: { error?: { detail?: string }; message?: string }) => {
          this.notify.showError(err?.error?.detail || err?.message || 'Unable to save PIN. Please try again.');
        },
      });
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
        this.authService
          .setSessionPin({ pin: newPin.trim(), forceReset: true })
          .subscribe({
            next: () => {
              this.otpVerifying = false;
              this.lock.setHasPin(true);
              this.lock.unlock();
              this.notify.showSuccess('PIN reset successful.');
              this.forgotPinForm.reset({ otp: '', newPin: '', confirmPin: '' });
              this.otpSent = false;
            },
            error: (pinErr: { error?: { detail?: string }; message?: string }) => {
              this.otpVerifying = false;
              this.notify.showError(pinErr?.error?.detail || pinErr?.message || 'OTP verified but PIN update failed.');
            },
          });
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.otpVerifying = false;
        this.notify.showError(err?.error?.detail || err?.message || 'OTP verification failed.');
      },
    });
  }

  async enableBiometricUnlock() {
    if (this.biometricBusy()) return;
    this.biometricBusy.set(true);
    try {
      const optionsResp = await firstValueFrom(this.authService.getPasskeyRegisterOptions());
      const publicKey = this.mapRegistrationOptions(optionsResp.publicKey);
      const credential = await navigator.credentials.create({ publicKey });
      if (!credential || credential.type !== 'public-key') {
        this.notify.showError('Passkey setup was cancelled.');
        return;
      }
      const serialized = this.serializeRegistrationCredential(credential as PublicKeyCredential);
      await firstValueFrom(this.authService.verifyPasskeyRegistration(serialized));
      this.lock.setPasskeyEnabled(true);
      this.loadPasskeyCredentials();
      this.loadSecurityOverview();
      this.notify.showSuccess('Passkey unlock enabled.');
    } catch (err: unknown) {
      const apiErr = err as { error?: { detail?: string }; message?: string };
      this.notify.showError(apiErr?.error?.detail || apiErr?.message || 'Could not enable passkey unlock.');
    } finally {
      this.biometricBusy.set(false);
    }
  }

  disableBiometricUnlock() {
    this.biometricBusy.set(true);
    this.authService.disablePasskey().subscribe({
      next: () => {
        this.biometricBusy.set(false);
        this.lock.setPasskeyEnabled(false);
        this.passkeyCredentials.set([]);
        this.passkeyLabels.set({});
        this.loadSecurityOverview();
        this.notify.showSuccess('Passkey unlock disabled.');
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.biometricBusy.set(false);
        this.notify.showError(err?.error?.detail || err?.message || 'Could not disable passkey.');
      },
    });
  }

  async testBiometricUnlock() {
    if (this.biometricBusy()) return;
    this.biometricBusy.set(true);
    try {
      const optionsResp = await firstValueFrom(this.authService.getPasskeyAuthOptions());
      const publicKey = this.mapAuthenticationOptions(optionsResp.publicKey);
      const assertion = await navigator.credentials.get({ publicKey });
      if (!assertion || assertion.type !== 'public-key') {
        this.notify.showError('Passkey verification was cancelled.');
        return;
      }
      const serialized = this.serializeAuthenticationCredential(assertion as PublicKeyCredential);
      await firstValueFrom(this.authService.verifyPasskeyAuth(serialized));
      this.notify.showSuccess('Passkey verification successful.');
    } catch (err: unknown) {
      const apiErr = err as { error?: { detail?: string }; message?: string };
      this.notify.showError(apiErr?.error?.detail || apiErr?.message || 'Passkey verification failed.');
    } finally {
      this.biometricBusy.set(false);
    }
  }

  savePasskeyLabel(credentialId: number) {
    const label = (this.passkeyLabels()[credentialId] || '').trim();
    if (!label) {
      this.notify.showError('Passkey label cannot be empty.');
      return;
    }
    this.authService.updatePasskeyCredential(credentialId, label).subscribe({
      next: () => {
        this.notify.showSuccess('Passkey name updated.');
        this.loadPasskeyCredentials();
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.notify.showError(err?.error?.detail || err?.message || 'Could not update passkey name.');
      },
    });
  }

  onPasskeyLabelInput(credentialId: number, value: string) {
    const next = { ...this.passkeyLabels() };
    next[credentialId] = value;
    this.passkeyLabels.set(next);
  }

  removePasskeyCredential(credentialId: number) {
    this.authService.deletePasskeyCredential(credentialId).subscribe({
      next: (res) => {
        this.lock.setPasskeyEnabled(!!res.enabled);
        this.notify.showSuccess('Passkey removed.');
        this.loadPasskeyCredentials();
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.notify.showError(err?.error?.detail || err?.message || 'Could not remove passkey.');
      },
    });
  }

  requestPasskeyRecoveryOtp() {
    if (this.passkeyRecoveryBusy()) return;
    this.passkeyRecoveryBusy.set(true);
    this.authService.requestPasskeyRecoveryOtp().subscribe({
      next: () => {
        this.passkeyRecoveryBusy.set(false);
        this.passkeyRecoveryOtpSent.set(true);
        this.notify.showSuccess('Recovery OTP sent to your mobile.');
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.passkeyRecoveryBusy.set(false);
        this.notify.showError(err?.error?.detail || err?.message || 'Could not send recovery OTP.');
      },
    });
  }

  verifyPasskeyRecoveryOtp() {
    if (!/^\d{4,6}$/.test(this.passkeyRecoveryOtp.trim())) {
      this.notify.showError('Enter a valid recovery OTP.');
      return;
    }
    if (this.passkeyRecoveryBusy()) return;
    this.passkeyRecoveryBusy.set(true);
    this.authService.verifyPasskeyRecoveryOtp(this.passkeyRecoveryOtp.trim()).subscribe({
      next: (res) => {
        this.passkeyRecoveryBusy.set(false);
        this.passkeyRecoveryOtp = '';
        this.passkeyRecoveryOtpSent.set(false);
        this.lock.setPasskeyEnabled(false);
        this.passkeyCredentials.set([]);
        this.passkeyLabels.set({});
        this.loadSecurityOverview();
        this.notify.showSuccess(`Passkeys revoked: ${res.revoked}.`);
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.passkeyRecoveryBusy.set(false);
        this.notify.showError(err?.error?.detail || err?.message || 'Recovery OTP verification failed.');
      },
    });
  }

  private async refreshBiometricSupport() {
    this.biometricSupported.set(await this.lock.canUsePasskey());
    this.authService.getPinStatus().subscribe({
      next: (res) => this.lock.setHasPin(!!res.hasPin),
      error: () => this.lock.setHasPin(false),
    });
    this.authService.getPasskeyStatus().subscribe({
      next: (res) => {
        this.lock.setPasskeyEnabled(!!res.enabled);
        if (res.enabled) {
          this.loadPasskeyCredentials();
        } else {
          this.passkeyCredentials.set([]);
          this.passkeyLabels.set({});
        }
      },
      error: () => {
        this.lock.setPasskeyEnabled(false);
        this.passkeyCredentials.set([]);
        this.passkeyLabels.set({});
      },
    });
  }

  private loadPasskeyCredentials() {
    this.passkeyListBusy.set(true);
    this.authService.getPasskeyCredentials().subscribe({
      next: (res) => {
        this.passkeyListBusy.set(false);
        const items = res.items || [];
        this.passkeyCredentials.set(items);
        const labels: Record<number, string> = {};
        for (const item of items) labels[item.id] = item.label || '';
        this.passkeyLabels.set(labels);
      },
      error: () => {
        this.passkeyListBusy.set(false);
        this.passkeyCredentials.set([]);
        this.passkeyLabels.set({});
      },
    });
  }

  savePreferencesManually() {
    this.persistPreferenceChanges(true);
  }

  lookupPinForBilling(): void {
    const pc = (this.billingForm.get('pincode')?.value || '').trim();
    if (!/^\d{6}$/.test(pc)) {
      this.notify.showError('Enter a valid 6-digit PIN code.');
      return;
    }
    if (this.pincodeLookupBusy()) return;
    this.pincodeLookupBusy.set(true);
    this.api.lookupPincode(pc).subscribe({
      next: (res: PincodeLookupResponse) => {
        this.pincodeLookupBusy.set(false);
        const first = res.addresses?.[0];
        if (first) {
          this.billingForm.patchValue({
            state: first.state || '',
            city: first.city || first.district || '',
          });
          this.notify.showSuccess('State and city updated from PIN code.');
        } else {
          this.notify.showWarning('No directory row for this PIN code. You can still enter state manually.');
        }
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.pincodeLookupBusy.set(false);
        this.notify.showError(err?.error?.detail || err?.message || 'PIN lookup failed.');
      },
    });
  }

  saveBillingAddress(): void {
    const user = this.user();
    if (!user || this.billingSaving()) return;
    const v = this.billingForm.getRawValue();
    this.billingSaving.set(true);
    this.authService
      .updateProfile({
        addressLine1: v.addressLine1.trim(),
        addressLine2: v.addressLine2.trim(),
        city: v.city.trim(),
        state: v.state.trim(),
        pincode: v.pincode.trim(),
        countryOfResidence: (v.countryOfResidence || 'India').trim(),
        gstNumber: v.gstNumber.trim(),
      })
      .subscribe({
        next: (u) => {
          this.billingSaving.set(false);
          this.hydratePreferencesFromUser(u);
          this.notify.showSuccess('Billing address saved.');
        },
        error: (err: { error?: { detail?: string }; message?: string }) => {
          this.billingSaving.set(false);
          this.notify.showError(err?.error?.detail || err?.message || 'Could not save billing address.');
        },
      });
  }

  revokeAllSessions() {
    this.authService.revokeSessions().subscribe({
      next: (res) => {
        this.notify.showSuccess(`Revoked ${res.revoked} device session(s).`);
        this.loadSecurityOverview();
        this.loadSecurityActivity();
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.notify.showError(err?.error?.detail || err?.message || 'Unable to revoke sessions.');
      },
    });
  }

  private loadSecurityOverview() {
    this.authService.getSecurityOverview().subscribe({
      next: (res) => this.securityOverview.set(res),
      error: () => this.securityOverview.set(null),
    });
  }

  private loadSecurityActivity() {
    this.authService.getSecurityActivity().subscribe({
      next: (res) => this.securityActivity.set((res.items || []).slice(0, 8)),
      error: () => this.securityActivity.set([]),
    });
  }

  private hydratePreferencesFromUser(userArg?: User | null) {
    const u = userArg ?? this.user();
    if (!u) return;
    this.selectedLanguage = (u.languagePreference || this.selectedLanguage || 'en').toLowerCase();
    this.selectedTimezone = u.timezone || this.selectedTimezone;
    this.selectedCurrency = (u.currencyPreference || this.selectedCurrency || 'INR').toUpperCase();
    const prefs = u.notificationPreferences || {};
    this.pushEnabled = Boolean(prefs.push ?? this.pushEnabled);
    this.emailEnabled = Boolean(prefs.email ?? this.emailEnabled);
    this.billingForm.patchValue({
      addressLine1: u.addressLine1 ?? '',
      addressLine2: u.addressLine2 ?? '',
      city: u.city ?? '',
      state: u.state ?? '',
      pincode: u.pincode ?? '',
      countryOfResidence: u.countryOfResidence ?? 'India',
      gstNumber: u.gstNumber ?? '',
    });
  }

  private persistPreferenceChanges(showSuccessToast = false) {
    const user = this.user();
    if (!user || this.preferencesSaving()) return;
    this.preferencesSaving.set(true);
    this.authService.updateProfile({
      languagePreference: this.selectedLanguage,
      timezone: this.selectedTimezone,
      currencyPreference: this.selectedCurrency,
      notificationPreferences: {
        ...(user.notificationPreferences || {}),
        push: this.pushEnabled,
        email: this.emailEnabled,
      },
      settings: user.settings || {},
    }).subscribe({
      next: () => {
        this.preferencesSaving.set(false);
        if (showSuccessToast) this.notify.showSuccess('Preferences saved.');
      },
      error: (err: { error?: { detail?: string }; message?: string }) => {
        this.preferencesSaving.set(false);
        this.notify.showError(err?.error?.detail || err?.message || 'Could not save preferences.');
      },
    });
  }

  private mapRegistrationOptions(raw: Record<string, unknown>): PublicKeyCredentialCreationOptions {
    const options = { ...(raw as Record<string, unknown>) };
    const user = { ...(options['user'] as Record<string, unknown>) };
    user['id'] = this.base64UrlToBuffer(String(user['id'] || ''));
    options['user'] = user;
    options['challenge'] = this.base64UrlToBuffer(String(options['challenge'] || ''));
    const exclude = Array.isArray(options['excludeCredentials']) ? options['excludeCredentials'] : [];
    options['excludeCredentials'] = exclude.map((item) => ({
      ...(item as Record<string, unknown>),
      id: this.base64UrlToBuffer(String((item as Record<string, unknown>)['id'] || '')),
    }));
    return options as unknown as PublicKeyCredentialCreationOptions;
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

  private serializeRegistrationCredential(credential: PublicKeyCredential): Record<string, unknown> {
    const response = credential.response as AuthenticatorAttestationResponse;
    return {
      id: credential.id,
      rawId: this.bufferToBase64Url(credential.rawId),
      type: credential.type,
      response: {
        attestationObject: this.bufferToBase64Url(response.attestationObject),
        clientDataJSON: this.bufferToBase64Url(response.clientDataJSON),
        transports: typeof response.getTransports === 'function' ? response.getTransports() : [],
      },
      clientExtensionResults: credential.getClientExtensionResults(),
    };
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

  private getUserPhone(): string {
    const u = this.user();
    if (!u) return '';
    const anyUser = u as { phone?: string; mobile?: string; mobileNumber?: string };
    return (anyUser.phone || anyUser.mobile || anyUser.mobileNumber || '').trim();
  }
}
