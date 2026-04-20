"""
Latin + Devanagari profanity gate for Connect chat text messages.

English terms: whole-token match (avoids substring false positives like "classic").
Hindi/other: substring phrases loaded from profanity_hi.txt (edit file to extend).

Tests may use CONNECT_PROFANITY_EXTRA_TERMS=comma,separated,tokens.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from django.conf import settings

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def clear_profanity_cache() -> None:
    """Invalidate cached word lists (tests / reload)."""
    _english_terms.cache_clear()
    _hindi_substrings.cache_clear()


def _terms_from_txt_file(path: Path) -> set[str]:
    terms: set[str] = set()
    if not path.is_file():
        return terms
    for line in path.read_text(encoding="utf-8").splitlines():
        w = line.strip().lower()
        if not w or w.startswith("#"):
            continue
        terms.add(w)
    return terms


@lru_cache(maxsize=1)
def _english_terms() -> frozenset[str]:
    terms: set[str] = set()
    terms |= _terms_from_txt_file(_DATA_DIR / "profanity_en.txt")
    raw = getattr(settings, "CONNECT_PROFANITY_EXTRA_TERMS", "") or ""
    for part in raw.split(","):
        p = part.strip().lower()
        if p:
            terms.add(p)
    custom = getattr(settings, "CONNECT_PROFANITY_CUSTOM_FILE", None)
    if custom:
        terms |= _terms_from_txt_file(Path(custom).expanduser())
    return frozenset(terms)


@lru_cache(maxsize=1)
def _hindi_substrings() -> tuple[str, ...]:
    phrases: list[str] = []
    path = _DATA_DIR / "profanity_hi.txt"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            phrases.append(_nfc(s))
    custom_hi = getattr(settings, "CONNECT_PROFANITY_CUSTOM_FILE_HI", None)
    if custom_hi:
        p = Path(custom_hi).expanduser()
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                phrases.append(_nfc(s))
    return tuple(phrases)


def contains_profanity(text: str) -> bool:
    """Return True if `text` must not be delivered as a chat message."""
    if not (text or "").strip():
        return False
    # Voice/attachment payloads may embed huge base64; scan a bounded prefix only.
    sample = text[:16000]
    norm = _nfc(sample)

    en = _english_terms()
    if en:
        for tok in re.findall(r"[A-Za-z]+", norm.lower()):
            if tok in en:
                return True

    for phrase in _hindi_substrings():
        if phrase and phrase in norm:
            return True

    return False


def user_facing_block_message() -> str:
    custom = getattr(settings, "CONNECT_PROFANITY_USER_MESSAGE", None)
    if custom:
        return str(custom)
    return (
        "This message contains language that is not allowed. "
        "Please use respectful words (English/Hindi). / "
        "Is message mein aisi bhasha hai jo allowed nahi hai. Kripya respectful language use karein."
    )
