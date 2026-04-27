import hashlib

import pytest

from portal.services.vendors.instantpay import InstantpayClient


@pytest.fixture
def instantpay_client():
    client = InstantpayClient()
    client.client_id = "cid123"
    client.client_secret = "sec456"
    client.auth_code = "STATIC_CODE"
    return client


def test_identity_auth_mode_pipe_headers(monkeypatch, instantpay_client):
    instantpay_client.identity_auth_mode = "sha256_pipe"
    monkeypatch.setattr(
        "portal.services.vendors.instantpay.time.time",
        lambda: 1_700_000_000,
    )

    headers, meta = instantpay_client._build_headers(
        request_id="rid-1",
        body={"vehicleNumber": "24BH8017B"},
        auth_code_only=True,
    )

    ts = "1700000000"
    expected = hashlib.sha256("cid123|sec456|1700000000".encode("utf-8")).hexdigest()
    assert headers["X-Ipay-Auth-Code"] == expected
    assert headers["X-Ipay-Timestamp"] == ts
    assert headers["X-Ipay-Client-Id"] == "cid123"
    assert headers["X-Ipay-Client-Secret"] == "sec456"
    assert meta["auth_mode"] == "sha256_pipe"


def test_identity_auth_mode_concat_headers(monkeypatch, instantpay_client):
    instantpay_client.identity_auth_mode = "sha256_concat"
    monkeypatch.setattr(
        "portal.services.vendors.instantpay.time.time",
        lambda: 1_700_000_001,
    )

    headers, meta = instantpay_client._build_headers(
        request_id="rid-2",
        body={"vehicleNumber": "24BH8017B"},
        auth_code_only=True,
    )

    expected = hashlib.sha256("cid123sec4561700000001".encode("utf-8")).hexdigest()
    assert headers["X-Ipay-Auth-Code"] == expected
    assert meta["auth_mode"] == "sha256_concat"


def test_identity_auth_mode_static_headers(monkeypatch, instantpay_client):
    instantpay_client.identity_auth_mode = "static"
    monkeypatch.setattr(
        "portal.services.vendors.instantpay.time.time",
        lambda: 1_700_000_002,
    )

    headers, meta = instantpay_client._build_headers(
        request_id="rid-3",
        body={"vehicleNumber": "24BH8017B"},
        auth_code_only=True,
    )

    assert headers["X-Ipay-Auth-Code"] == "STATIC_CODE"
    assert meta["auth_mode"] == "static"


def test_identity_auth_mode_fixed_1_headers(monkeypatch, instantpay_client):
    instantpay_client.identity_auth_mode = "fixed_1"
    monkeypatch.setattr(
        "portal.services.vendors.instantpay.time.time",
        lambda: 1_700_000_003,
    )

    headers, meta = instantpay_client._build_headers(
        request_id="rid-4",
        body={"vehicleRegistrationNumber": "24BH8017B"},
        auth_code_only=True,
    )

    assert headers["X-Ipay-Auth-Code"] == "1"
    assert headers["X-Ipay-Client-Id"] == "cid123"
    assert headers["X-Ipay-Client-Secret"] == "sec456"
    assert "X-Ipay-Timestamp" not in headers
    assert meta["auth_mode"] == "fixed_1"


def test_vehicle_challan_lookup_uses_plain_uppercase_payload(monkeypatch, instantpay_client):
    instantpay_client.identity_auth_mode = "sha256_pipe"
    monkeypatch.setattr(instantpay_client, "is_configured", lambda: True)
    monkeypatch.setattr(
        instantpay_client,
        "_path_candidates",
        lambda _path: ["/identity/vehicleChallan"],
    )
    monkeypatch.setattr(
        instantpay_client,
        "_build_headers",
        lambda **kwargs: (
            {"Content-Type": "application/json", "X-Ipay-Auth-Code": "1", "X-Ipay-Client-Id": "cid123", "X-Ipay-Client-Secret": "sec456"},
            {"auth_mode": "sha256_pipe"},
        ),
    )

    captured = {}

    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"statuscode": "RPI", "status": "The X-Ipay-Auth-Code header is invalid."}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _Response()

    monkeypatch.setattr("portal.services.vendors.instantpay.httpx.Client", _Client)

    res = instantpay_client.request(
        "vehicle_challan_lookup",
        {"vehicle_number": "24bh8017b", "partner_txn_id": "p1"},
    )

    assert captured["url"].endswith("/identity/vehicleChallan")
    assert captured["json"]["vehicleRegistrationNumber"] == "24BH8017B"
    assert captured["json"]["consent"] == "Y"
    assert captured["json"]["latitude"] == "0.0"
    assert captured["json"]["longitude"] == "0.0"
    assert captured["json"]["externalRef"] == "p1"
    assert "payload" not in captured["json"]
    assert res["attempted_path"] == "/identity/vehicleChallan"


