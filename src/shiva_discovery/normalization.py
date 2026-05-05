from __future__ import annotations

import re
import unicodedata


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(value: object) -> str:
    """Normalize names for matching, aliases, and dedupe-friendly comparisons."""
    if value is None:
        return ""

    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold().replace("&", " and ")
    text = _NON_ALNUM_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_header(value: object) -> str:
    """Normalize CSV headers into snake-like lookup keys."""
    return normalize_name(value).replace(" ", "_")


def compact_normalized(value: object) -> str:
    """Normalize and remove spaces for compound Indian temple names."""
    return normalize_name(value).replace(" ", "")
