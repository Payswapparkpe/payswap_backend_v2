"""
Print a sanitized View Bill request/response log for sharing with Mobikwik support.
No secrets or actual encrypted values – only URL, keyVersion, lengths, plain payload structure, and response code/message.
Usage: python manage.py mobikwik_bbps_sanitized_log
Paste the output into your email so they don't have to ask twice.
"""
import json
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print sanitized View Bill log for Mobikwik support (no secrets)"

    def handle(self, *args, **options):
        from portal.services.vendors.mobikwik import MobikwikBBPSClient

        client = MobikwikBBPSClient()
        if not client.is_configured():
            self.stdout.write(self.style.ERROR("MOBIKWIK_BBPS not configured. Set .env and retry."))
            return

        # Plain payload as per doc (View Bill)
        plain = {"cn": "151608882", "op": "31", "cir": "", "adParams": {}}
        plain_json = json.dumps(plain, sort_keys=False, separators=(',', ':'))

        # Get encrypted envelope (lengths only)
        enc = client._encrypt_payload(plain) if client.use_encryption and client.public_key_pem else None

        # Actual API call to get response
        result = client.view_bill(operator_id="31", customer_id="151608882", extra_params={"cir": ""})
        data = result.get("data") or {}
        msg = data.get("message") or {}
        resp_code = msg.get("code", "")
        resp_text = msg.get("text", "")

        lines = [
            "",
            "--- SANITIZED VIEW BILL LOG (for Mobikwik support) ---",
            "",
            "Request:",
            "  URL: POST " + client.base_url + "/recharge/v3/retailerViewbill",
            "  Headers: Content-Type: application/json, Accept: application/json, Authorization: <token>",
            "",
            "Plain payload (before encryption), as per RT-Recharge doc:",
            "  " + plain_json,
            "",
        ]
        if enc and "encryptedSessionKey" in enc:
            lines.extend([
                "Encrypted request body (metadata only; values redacted):",
                "  keyVersion: " + str(enc.get("keyVersion", "")),
                "  len(iv): " + str(len(enc.get("iv", ""))),
                "  len(encryptedSessionKey): " + str(len(enc.get("encryptedSessionKey", ""))),
                "  len(encryptedPayload): " + str(len(enc.get("encryptedPayload", ""))),
                "  Encryption: AES-256-GCM (16-byte IV, 128-bit tag), RSA-2048 PKCS1Padding for session key, Base64 encoding.",
                "",
            ])
        else:
            lines.append("  (Encryption off or key missing – no encrypted envelope.)\n")

        lines.extend([
            "Response:",
            "  HTTP status: " + str(result.get("status_code", "—")),
            "  success: " + str(data.get("success", "—")),
            "  message.code: " + str(resp_code),
            "  message.text: " + str(resp_text),
            "",
            "--- END ---",
            "",
        ])
        self.stdout.write("\n".join(lines))
