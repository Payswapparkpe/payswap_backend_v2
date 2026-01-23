# MFA Setup Documentation

## Overview

Multi-Factor Authentication (MFA) is enforced for Admin, Employee, Super, and Distributor roles.

## Setup Flow

1. User attempts to login
2. System checks if role requires MFA
3. If MFA not configured → Redirect to `/mfa/setup/`
4. User chooses method (OTP or Authenticator)
5. User completes setup
6. MFA configured → User can now login

## OTP Setup

1. Select "OTP via SMS"
2. Enter phone number
3. System sends OTP via Kaleyra
4. Setup complete

## Authenticator Setup

1. Select "Authenticator App"
2. Scan QR code with authenticator app
3. Enter verification code from app
4. Setup complete

## Verification

During login:
1. After username/password verification
2. System prompts for MFA code
3. Enter OTP (if SMS method) or Authenticator code
4. On success → Login complete

## Security

- OTP expires in 5 minutes
- Rate limiting: Max 3 OTP requests per 10 minutes
- TOTP secret is encrypted in database
- MFA cannot be bypassed for enforced roles
