from __future__ import annotations

from django.core.management.base import BaseCommand

from portal.services.vendors.instantpay import InstantpayClient


class Command(BaseCommand):
    help = (
        "Print sanitized Instantpay identity auth metadata for vehicle challan lookup "
        "without making a vendor API call."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--vehicle-number",
            type=str,
            default="24BH8017B",
            help="Vehicle number used to build the normalized payload.",
        )

    def handle(self, *args, **options):
        client = InstantpayClient()
        vehicle_number = str(options.get("vehicle_number") or "").strip().upper()
        payload = {"vehicleNumber": vehicle_number}
        request_id = client._request_id()
        _, meta = client._build_headers(
            request_id=request_id,
            body=payload,
            auth_code=None,
            auth_code_only=True,
        )

        self.stdout.write("Instantpay identity auth debug")
        self.stdout.write(f"base_url: {client.base_url}")
        self.stdout.write(f"identity_auth_mode: {client.identity_auth_mode}")
        self.stdout.write(f"request_id: {request_id}")
        self.stdout.write(f"normalized_payload: {payload}")
        self.stdout.write(f"request_meta: {meta}")
