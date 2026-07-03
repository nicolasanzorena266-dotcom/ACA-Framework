import unicodedata


def repair_mojibake(text: str) -> str:
    """Repair common UTF-8 text that was decoded as Latin-1/CP1252."""

    markers = ["Ãƒ", "Ã‚"]
    if not any(marker in text for marker in markers):
        return text

    for encoding in ("latin1", "cp1252"):
        try:
            repaired = text.encode(encoding).decode("utf-8")
            if repaired != text:
                return repaired
        except UnicodeError:
            continue

    return text


def normalize_text(value: object) -> str:
    """Normalize user/domain text for stable matching."""

    text = repair_mojibake(str(value or ""))
    text = text.lower().strip()
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(without_accents.split())