def test_account_statement_uses_auth_code_only_headers(monkeypatch, instantpay_client):
    instantpay_client.identity_auth_mode = "fixed_1"
    monkeypatch.setattr(instantpay_client, "is_configured", lambda: True)
    monkeypatch.setattr(instantpay_client, "_path_candidates", lambda _path: ["/reports/statement"])

    captured = {"auth_code_only": None, "headers": None}

    def _fake_build_headers(**kwargs):
        captured["auth_code_only"] = kwargs.get("auth_code_only")
        return (
            {
                "Content-Type": "application/json",
                "X-Ipay-Auth-Code": "1",
                "X-Ipay-Client-Id": "cid123",
                "X-Ipay-Client-Secret": "sec456",
            },
            {"auth_mode": "fixed_1"},
        )

    monkeypatch.setattr(instantpay_client, "_build_headers", _fake_build_headers)

    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"statuscode": "TXN", "status": "Transaction Successful", "data": {"records": []}}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["headers"] = headers
            return _Response()

    monkeypatch.setattr("portal.services.vendors.instantpay.httpx.Client", _Client)

    res = instantpay_client.request(
        "account_statement",
        {
            "bankProfileId": "0",
            "accountNumber": "9461001200",
            "externalRef": "DB123",
            "pagination": {"pageNumber": 1, "recordsPerPage": 1},
            "filters": {"txnDateFrom": "2026-04-27", "txnDateTo": "2026-04-27"},
        },
    )

    assert captured["auth_code_only"] is True
    assert captured["headers"]["X-Ipay-Auth-Code"] == "1"
    assert captured["headers"]["X-Ipay-Client-Id"] == "cid123"
    assert captured["headers"]["X-Ipay-Client-Secret"] == "sec456"
    assert res["attempted_path"] == "/reports/statement"


def test_business_wallet_balance_uses_auth_code_only_headers(monkeypatch, instantpay_client):
    instantpay_client.identity_auth_mode = "fixed_1"
    monkeypatch.setattr(instantpay_client, "is_configured", lambda: True)
    monkeypatch.setattr(instantpay_client, "_path_candidates", lambda _path: ["/accounts/balance"])

    captured = {"auth_code_only": None, "headers": None, "json": None}

    def _fake_build_headers(**kwargs):
        captured["auth_code_only"] = kwargs.get("auth_code_only")
        return (
            {
                "Content-Type": "application/json",
                "X-Ipay-Auth-Code": "1",
                "X-Ipay-Client-Id": "cid123",
                "X-Ipay-Client-Secret": "sec456",
            },
            {"auth_mode": "fixed_1"},
        )

    monkeypatch.setattr(instantpay_client, "_build_headers", _fake_build_headers)

    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "statuscode": "TXN",
                "status": "Transaction Successful",
                "data": {"balance": {"available": "16.82"}},
            }

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["headers"] = headers
            captured["json"] = json
            return _Response()

    monkeypatch.setattr("portal.services.vendors.instantpay.httpx.Client", _Client)

    res = instantpay_client.request(
        "business_wallet_balance",
        {
            "bankProfileId": "0",
            "accountNumber": "9461001200",
            "externalRef": "DB123",
            "latitude": "20.1236",
            "longitude": "78.3228",
        },
    )

    assert captured["auth_code_only"] is True
    assert captured["headers"]["X-Ipay-Auth-Code"] == "1"
    assert captured["headers"]["X-Ipay-Client-Id"] == "cid123"
    assert captured["headers"]["X-Ipay-Client-Secret"] == "sec456"
    assert captured["json"]["accountType"] == "CURRENT"
    assert "payload" not in captured["json"]
    assert res["attempted_path"] == "/accounts/balance"
