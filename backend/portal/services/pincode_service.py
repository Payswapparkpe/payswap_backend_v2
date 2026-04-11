"""
Pincode lookup via data.gov.in All India Pincode Directory API.
Used by ParkPe for address lookup by pincode (registration, etc.).
"""
import os
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from django.conf import settings

logger = logging.getLogger(__name__)

# Normalize 6-digit Indian pincode
PINCODE_RE = re.compile(r"^\d{6}$")

_DEFAULT_BASE_URL = "https://api.data.gov.in/resource/5c2f62fe-5afa-4119-a499-fec9d604d5bd"


def _get_config() -> Tuple[Optional[str], str]:
    try:
        from core.config import payswap_config
        api_key = getattr(payswap_config, "DATA_GOV_IN_API_KEY", None) or None
        if not api_key:
            api_key = (os.environ.get("DATA_GOV_IN_API_KEY") or "").strip() or None
        base_url = getattr(
            payswap_config,
            "DATA_GOV_IN_PINCODE_RESOURCE_URL",
            _DEFAULT_BASE_URL,
        )
        return api_key or None, (base_url or _DEFAULT_BASE_URL).strip()
    except Exception as e:
        logger.warning("pincode_service config load failed: %s", e)
        api_key = (os.environ.get("DATA_GOV_IN_API_KEY") or "").strip() or None
        return api_key, _DEFAULT_BASE_URL


def _normalize_pincode(pincode: str) -> Optional[str]:
    if not pincode:
        return None
    digits = re.sub(r"\D", "", str(pincode))
    return digits if len(digits) == 6 else None


def _record_to_address(record: Dict[str, Any]) -> Dict[str, str]:
    """Map data.gov.in record to a simple address shape (state, district/city, area)."""
    def get(*keys: str, default: str = "") -> str:
        for k in keys:
            v = record.get(k)
            if v and isinstance(v, str) and v.strip():
                return v.strip()
        return default

    state = get("statename", "state", "StateName")
    district = get("Districtname", "districtname", "district", "DistrictName")
    taluk = get("Taluk", "taluk")
    officename = get("officename", "OfficeName", "officeName")
    division = get("divisionname", "DivisionName")
    region = get("regionname", "RegionName")
    circle = get("circlename", "CircleName")
    pincode = get("pincode", "Pincode")

    # Prefer district as city; else taluk or office name
    city = district or taluk or officename or ""
    # Build a short address line: area / post office
    area = officename or taluk or division or ""

    return {
        "state": state,
        "district": district,
        "city": city,
        "taluk": taluk,
        "officename": officename,
        "area": area,
        "division": division,
        "region": region,
        "circle": circle,
        "pincode": pincode,
    }


def fetch_by_pincode(pincode: str) -> Tuple[bool, Optional[str], List[Dict[str, str]]]:
    """
    Fetch address records for a 6-digit Indian pincode from data.gov.in.

    Returns:
        (success, error_message, list of address dicts).
        Each address dict has: state, district, city, taluk, officename, area, pincode, etc.
    """
    normalized = _normalize_pincode(pincode)
    if not normalized:
        return False, "Invalid pincode. Enter a 6-digit Indian pincode.", []

    api_key, base_url = _get_config()
    if not api_key:
        logger.warning("pincode_service DATA_GOV_IN_API_KEY not configured")
        return False, "Pincode lookup is not configured. Add DATA_GOV_IN_API_KEY to your .env file.", []

    url = base_url.rstrip("/")
    # Request max records per call (data.gov.in often allows 1000) so all POs under pincode are returned
    params = {
        "api-key": api_key,
        "format": "json",
        "limit": 1000,
        "offset": 0,
        "filters[pincode]": normalized,
    }
    try:
        # data.gov.in can be slow; use 25s timeout to avoid 503 from our API
        resp = requests.get(url, params=params, timeout=25)
        resp.raise_for_status()
        data = resp.json()
    except requests.Timeout as e:
        logger.warning("pincode_service timeout for pincode=%s: %s", normalized[:2] + "****", e)
        return False, "Address service is taking too long. Please try again in a moment.", []
    except requests.RequestException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        body = ""
        if hasattr(e, "response") and e.response is not None:
            try:
                body = (e.response.text or "")[:200]
            except Exception:
                pass
        logger.warning(
            "pincode_service request failed for pincode=%s: %s (status=%s, body=%s)",
            normalized[:2] + "****", e, status, body
        )
        if status == 403:
            return False, "Address service access denied. Please try again later.", []
        if status and status >= 500:
            return False, "Address service is temporarily unavailable. Please try again in a few minutes.", []
        return False, "Unable to fetch address. Please try again.", []
    except (ValueError, KeyError) as e:
        logger.warning("pincode_service parse failed: %s", e)
        return False, "Invalid response from address service.", []

    records = data.get("records") if isinstance(data, dict) else None
    if not records or not isinstance(records, list):
        return True, None, []

    # Dedupe by (state, district, officename) so each post office / office shows as separate option
    # Previously (state, district, city) merged all offices in same city into one
    seen: set = set()
    out: List[Dict[str, str]] = []
    for r in records:
        if not isinstance(r, dict):
            continue
        addr = _record_to_address(r)
        key = (addr["state"], addr["district"], addr["officename"] or addr["taluk"] or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(addr)

    return True, None, out
