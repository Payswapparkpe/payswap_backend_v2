// User Model
export interface User {
  id: string;
  name: string;
  email: string;
  phone: string;
  role?: 'user' | 'admin' | 'partner' | 'fleet' | 'parking';
  roleCode?: string;
  avatar?: string;
  emailVerified?: boolean;
  phoneVerified?: boolean;
  createdAt?: Date | string;
  updatedAt?: Date | string;
  languagePreference?: string;
  timezone?: string;
  currencyPreference?: string;
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  state?: string;
  pincode?: string;
  countryOfResidence?: string;
  profileType?: 'individual' | 'business' | 'corporate';
  businessName?: string;
  businessRegistrationNumber?: string;
  businessType?: string;
  gstNumber?: string;
  taxId?: string;
  billingAddressComplete?: boolean;
  notificationPreferences?: {
    push?: boolean;
    email?: boolean;
    sms?: boolean;
    in_app?: boolean;
    quiet_hours_enabled?: boolean;
    quiet_hours_start?: string;
    quiet_hours_end?: string;
    critical_alert_override?: boolean;
  };
  settings?: Record<string, unknown>;
}

// Auth Requests – login by email + password or phone + password
export interface LoginRequest {
  email?: string;
  phone?: string;
  password: string;
  rememberMe?: boolean;
}

export interface LoginResponse {
  token: string;
  refreshToken?: string;
  user: User;
  expiresIn?: number;
}

export interface RegisterRequest {
  name: string;
  email: string;
  phone: string;
  password: string;
  confirmPassword: string;
  acceptTerms: boolean;
  marketingConsent?: boolean;
  /** Address from pincode lookup (optional) */
  pincode?: string;
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  state?: string;
}

/** Single address record from data.gov.in pincode API */
export interface PincodeAddress {
  state: string;
  district: string;
  city: string;
  taluk: string;
  officename: string;
  area: string;
  division?: string;
  region?: string;
  circle?: string;
  pincode: string;
}

export interface PincodeLookupResponse {
  pincode: string;
  addresses: PincodeAddress[];
}

export interface RegisterResponse {
  message: string;
  userId: string;
  requiresVerification?: boolean;
}

/** Request to send OTP during registration (same as RegisterRequest). */
export interface RegisterSendOtpRequest extends RegisterRequest {}

/** Response from register send-otp. */
export interface RegisterSendOtpResponse {
  message: string;
  expires_in: number;
}

/** Request to complete registration with OTP verification. */
export interface RegisterVerifyRequest extends RegisterRequest {
  otp: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ForgotPasswordResponse {
  message: string;
  resetTokenSent: boolean;
}

export interface ResetPasswordRequest {
  token: string;
  newPassword: string;
  confirmPassword: string;
}

export interface VerifyEmailRequest {
  token: string;
  email: string;
}

export interface RefreshTokenRequest {
  refreshToken: string;
}

export interface RefreshTokenResponse {
  token: string;
  expiresIn: number;
}

// Auth State (for NgRx)
export interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  tokenExpiry: Date | null;
}

// Consent
export interface UserConsent {
  termsAccepted: boolean;
  termsAcceptedAt?: Date | string;
  privacyPolicyAccepted: boolean;
  privacyPolicyAcceptedAt?: Date | string;
  marketingConsent?: boolean;
  marketingConsentAt?: Date | string;
}
