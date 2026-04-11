"""
Test all BBPS operators/billers from Operators.xlsx against Mobikwik View Bill API.
Loads operators from Excel, calls View Bill for each (with a test customer ID), and reports OK / FAIL per operator.
Uses format-valid test consumer IDs per category; retries failures with length-derived ID when error says "X character long".
Treats E702 (no outstanding bill) as OK.
"""
import json
import re
from django.core.management.base import BaseCommand


def _parse_length_from_error(text: str):
    """Parse 'Please enter 9 character long CA Number' or '10-15 character long' -> (min_len, max_len). Returns None if not found."""
    if not text:
        return None
    # e.g. "10-15 character long" or "9-10 character long"
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*character\s*long", text, re.I)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    # e.g. "9 character long" or "12 character long"
    m = re.search(r"(\d+)\s*character\s*long", text, re.I)
    if m:
        n = int(m.group(1))
        return (n, n)
    return None


def _test_id_for_length(min_len: int, max_len: int) -> str:
    """Return a numeric test string of length in [min_len, max_len] (use max_len for safety)."""
    n = max(min_len, min(max_len, 20))  # cap at 20
    return "1" * (n - 1) + "0" if n > 0 else "0"  # e.g. 9 -> 111111110


def _format_valid_customer_id(operator: dict, default: str = "0") -> str:
    """Return a format-valid test consumer ID for this operator category (so Mobikwik does not reject on length/format)."""
    cat = (operator.get("category") or "").upper()
    # Map category to typical length/format; use placeholder that passes validation
    if cat in ("DTH",):
        return "1234567890"  # 10-digit subscriber ID common for DTH
    if cat in ("POSTPAID", "MOBILE", "PREPAID"):
        return "9999999999"  # 10-digit mobile
    if cat in ("LANDLINE", "BROADBAND"):
        return "2212345678"  # 10-digit with STD
    if cat == "ELECTRICITY":
        return "123456789012"  # 12-char CA/consumer common
    if cat in ("GAS", "WATER"):
        return "123456789012"  # 12-char CA
    if cat == "INSURANCE":
        return "12345678901"  # 10-11 char policy
    if cat == "FASTAG":
        return "310221002679"  # example vehicle/tag format
    return default


