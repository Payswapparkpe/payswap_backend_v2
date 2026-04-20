"""
Persist Connect chat attachment/voice payloads off huge base64 JSON into default storage.
"""
from __future__ import annotations

import base64
import binascii
import re
import secrets

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Align with frontend MVP cap; server enforces strictly.
MAX_CONNECT_MEDIA_BYTES = 512 * 1024


def persist_connect_binary_from_data_url(thread_id: int, metadata: dict) -> dict:
    """
    If metadata contains data_url (base64 data URI), write bytes to storage and replace
    with storage_path + mime_type + size. Removes data_url from stored metadata.
    """
    if not isinstance(metadata, dict):
        return metadata or {}
    data_url = metadata.get("data_url")
    if not data_url or not isinstance(data_url, str):
        return metadata
    if not data_url.startswith("data:"):
        return metadata
    match = re.match(r"data:([^;]+);base64,(.+)", data_url, re.DOTALL)
    if not match:
        return metadata
    mime = (match.group(1) or "application/octet-stream").strip()[:120]
    b64_payload = match.group(2).strip()
    try:
        raw = base64.b64decode(b64_payload, validate=True)
    except binascii.Error:
        raise ValueError("Invalid attachment encoding.") from None
    if len(raw) > MAX_CONNECT_MEDIA_BYTES:
        raise ValueError(f"Attachment too large. Max {MAX_CONNECT_MEDIA_BYTES // 1024}KB.")
    sub = mime.split("/")[-1].lower() if "/" in mime else "bin"
    safe_ext = re.sub(r"[^a-z0-9]", "", sub)[:12] or "bin"
    path = f"connect/chat/{thread_id}/{secrets.token_hex(10)}.{safe_ext}"
    saved_path = default_storage.save(path, ContentFile(raw))
    out = {k: v for k, v in metadata.items() if k != "data_url"}
    out["storage_path"] = saved_path
    out["mime_type"] = mime
    out["size"] = len(raw)
    if metadata.get("file_name"):
        out["file_name"] = str(metadata["file_name"])[:255]
    return out
