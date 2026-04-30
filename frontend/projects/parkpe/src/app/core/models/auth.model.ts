/**
 * Re-export auth types from the shared library so ParkPe stays aligned with a single source of truth.
 * Prefer: `import { User } from 'shared'`.
 */
export type {
  User,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  RegisterSendOtpRequest,
  RegisterSendOtpResponse,
  RegisterVerifyRequest,
  PincodeAddress,
  PincodeLookupResponse,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
  ResetPasswordRequest,
  VerifyEmailRequest,
  RefreshTokenRequest,
  RefreshTokenResponse,
  AuthState,
  UserConsent,
} from 'shared';
