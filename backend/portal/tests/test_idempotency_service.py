import pytest

from portal.services.idempotency_service import reserve_idempotency


@pytest.mark.django_db
def test_idempotency_replay_same_fingerprint():
    scope = "partner_1:v2:test"
    key = "abc-123"
    fingerprint = "f" * 64

    outcome, cached = reserve_idempotency(scope, key, request_fingerprint=fingerprint)
    assert outcome == "reserved"
    assert cached is None

    outcome2, cached2 = reserve_idempotency(scope, key, request_fingerprint=fingerprint)
    assert outcome2 == "conflict"
    assert cached2 is None


@pytest.mark.django_db
def test_idempotency_rejects_fingerprint_mismatch():
    scope = "partner_1:v2:test"
    key = "abc-123"

    outcome, _ = reserve_idempotency(scope, key, request_fingerprint="a" * 64)
    assert outcome == "reserved"

    mismatch_outcome, _ = reserve_idempotency(scope, key, request_fingerprint="b" * 64)
    assert mismatch_outcome == "fingerprint_mismatch"
