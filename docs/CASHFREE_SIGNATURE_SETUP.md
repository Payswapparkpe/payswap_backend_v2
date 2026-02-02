# Cashfree API Signature Setup

## Problem
Cashfree API is returning error: `"x-cf-signature missing in the request header"`

## Solution Options

You have **two options** to resolve this:

### Option 1: Whitelist IP Address (Recommended - Simpler)

1. Log in to [Cashfree Secure ID Dashboard](https://merchant.cashfree.com/verificationsuite/home)
2. Go to **Developers** → **Two-Factor Authentication** → **Secure ID**
3. Select **IP Whitelist** from the dropdown
4. Click **Add IP Address**
5. Add your server's IP address (IPv4 only)
6. You can whitelist up to 25 IP addresses

**Note:** If your IP is dynamic or you need more than 25 IPs, use Option 2.

### Option 2: Configure Public Key for Signature Generation

1. Log in to [Cashfree Secure ID Dashboard](https://merchant.cashfree.com/verificationsuite/home)
2. Go to **Developers** → **Two-Factor Authentication** → **Secure ID**
3. Select **Public Key** from the dropdown
4. Click **Generate Public Key**
5. Download the public key file (password protected - password sent to your email)
6. Extract the public key (PEM format)

#### Configure in .env file:

**Option A: Direct PEM string (recommended for single key)**
```bash
CASHFREE_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"
```

**Option B: File path (recommended for multiple environments)**
```bash
CASHFREE_PUBLIC_KEY_PATH=/path/to/cashfree_public_key.pem
```

## How Signature Generation Works

The code automatically generates the signature using:
1. Your `x-client-id` (CASHFREE_API_KEY)
2. Current UNIX timestamp
3. RSA encryption with the public key
4. Base64 encoding

Signature is valid for 5 minutes and is regenerated for each request.

## Current Status

✅ Signature generation code is implemented
✅ Code will automatically use signature if public key is configured
✅ Code will gracefully handle missing public key (but API calls will fail until IP is whitelisted or public key is configured)

## Next Steps

1. **Choose Option 1 or Option 2** above
2. If using Option 2, add the public key to `.env` file
3. Restart your Django server
4. Test the APIs again

## Testing

After configuration, run:
```bash
python manage.py test_all_cashfree_apis
```

This will test all APIs and verify they're working correctly.
