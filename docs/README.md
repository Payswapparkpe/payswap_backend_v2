# Portal App Documentation

## Overview

The Portal app provides comprehensive user management, authentication, KYC verification, and wallet functionality for the Payswap platform.

## Features

- **User Management**: Custom user model with role-based access
- **Authentication**: Session-based authentication with MFA
- **KYC Verification**: Document verification with multiple vendors
- **Wallet System**: Secure wallet with encrypted storage
- **Role-Based Access Control**: Django Groups and permissions
- **Profile Management**: One profile, multiple users

## Architecture

### Models
- `User`: Custom user model with auto-generated usernames
- `Profile`: Business/individual profiles
- `Role`: User roles with hierarchy
- `KYC`: Know Your Customer verification
- `Wallet`: User wallet with encrypted seed phrases
- `WalletTransaction`: Transaction history
- `UserPermission`: Custom permission assignments

### Services
- Document Verification (Cashfree, Invincible Ocean)
- OTP Service (Kaleyra)
- Email Service (AWS SES)
- Notification Service (AWS SNS)
- Storage Service (AWS S3)

## Usage

See individual documentation files:
- [Authentication](authentication.md)
- [MFA Setup](mfa_setup.md)
- [Permissions](permissions.md)
- [API & Portal](API_README.md)
- [Vendor Integration](VENDOR_INTEGRATION_REFERENCE.md)
