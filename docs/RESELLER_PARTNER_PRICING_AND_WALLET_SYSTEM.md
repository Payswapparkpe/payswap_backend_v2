# Reseller Partner Pricing and Wallet System

## Overview

This document describes the implementation of the comprehensive pricing, wallet, and commission system for Reseller Partners. The system ensures that partners are charged for API usage, commissions are credited appropriately, and all financial transactions are properly tracked.

## Implementation Date
January 26, 2026

## Features Implemented

### 1. Service Cost Tracking (`ServiceCost` Model)

**Purpose**: Track our cost per service/product (what we pay vendors)

**Key Fields**:
- `service`: Foreign key to Service
- `cost_type`: FIXED, PERCENTAGE, PER_TRANSACTION, TIERED
- `base_cost`: Base cost for the service
- `cost_percentage`: Cost percentage (if percentage-based)
- `cost_per_transaction`: Cost per transaction
- `tiered_cost`: JSON field for tiered pricing
- `provides_commission`: Boolean - whether service provides commission
- `commission_on`: Who gets commission (e.g., 'sender', 'receiver', 'partner')

**Usage**: Admin can set the cost we pay vendors for each service, which helps calculate margins and partner pricing.

### 2. Automatic Wallet Debit System

**Implementation**: `PartnerAccountingService.charge_partner_for_service()`

**How it works**:
1. When a partner uses an API service, the system:
   - Checks partner's wallet balance
   - Calculates charge amount based on partner pricing
   - Debits the wallet
   - Records a REVENUE transaction
   - Automatically creates COMMISSION transaction if applicable
   - Credits commission to wallet

**Features**:
- Automatic balance checking
- Insufficient balance handling (returns 402 Payment Required)
- Wallet transaction logging
- Transaction recording for accounting

### 3. Payment Services (AEPS, DMT, BBPS)

**Services Added**:
- **AEPS** (Aadhaar Enabled Payment System)
  - Commission-based service
  - Per-transaction cost model
  - Commission credited to partner

- **DMT** (Domestic Money Transfer)
  - Commission-based service
  - Percentage-based cost model
  - **RBI Rule**: Sender is charged (configured in ServiceCost)
  - Commission credited to partner

- **BBPS** (Bharat Bill Payment System)
  - Commission-based service
  - Per-transaction cost model
  - Multiple biller categories with individual commission rates

### 4. BBPS Biller Category System

**Model**: `BBPSBillerCategory`

**Purpose**: Set commission rates for each BBPS biller category

**Categories Supported**:
- Electricity
- Water
- Gas
- Mobile Prepaid/Postpaid
- Landline
- Broadband
- DTH
- Insurance
- Loan
- Credit Card
- Fastag
- Municipal
- Education
- Healthcare
- Other

**Features**:
- Category-specific commission rates
- Category-specific base costs
- Commission type configuration (Revenue Share, Markup, Fixed)

### 5. RBI Rules Configuration

**Model**: `RBIRuleConfiguration`

**Purpose**: Store RBI compliance rules for services

**Features**:
- Rule name and description
- Flexible JSON configuration
- RBI circular reference tracking
- Effective date management

**Example**: DMT service has RBI rule that sender is charged, stored in `rule_config` as `{'charges_on': 'sender', 'max_amount': 10000}`

### 6. API Integration

**Updated Views**:
- `VoucherIssueView`: Now charges partner wallet before issuing voucher
- `PANVerifyView`: Now charges partner wallet for KYC verification
- All other API v2 views can be updated similarly

**Error Handling**:
- Returns `402 Payment Required` if wallet has insufficient balance
- Logs all transaction attempts
- Doesn't fail API request if transaction recording fails (graceful degradation)

## Database Models

### New Models

1. **ServiceCost**
   - Tracks vendor costs per service
   - Supports multiple cost models
   - Commission configuration

2. **BBPSBillerCategory**
   - Biller category management
   - Category-specific commission rates
   - Category-specific costs

