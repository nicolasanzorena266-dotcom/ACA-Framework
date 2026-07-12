from __future__ import annotations

import re
import unicodedata


def repair_mojibake(value: object) -> str:
    """Repair common UTF-8 text decoded as Latin-1 or CP1252."""

    text = str(value or "")
    if not _looks_mojibaked(text):
        return text

    for encoding in ("latin1", "cp1252"):
        try:
            repaired = text.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if repaired != text:
            return repaired

    return text


def normalize_text(value: object) -> str:
    """Normalize text for stable deterministic matching.

    This is ACA's framework-level text normalization boundary. It is
    domain-agnostic, deterministic and idempotent. Punctuation is preserved for
    compatibility with existing runtime contracts.
    """

    text = repair_mojibake(value).lower().strip()
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return collapse_spaces(without_accents)


def normalize_search_text(value: object, *, typo_tolerant: bool = False) -> str:
    """Normalize text for token/substring search.

    Search normalization removes punctuation and can optionally collapse common
    repeated-letter typos while keeping the core normalization contract shared.
    """

    text = normalize_text(value)
    if typo_tolerant:
        text = re.sub(r"([aeiou])\1+", r"\1", text)
        text = re.sub(r"([^aeiou\s])\1{2,}", r"\1", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return collapse_spaces(text)


def collapse_spaces(value: object) -> str:
    return " ".join(str(value or "").split())


def _looks_mojibaked(text: str) -> bool:
    return any(marker in text for marker in ("Ã", "Â", "â"))
