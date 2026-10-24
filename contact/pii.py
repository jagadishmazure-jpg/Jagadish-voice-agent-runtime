"""PII masking for transcripts, handoff packets, events and logs.

Covers payment cards (Luhn-checked, so order numbers are not masked), email
addresses, phone numbers and US SSNs. Masking runs before anything leaves the
call: the handoff packet, the analytics event sink and the log formatter all
go through ``mask`` / ``mask_obj``.
"""
from __future__ import annotations

import logging
import re
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SSN_RE = re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b")
CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?1[ .-]?)?(?:\(\d{3}\)\s?|\d{3}[ .-])\d{3}[ .-]\d{4}\b")


def luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _card_sub(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group(0))
    if 13 <= len(digits) <= 19 and luhn_ok(digits):
        return "[CARD]"
    return m.group(0)


def mask(text: str) -> str:
    """Return ``text`` with cards, emails, SSNs and phones replaced by tags."""
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = CARD_CANDIDATE_RE.sub(_card_sub, text)
    text = SSN_RE.sub("[SSN]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    return text


def mask_obj(obj: Any) -> Any:
    """Mask every string inside nested dicts / lists / tuples."""
    if isinstance(obj, str):
        return mask(obj)
    if isinstance(obj, dict):
        return {k: mask_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(mask_obj(v) for v in obj)
    return obj


def has_pii(text: str) -> bool:
    return mask(text) != text


class MaskingFormatter(logging.Formatter):
    """Log formatter that masks the final rendered line."""

    def format(self, record: logging.LogRecord) -> str:
        return mask(super().format(record))
