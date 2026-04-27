from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from portal.utils.logging_helper import get_logger

logger = get_logger("portal.notifications.push_fcm")
_FCM_SCOPE = ["https://www.googleapis.com/auth/firebase.messaging"]


@dataclass
class FcmSendResult:
    success: bool
    provider_message_id: str = ""
    error_message: str = ""
    response_payload: dict[str, Any] | None = None
    token_invalid: bool = False


def _load_service_account_info() -> dict[str, Any]:
    inline_json = getattr(settings, "FCM_SERVICE_ACCOUNT_JSON", None)
    if inline_json:
        return json.loads(str(inline_json))

    file_path = getattr(settings, "FCM_SERVICE_ACCOUNT_PATH", None)
    if not file_path:
        raise ValueError("FCM service account not configured")
    content = Path(file_path).expanduser().read_text(encoding="utf-8")
    return json.loads(content)


def _get_project_id(credentials_info: dict[str, Any]) -> str:
    configured = str(getattr(settings, "FCM_PROJECT_ID", "") or "").strip()
    if configured:
        return configured
    inferred = str(credentials_info.get("project_id") or "").strip()
    if inferred:
        return inferred
    raise ValueError("FCM project id missing")


def _access_token(credentials_info: dict[str, Any]) -> str:
    credentials = service_account.Credentials.from_service_account_info(credentials_info, scopes=_FCM_SCOPE)
    credentials.refresh(Request())
    if not credentials.token:
        raise ValueError("FCM access token unavailable")
    return credentials.token


def send_fcm_notification(*, token: str, title: str, body: str, data: dict[str, str] | None = None) -> FcmSendResult:
    try:
        info = _load_service_account_info()
        project_id = _get_project_id(info)
        access_token = _access_token(info)
    except Exception as exc:  # noqa: BLE001
        return FcmSendResult(success=False, error_message=f"fcm_config_error: {exc}")

    payload: dict[str, Any] = {
        "message": {
            "token": token,
            "notification": {
                "title": title,
                "body": body,
            },
        }
    }
    if data:
        payload["message"]["data"] = {k: str(v) for k, v in data.items()}

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp_json = resp.json() if resp.content else {}
    except Exception as exc:  # noqa: BLE001
        return FcmSendResult(success=False, error_message=f"fcm_http_error: {exc}")

    if 200 <= resp.status_code < 300:
        provider_message_id = str(resp_json.get("name") or "")
        return FcmSendResult(
            success=True,
            provider_message_id=provider_message_id,
            response_payload=resp_json if isinstance(resp_json, dict) else {"raw": str(resp_json)},
        )

    error_message = ""
    token_invalid = False
    if isinstance(resp_json, dict):
        err = resp_json.get("error") or {}
        message = str(err.get("message") or "")
        status = str(err.get("status") or "")
        error_message = f"{status}: {message}".strip(": ")
        details = err.get("details") or []
        details_blob = json.dumps(details, ensure_ascii=True).lower() if details else ""
        token_invalid = "unregistered" in details_blob or "invalid argument" in message.lower()
    else:
        error_message = f"fcm_error_status_{resp.status_code}"

    logger.warning(
        "fcm_send_failed",
        extra={
            "status_code": resp.status_code,
            "token_prefix": token[:18],
            "error_message": error_message,
        },
    )
    return FcmSendResult(
        success=False,
        error_message=error_message or f"fcm_error_status_{resp.status_code}",
        response_payload=resp_json if isinstance(resp_json, dict) else {"raw": str(resp_json)},
        token_invalid=token_invalid,
    )
