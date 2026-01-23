# Authentication Documentation

## Overview

Portal uses Django session authentication with Multi-Factor Authentication (MFA) support.

## Authentication Flow

1. **Sign In**: Username + Password
2. **MFA Check**: If role requires MFA, verify MFA setup
3. **MFA Verification**: OTP or Authenticator code
4. **Session Creation**: Create Django session
5. **Dashboard Redirect**: Route to role-specific dashboard

## MFA Enforcement

**Enforced Roles**: Admin, Employee, Super, Distributor

These roles **must** configure MFA before they can login. The system will:
1. Check MFA configuration on login
2. Redirect to MFA setup if not configured
3. Block dashboard access until MFA is set up

## MFA Methods

1. **OTP (SMS)**: Receive 6-digit code via SMS (Kaleyra)
2. **Authenticator App**: Use TOTP authenticator (Google Authenticator, Authy, etc.)

## User Requirements

Before login, users must have:
- Active account (`is_active = True`)
- Verified email (`email_verified = True`)
- MFA configured (if role requires it)
- KYC completed (if role requires it)
