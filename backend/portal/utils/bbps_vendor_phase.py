"""Map Mobikwik / biller vendor status strings to success | failed | pending."""


def vendor_payment_phase(vendor_status: str) -> str:
    """Used for API responses and DB `resolved_phase` derivation."""
    s = (vendor_status or "").strip().upper()
    if not s or s == "UNKNOWN":
        return "pending"
    if any(x in s for x in ("SUCCESS", "COMPLETED", "PAID", "SETTLED", "FULFILLED", "COMPLETE")):
        return "success"
    if any(x in s for x in ("FAIL", "ERROR", "REJECT", "CANCEL", "DECLINED", "INVALID", "DENIED")):
        return "failed"
    if any(x in s for x in ("PENDING", "SUBMITTED", "INIT", "PROCESSING", "IN_PROGRESS", "WAIT", "UNKNOWN")):
        return "pending"
    return "pending"
