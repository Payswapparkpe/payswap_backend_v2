"""
Central transaction / order / reference ID generator (ParkPe & portal).

Format (fixed 20 chars): T + YYYYMMDDHHMMSS + MMMM + R
  - T: prefix (default)
  - YYYYMMDDHHMMSS: UTC timestamp (14)
  - MMMM: first 4 digits of microsecond
  - R: one random char (0-9 or A-Z)

Example: T2026032007124729791
"""
from __future__ import annotations

import random
import string
from datetime import datetime


_RAND_CHARS = string.digits + string.ascii_uppercase


def generate_transaction_id(prefix: str = "T") -> str:
    """
    Generate a fixed-length 20-char transaction ID.

    1 (prefix) + 14 (datetime) + 4 (microsecond slice) + 1 (random char) = 20
    """
    now = datetime.utcnow()
    ts = now.strftime("%Y%m%d%H%M%S")
    micro4 = f"{now.microsecond:06d}"[:4]
    rand1 = random.choice(_RAND_CHARS)
    tid = f"{prefix}{ts}{micro4}{rand1}"
    # Safety guard for contract: always 20 chars.
    return tid[:20] if len(tid) > 20 else tid.ljust(20, "0")