3. **RBIRuleConfiguration**
   - RBI compliance rules
   - Flexible JSON configuration
   - Rule versioning

### Updated Models

1. **Service**
   - No changes (existing model used)

2. **ResellerPartnerPricing**
   - No changes (existing model used)

3. **ResellerPartnerTransaction**
   - No changes (existing model used)

## Service Flow

### When Partner Uses API Service

1. **API Request** → Partner makes API call with API key
2. **Authentication** → API key validated, partner identified
3. **Service Execution** → Service logic executed (e.g., voucher issued, KYC verified)
4. **Pricing Lookup** → Partner pricing for service retrieved
5. **Charge Calculation** → Charge amount calculated based on pricing
6. **Wallet Debit** → Partner wallet debited
7. **Transaction Recording** → REVENUE transaction recorded
8. **Commission Calculation** → Commission calculated if applicable
9. **Commission Credit** → Commission credited to partner wallet
10. **Response** → API response returned to partner

### Commission Flow (for AEPS, DMT, BBPS)

1. **Service Usage** → Partner uses commission-based service
2. **REVENUE Transaction** → Partner charged, REVENUE transaction created
3. **Commission Calculation** → Commission calculated from pricing config
4. **COMMISSION Transaction** → Separate COMMISSION transaction created
5. **Wallet Credit** → Commission credited to partner wallet
6. **Settlement** → Commission included in periodic settlements

## Management Commands

### Seed Payment Services

```bash
python manage.py seed_payment_services
```

**What it does**:
- Creates AEPS, DMT, BBPS services
- Creates ServiceCost entries for each service
- Creates all BBPS biller categories with default commission rates
- Sets up RBI rule for DMT (sender charged)

## Admin Interface

All new models are registered in Django Admin:

- **Service**: Manage services
- **ServiceCost**: Set vendor costs per service
- **BBPSBillerCategory**: Configure biller category commissions
- **RBIRuleConfiguration**: Manage RBI compliance rules

## API Endpoints

### Updated Endpoints

All API v2 endpoints now automatically:
- Charge partner wallet
- Record transactions
- Handle insufficient balance errors

**Example Response (Insufficient Balance)**:
```json
{
  "success": false,
  "message": "Insufficient wallet balance",
  "status_code": 402
}
```

## Configuration

### Setting Partner Pricing

1. Go to Admin → Reseller Partner Pricing
2. Select partner and service
3. Configure:
   - Pricing type (Percentage, Fixed, Tiered)
   - Base price
   - Markup percentage/fixed amount
   - Commission type
   - Commission percentage/fixed amount

### Setting Service Costs

1. Go to Admin → Service Cost
2. Select service
3. Configure:
   - Cost type
   - Base cost
   - Cost percentage/per-transaction
   - Commission settings

### Setting BBPS Biller Commissions

1. Go to Admin → BBPS Biller Category
2. Select category
3. Configure:
   - Default commission percentage
   - Base cost
   - Commission type

## Testing

### Test Wallet Debit

1. Create a reseller partner
2. Add wallet balance
3. Set partner pricing for a service
4. Make API call
5. Verify:
   - Wallet balance decreased
   - REVENUE transaction created
   - COMMISSION transaction created (if applicable)
   - Wallet credited with commission

### Test Insufficient Balance

1. Create a reseller partner
2. Set wallet balance to low amount
3. Make API call with high charge
4. Verify:
   - 402 Payment Required error
   - No wallet debit
   - No transaction recorded

## Future Enhancements

1. **Real-time Balance Updates**: WebSocket notifications for wallet balance changes
2. **Auto-recharge**: Automatic wallet top-up when balance is low
3. **Credit Limits**: Credit limit for partners
4. **Settlement Automation**: Automated settlement processing
5. **Advanced Reporting**: Detailed financial reports and analytics

## Notes

- All financial calculations use `Decimal` for precision
- Wallet transactions are immutable (no deletion)
- Commission is calculated and credited automatically
- RBI rules can be edited as needed (flexible JSON config)
- BBPS biller categories can be extended easily
