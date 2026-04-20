"""
Seed ApiVendor and VendorApi for orchestration (Vendor → APIs → Service Flow).

Run: python manage.py seed_vendor_apis

Creates/updates:
- ApiVendor: PayPoint, PayPoint DMT, Euronet, Cashfree, Kaleyra, Mobikwik, Instantpay, Leegality, Cashfree PG
- VendorApi per vendor (API name, api_code, api_type, purpose) so ServiceFlowStep can reference them.
"""
import logging
from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


# (vendor_code, vendor_name, description) — AEPS/DMT (PayPoint) removed; on Payswap Frontend
VENDORS = [
    ("euronet", "Euronet", "Euronet BBPS / EnService"),
    ("cashfree", "Cashfree", "Cashfree Verification (PAN, Aadhaar, Bank, etc.)"),
    ("cashfree_pg", "Cashfree PG", "Cashfree Payment Gateway"),
    ("kaleyra", "Kaleyra", "Kaleyra SMS, IVR, Click-to-Call"),
    ("mobikwik", "Mobikwik", "Mobikwik BBPS"),
    ("instantpay", "Instantpay", "Instantpay – Identity, Banking, Payouts, AePS, Collect, Tax"),
    ("leegality", "Leegality", "Leegality e-sign / document"),
]

# vendor_code -> list of (api_code, name, api_type, purpose)
VENDOR_APIS = {
    "euronet": [
        ("operators", "Get Operators / Billers", "QUERY", "BBPS operators/billers"),
        ("fetch_bill", "Fetch Bill", "VALIDATION", "Fetch bill details"),
        ("pay_bill", "Pay Bill", "TRANSACTION", "Pay bill"),
        ("payment_status", "Payment Status", "QUERY", "Payment status by ref id"),
    ],
    "cashfree": [
        ("pan", "PAN Verification", "VALIDATION", "Verify PAN"),
        ("aadhaar", "Aadhaar Verification", "VALIDATION", "Verify Aadhaar"),
        ("bank", "Bank Account Verification", "VALIDATION", "Verify bank account"),
        ("phone", "Phone Verification", "VALIDATION", "Verify phone"),
        ("email", "Email Verification", "VALIDATION", "Verify email"),
        ("gst", "GST Verification", "VALIDATION", "Verify GSTIN"),
        ("ifsc", "IFSC Verification", "QUERY", "IFSC and bank branch details"),
    ],
    "cashfree_pg": [
        ("create_order", "Create Order", "TRANSACTION", "Create payment order"),
        ("order_status", "Order Status", "QUERY", "Get order status"),
        ("refund", "Refund", "TRANSACTION", "Refund payment"),
    ],
    "kaleyra": [
        ("sms", "Send SMS", "TRANSACTION", "Send SMS"),
        ("template_sms", "Template SMS", "TRANSACTION", "SMS with DLT template"),
        ("click_to_call", "Click to Call", "TRANSACTION", "Voice call connect"),
    ],
    "mobikwik": [
        ("operators", "Get Operators / Billers", "QUERY", "BBPS operators/billers"),
        ("fetch_bill", "Fetch Bill", "VALIDATION", "Fetch bill details"),
        ("pay_bill", "Pay Bill", "TRANSACTION", "Pay bill"),
        ("payment_status", "Payment Status", "QUERY", "Payment status by ref id"),
    ],
    "instantpay": [
        ("aeps_withdraw", "AEPS Withdraw", "TRANSACTION", "AEPS cash withdrawal"),
        ("balance_check", "Balance Check", "QUERY", "AEPS/Banking balance check"),
        ("account_statement", "Account Statement", "QUERY", "Mini/Account statement"),
        ("dmt_transfer", "DMT Transfer", "TRANSACTION", "Domestic money transfer"),
        ("remittance_domestic", "Remittance Domestic", "TRANSACTION", "Domestic remittance"),
        ("remittance_nepal", "Remittance Nepal", "TRANSACTION", "Cross-border remittance to Nepal"),
        ("credit_card_bill_pay", "Credit Card Bill Payment", "TRANSACTION", "Credit card bill payment"),
        ("rc_verification", "RC Verification", "VALIDATION", "Vehicle registration verification"),
        ("vehicle_challan_lookup", "Vehicle Challan Lookup", "QUERY", "Lookup challan by vehicle details"),
        ("digilocker_init", "DigiLocker Init", "SETUP", "Start DigiLocker authorization flow"),
        ("digilocker_status", "DigiLocker Status", "QUERY", "Fetch DigiLocker status/documents"),
        ("card_bin_lookup", "Card BIN Lookup", "QUERY", "Lookup card BIN details"),
        ("credit_report", "Credit Report", "QUERY", "Fetch credit bureau report"),
        ("credit_score_simulator", "Credit Score Simulator", "QUERY", "Simulate credit score changes"),
        ("merchant_onboarding", "Merchant Onboarding", "SETUP", "Create/update merchant onboarding"),
        ("transaction_status", "Transaction Status", "QUERY", "Fetch transaction status by reference"),
        ("gstin_lookup", "GSTIN Lookup", "QUERY", "GSTIN verification"),
        ("pincode_lookup", "Pincode Lookup", "QUERY", "Pincode details"),
        ("bank_verification", "Bank Verification", "VALIDATION", "Bank account verification"),
    ],
    "leegality": [
        ("create_contract", "Create Contract", "SETUP", "Create e-sign contract"),
        ("signing_status", "Signing Status", "QUERY", "Get signing status"),
    ],
}


class Command(BaseCommand):
    help = "Seed ApiVendor and VendorApi for orchestration (Service Flow)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be created, do not write DB.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        if dry_run:
            self.stdout.write("DRY RUN – no DB changes")

        from portal.models import ApiVendor, VendorApi

        created_vendors = 0
        updated_vendors = 0
        created_apis = 0
        updated_apis = 0

        for code, name, description in VENDORS:
            vendor, v_created = ApiVendor.objects.get_or_create(
                code=code,
                defaults={"name": name, "description": description, "is_active": True},
            )
            if v_created:
                created_vendors += 1
                self.stdout.write(f"  Created ApiVendor: {name} ({code})")
            else:
                if vendor.name != name or vendor.description != description:
                    if not dry_run:
                        vendor.name = name
                        vendor.description = description
                        vendor.save(update_fields=["name", "description", "updated_at"])
                    updated_vendors += 1

            apis = VENDOR_APIS.get(code, [])
            for api_code, api_name, api_type, purpose in apis:
                api, a_created = VendorApi.objects.get_or_create(
                    vendor=vendor,
                    api_code=api_code,
                    defaults={
                        "name": api_name,
                        "api_type": api_type,
                        "purpose": purpose or "",
                        "is_active": True,
                    },
                )
                if a_created:
                    created_apis += 1
                else:
                    if api.name != api_name or api.api_type != api_type or (api.purpose or "") != (purpose or ""):
                        if not dry_run:
                            api.name = api_name
                            api.api_type = api_type
                            api.purpose = purpose or ""
                            api.save(update_fields=["name", "api_type", "purpose", "updated_at"])
                        updated_apis += 1

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Vendors: {created_vendors} created, {updated_vendors} updated. "
                    f"APIs: {created_apis} created, {updated_apis} updated."
                )
            )
        else:
            self.stdout.write(
                f"Would process {len(VENDORS)} vendors and {sum(len(VENDOR_APIS.get(c, [])) for c, _, _ in VENDORS)} APIs."
            )
