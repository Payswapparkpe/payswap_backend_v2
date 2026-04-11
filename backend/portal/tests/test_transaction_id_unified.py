"""Unified T-format transaction / reference IDs (20 chars)."""
import re

from portal.utils.transaction_id import generate_transaction_id
from portal.utils.voucher_utils import generate_reference_number


_TID_RE = re.compile(r"^T\d{14}\d{4}[0-9A-Z]$")


def test_generate_transaction_id_format_and_length():
    tid = generate_transaction_id()
    assert len(tid) == 20
    assert _TID_RE.match(tid), tid


def test_generate_reference_number_matches_unified_format():
    ref = generate_reference_number()
    assert len(ref) == 20
    assert _TID_RE.match(ref), ref
    ref2 = generate_reference_number("BRN")
    assert len(ref2) == 20
    assert _TID_RE.match(ref2), ref2