class Command(BaseCommand):
    help = "Test all BBPS operators/billers from Operators.xlsx (View Bill per operator)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--category",
            type=str,
            default=None,
            help="Filter operators by category (e.g. ELECTRICITY, FASTAG)",
        )
        parser.add_argument(
            "--customer-id",
            type=str,
            default="0",
            help="Test customer/consumer ID to use for View Bill (default: 0)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of operators to test (default: all)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list operators from Excel, do not call Mobikwik API",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print full API response for each operator",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Write results summary to JSON file (path)",
        )
        parser.add_argument(
            "--retry-failures",
            action="store_true",
            help="Retry failed operators once with length-correct consumer ID parsed from error",
        )

    def handle(self, *args, **options):
        from portal.services.bbps_operators_loader import load_bbps_operators_from_excel
        from portal.services.vendors.mobikwik import MobikwikBBPSClient

        category = options.get("category")
        customer_id = options.get("customer_id") or "0"
        limit = options.get("limit")
        dry_run = options.get("dry_run")
        verbose = options.get("verbose")
        output_path = options.get("output")
        retry_failures = options.get("retry_failures")

        self.stdout.write("BBPS Operators / Billers test (from Operators.xlsx)")
        self.stdout.write("=" * 60)

        operators = load_bbps_operators_from_excel(bbps_enabled_only=True, category=category)
        if not operators:
            self.stdout.write(self.style.WARNING("No operators found. Check Mobikwik/Operators.xlsx and BBPS Enabled filter."))
            return

        if limit:
            operators = operators[:limit]
        self.stdout.write(f"Loaded {len(operators)} operators" + (f" (category={category})" if category else "") + ".")
        if dry_run:
            self.stdout.write(self.style.NOTICE("Dry run – listing only (no API calls)."))
            for i, op in enumerate(operators, 1):
                op_val = op.get("op")
                self.stdout.write(
                    f"  {i}. {op.get('name', '')} | biller_id={op.get('operator_id')} | op={op_val} | category={op.get('category')}"
                )
            return

        client = MobikwikBBPSClient()
        if not client.is_configured():
            self.stdout.write(
                self.style.ERROR(
                    "Mobikwik BBPS not configured. Set MOBIKWIK_BBPS_ENABLED=True and credentials in .env"
                )
            )
            return

        # Ensure token
        token_result = client.get_token()
        if not token_result.get("success"):
            self.stdout.write(self.style.ERROR(f"Token failed: {token_result.get('error')}"))
            return
        self.stdout.write(self.style.SUCCESS("Token OK"))
        self.stdout.write("")

        results = []
        for i, operator in enumerate(operators, 1):
            name = operator.get("name", "Unknown")
            biller_id = operator.get("operator_id", "")
            op_val = operator.get("op")
            cat = operator.get("category", "")
            # Mobikwik expects "op" as integer; use numeric op when available
            operator_id_for_api = op_val if isinstance(op_val, int) else biller_id
            # Use format-valid test consumer ID per operator when default "0" so validation passes
            cid = _format_valid_customer_id(operator, customer_id) if customer_id == "0" else customer_id

            self.stdout.write(f"[{i}/{len(operators)}] {name} (op={operator_id_for_api}) ... ", ending="")
            try:
                result = client.view_bill(
                    operator_id=operator_id_for_api,
                    customer_id=cid,
                    extra_params={},
                )
            except Exception as e:
                results.append({"name": name, "biller_id": biller_id, "op": op_val, "category": cat, "status": "ERROR", "message": str(e)})
                self.stdout.write(self.style.ERROR(f"ERROR: {e}"))
                continue

            success = result.get("success") is True
            data = result.get("data") or {}
            msg_obj = data.get("message") if isinstance(data.get("message"), dict) else {}
            code = str(msg_obj.get("code", "") or "")
            text = msg_obj.get("text", "") or result.get("error", "") or ""
            text = str(text).strip()
            # E702 / "No outstanding bills found" = API success (request accepted, no bill for this consumer)
            no_bill_ok = "E702" in text or "No outstanding bills found" in text or "no outstanding bill" in text.lower()
            # Treat as error only when not a success code and not the "no bill" case
            is_error = bool(msg_obj and not no_bill_ok and (code not in (None, "", "0", "200") or bool(text)))
            if success and (not is_error or no_bill_ok):
                results.append({"name": name, "biller_id": biller_id, "op": op_val, "category": cat, "status": "OK", "message": "No bill" if no_bill_ok else ""})
                self.stdout.write(self.style.SUCCESS("OK" + (" (no bill)" if no_bill_ok else "")))
            else:
                short_msg = (text[:80] + "…") if len(text) > 80 else text
                results.append({"name": name, "biller_id": biller_id, "op": op_val, "category": cat, "status": "FAIL", "message": text})
                self.stdout.write(self.style.WARNING(f"FAIL: {short_msg}"))
            if verbose:
                self.stdout.write(json.dumps(result, indent=2))

        # Retry failures with length-derived consumer ID when error mentions "X character long"
        if retry_failures and operators:
            failed_idx = [i for i, r in enumerate(results) if r["status"] == "FAIL"]
            retried = 0
            for idx in failed_idx:
                r = results[idx]
                msg = r.get("message") or ""
                lengths = _parse_length_from_error(msg)
                if not lengths:
                    continue
                min_len, max_len = lengths
                retry_cid = _test_id_for_length(min_len, max_len)
                operator = operators[idx]
                name = operator.get("name", "Unknown")
                biller_id = operator.get("operator_id", "")
                op_val = operator.get("op")
                cat = operator.get("category", "")
                operator_id_for_api = op_val if isinstance(op_val, int) else biller_id
                self.stdout.write(f"  Retry [{idx+1}] {name} with len={len(retry_cid)} ... ", ending="")
                try:
                    result = client.view_bill(operator_id=operator_id_for_api, customer_id=retry_cid, extra_params={})
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"ERROR: {e}"))
                    continue
                success = result.get("success") is True
                data = result.get("data") or {}
                msg_obj = data.get("message") if isinstance(data.get("message"), dict) else {}
                code = str(msg_obj.get("code", "") or "")
                text = msg_obj.get("text", "") or result.get("error", "") or ""
                text = str(text).strip()
                no_bill_ok = "E702" in text or "No outstanding bills found" in text or "no outstanding bill" in text.lower()
                is_error = bool(msg_obj and not no_bill_ok and (code not in (None, "", "0", "200") or bool(text)))
                if success and (not is_error or no_bill_ok):
                    results[idx] = {"name": name, "biller_id": biller_id, "op": op_val, "category": cat, "status": "OK", "message": "No bill" if no_bill_ok else ""}
                    self.stdout.write(self.style.SUCCESS("OK (retry)"))
                    retried += 1
                else:
                    self.stdout.write(self.style.WARNING(f"FAIL: {text[:60]}…"))
            if retried:
                self.stdout.write(self.style.SUCCESS(f"Retry pass: {retried} more OK."))
                self.stdout.write("")

        self.stdout.write("")
        self.stdout.write("=" * 60)
        ok_count = sum(1 for r in results if r["status"] == "OK")
        fail_count = sum(1 for r in results if r["status"] == "FAIL")
        err_count = sum(1 for r in results if r["status"] == "ERROR")
        self.stdout.write(self.style.SUCCESS(f"OK: {ok_count}") + f"  |  FAIL: {fail_count}  |  ERROR: {err_count}  |  Total: {len(results)}")
        self.stdout.write("")
        if fail_count or err_count:
            self.stdout.write("Failed / error operators:")
            for r in results:
                if r["status"] != "OK":
                    self.stdout.write(f"  - {r['name']} (biller_id={r['biller_id']}, op={r['op']}): {r.get('message', '')[:100]}")
        if output_path:
            try:
                import json as json_mod
                with open(output_path, "w", encoding="utf-8") as f:
                    json_mod.dump({
                        "summary": {"ok": ok_count, "fail": fail_count, "error": err_count, "total": len(results)},
                        "results": results,
                    }, f, indent=2, ensure_ascii=False)
                self.stdout.write(self.style.SUCCESS(f"Results written to {output_path}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to write output file: {e}"))
        self.stdout.write(self.style.SUCCESS("Done."))
