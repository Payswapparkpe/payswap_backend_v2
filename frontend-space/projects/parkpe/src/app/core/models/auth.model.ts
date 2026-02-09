// User Model
export interface User {
  id: string;
  name: string;
  email: string;
  phone: string;
  role?: 'user' | 'admin';
  avatar?: string;
  emailVerified?: boolean;
  phoneVerified?: boolean;
  createdAt?: Date | string;
  updatedAt?: Date | string;
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
}

export interface RegisterResponse {
  message: string;
  userId: string;
  requiresVerification?: boolean;
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
