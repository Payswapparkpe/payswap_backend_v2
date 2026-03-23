# Phase 0 Audit — Step 6: Model & Data Ownership Map

**Read-only audit. No code changes.**

---

## 1. Portal models (portal/models/_monolith.py)

All portal models live in a single `_monolith.py`; re-exported via `portal.models.__init__`. Table names use `portal_*` prefix.

### 1.1 Auth / User

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| UserManager | — | Custom user manager; username generation, Role | User |
| Profile | portal_profile | OneToOne User; name, phone, email, KYC/MFA | User |
| Role | portal_role | Role codes, hierarchy_level | User |
| User | portal_user | AbstractUser; role FK | Profile, Role |
| UserPermission | portal_user_permission | Per-user permissions | User |
| KYC | portal_kyc | KYC documents/status | User |

### 1.2 Partner / API keys / Billing

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| ResellerPartner | portal_reseller_partner | Partner org; status, limits | APIKey, PartnerVendorAssignment, ResellerPartnerPricing/Transaction/Settlement |
| PartnerVendorAssignment | portal_partner_vendor_assignment | Partner ↔ ApiVendor assignment | ResellerPartner, ApiVendor |
| APIKey | portal_api_key | Partner API keys | ResellerPartner |
| InternalAPIKey | portal_internal_api_key | Internal service keys | — |
| APIKeyUsageLog | portal_api_key_usage_log | Usage log per key | APIKey |
| ResellerPartnerPricing | portal_reseller_partner_pricing | Partner pricing rules | ResellerPartner |
| ResellerPartnerTransaction | portal_reseller_partner_transaction | Partner transactions | ResellerPartner |
| ResellerPartnerSettlement | portal_reseller_partner_settlement | Settlements | ResellerPartner |
| IdempotencyRecord | portal_idempotency_record | Idempotency keys | — |
| ApprovalRequest | portal_approval_request | Approval workflow | ResellerPartner, User |

### 1.3 Wallet

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| Wallet | portal_wallet | User wallet balance | User |
| WalletTransaction | portal_wallet_transaction | Wallet txns | Wallet |

### 1.4 Vouchers (Gift / VoucherX)

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| GiftVoucherBrand | portal_gift_voucher_brand | Voucher brand | GiftVoucher, VoucherClient |
| VoucherClient | portal_voucher_client | Client for brands | GiftVoucherBrand |
| GiftVoucher | portal_gift_voucher | Single voucher | GiftVoucherBrand, VoucherClient |
| GiftVoucherTransaction | portal_gift_voucher_transaction | Voucher txns | GiftVoucher |
| GiftVoucherOTP | portal_gift_voucher_otp | OTP for redemption | GiftVoucher |
| BulkVoucherIssuanceBatch | portal_bulk_voucher_issuance_batch | Bulk issuance | GiftVoucherBrand, VoucherClient |
| GiftVoucherAuditLog | portal_gift_voucher_audit_log | Voucher audit | GiftVoucher |

### 1.5 Connect (ParkPe vehicles / chat)

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| Vehicle | portal_connect_vehicle | Vehicle (user-linked) | User |
| VehicleQRCode | portal_connect_vehicle_qrcode | QR for vehicle | Vehicle |
| VehicleRCData | portal_connect_vehicle_rc_data | RC data | Vehicle |
| VehicleRCUnlock | portal_connect_vehicle_rc_unlock | RC unlock requests | Vehicle |
| ConnectPredefinedMessage | portal_connect_predefined_message | Predefined messages | — |
| ConnectThread | portal_connect_thread | Chat thread | Vehicle (or user) |
| ConnectMessage | portal_connect_message | Chat message | ConnectThread |
| ConnectCallLog | portal_connect_call_log | Call log | — |
| ConnectScanLog | portal_connect_scan_log | Scan events | — |
| ConnectReport | portal_connect_report | Reports | — |

### 1.6 ParkPe (app-specific)

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| ParkPeVoucherBalance | portal_parkpe_voucher_balance | ParkPe voucher balance | User |
| ParkPeVoucherTransaction | portal_parkpe_voucher_transaction | ParkPe voucher txns | User |
| ParkPeServiceConfig | portal_parkpe_service_config | Service config | User |
| ParkPePaymentGatewayConfig | portal_parkpe_payment_gateway_config | PG config | User |
| ParkPePaymentOrder | portal_parkpe_payment_order | Payment orders | User |
| ParkPeBBPSFavoriteBiller | portal_parkpe_bbps_favorite_biller | Favorite billers | User |
| ParkPeBBPSSavedBill | portal_parkpe_bbps_saved_bill | Saved bills | User |

