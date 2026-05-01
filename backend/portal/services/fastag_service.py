"""
FASTag issuer abstraction — deduct / balance / link verification.

Production deployments plug in NPCI or bank-specific APIs; default uses a safe stub
that simulates success in dev so parking flows remain testable end-to-end.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

from portal.utils.logging_helper import get_logger

logger = get_logger("portal.services.fastag")


class InsufficientFasTagBalance(Exception):
    """Raised when issuer rejects deduction for insufficient wallet balance."""

    def __init__(self, message: str = "Insufficient FASTag balance"):
        self.message = message
        super().__init__(message)


@dataclass
class FastagDeductResult:
    success: bool
    reference: str = ""
    error: str = ""


class FastagIssuerClient:
    """Replace methods with real HTTP calls to issuer/NPCI orchestration."""

    def deduct(self, wallet_id: str, amount: Decimal, ref: str) -> FastagDeductResult:
        """
        Request wallet debit. `ref` should be deterministic per ParkingTransaction PK.
        """
        if not wallet_id:
            return FastagDeductResult(False, error="missing_wallet_id")

        mode = getattr(settings, "FASTAG_ISSUER_MODE", "stub")
        if mode == "stub":
            logger.info(
                "fastag_deduct_stub",
                extra_data={"wallet_id": wallet_id[-4:], "amount": str(amount), "ref": ref},
            )
            return FastagDeductResult(True, reference=f"STUB-{ref}")

        # Future: HTTP client to issuer
        return FastagDeductResult(False, error="issuer_not_configured")

    def balance(self, wallet_id: str) -> Decimal | None:
        mode = getattr(settings, "FASTAG_ISSUER_MODE", "stub")
        if mode == "stub":
            return Decimal("1000.00")
        return None


default_client = FastagIssuerClient()


def deduct_wallet(wallet_id: str, amount: Decimal, ref: str) -> FastagDeductResult:
    return default_client.deduct(wallet_id, amount, ref)