### 1.7 BBPS (portal catalog / config)

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| BBPSBillerCategory | portal_bbps_biller_category | Biller categories | — |
| BBPSOperator | portal_bbps_operator | Operators (loaded by bbps_operators_loader) | — |
| RBIRuleConfiguration | portal_rbi_rule_configuration | RBI rules | — |

### 1.8 Services / vendor (portal service catalog)

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| Service | portal_service | Service definition | ServiceCost, ServiceFlowStep |
| ApiVendor | portal_apivendor | Vendor (e.g. Mobikwik) | PartnerVendorAssignment, VendorApi |
| VendorApi | portal_vendorapi | Vendor API mapping | ApiVendor |
| ServiceFlowStep | portal_serviceflowstep | Flow steps | Service |
| ServiceCost | portal_service_cost | Cost per service | Service |

### 1.9 Tickets / support

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| Department | portal_department | Support department | Agent |
| Agent | portal_agent | Support agent | User, Department |
| Ticket | portal_ticket | Support ticket | User, Agent, Department |
| TicketNote | portal_ticket_note | Ticket notes | Ticket |
| TicketAssignmentHistory | portal_ticket_assignment_history | Assignment history | Ticket, Agent |
| TicketAttachment | portal_ticket_attachment | Attachments | Ticket |

### 1.10 Logging / queue / API log (portal)

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| LogEntry | portal_log_entry | Generic log entries | User (optional) |
| EmailQueue | portal_email_queue | Queued emails | — |
| CashfreeAPILog | portal_cashfree_api_log | Cashfree API request/response log | — |

---

## 2. API Management models (api_management/models.py)

Tables use `api_management_*` prefix. Ownership: API registry, governance, control, SLA, jobs.

### 2.1 API registry & products

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| ServiceCategory | api_management_service_category | Category (BBPS, Wallet, etc.) | APIRegistry |
| APIProduct | api_management_api_product | Product toggle per platform (Parkpe/Payswap) | — |
| APIRegistry | api_management_api_registry | Per-endpoint registry (status, roles, rate limit) | ServiceCategory |

### 2.2 API logging & monitoring

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| APILog | api_management_api_log | Request/response log (principal, status, duration) | APIRegistry, User, portal.APIKey |
| APIDowntimeEvent | api_management_api_downtime_event | Downtime windows | APIRegistry |
| APISLAStat | api_management_api_sla_stat | Per-partner, per-service, per-day SLA | ResellerPartner |

### 2.3 Governance

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| PartnerAPISubscription | api_management_partner_api_subscription | Partner ↔ API allowlist | ResellerPartner, APIRegistry |
| FeatureFlag | api_management_feature_flag | Global feature flags | FeatureFlagOverride |
| FeatureFlagOverride | api_management_feature_flag_override | Per-partner/app/user override | FeatureFlag |
| ControlAuditLog | api_management_control_audit_log | Audit for control actions | User |

### 2.4 System jobs & alerts

| Model | Table | Purpose | Key relations |
|-------|--------|---------|----------------|
| SystemJobStatus | api_management_system_job_status | Job registry + last run + SLA status | — |
| SystemJobRun | api_management_system_job_run | Per-run record (Super Admin UI) | User |
| SystemAlertRule | api_management_system_alert_rule | Alert rules (e.g. SLA_LOW); notify_email | — |

---

## 3. Findings: redundancy, deprecation, similar-purpose

- **Two API logs:** `portal.CashfreeAPILog` (Cashfree-specific, portal) vs `api_management.APILog` (generic, registry-linked, principal_type, used for SLA). Different scope; CashfreeAPILog is vendor-specific, APILog is governance/middleware. Not redundant but overlapping “log API calls” concern.  
- **Multiple audit/log tables:** `portal.LogEntry`, `portal.GiftVoucherAuditLog`, `api_management.ControlAuditLog`. Different domains (generic activity, voucher ops, control actions). Similar-purpose (audit trail) but not redundant.  
- **Partner “subscription” in two places:** Portal has `PartnerVendorAssignment` (partner ↔ ApiVendor). API Management has `PartnerAPISubscription` (partner ↔ APIRegistry). Different: vendor assignment vs API allowlist; both are “what can this partner use.”  
- **No wallet app split:** Wallet models live in portal monolith; no separate `wallet` app. Single ownership (portal).  
- **Monolith:** All portal models in one file (`_monolith.py`); no per-domain split. Increases coupling and file size.  
- **Deprecation:** No models explicitly marked deprecated in code; migrations not scanned for “replaced by” comments.  
- **Similar-purpose:** `APIKeyUsageLog` (portal) vs `APILog` (api_management) — both can record API key usage; APILog is broader (user + api_key + anon) and tied to APIRegistry; APIKeyUsageLog may be legacy or partner-facing only.

---

*End of Step 6 — Data Model Map.*
