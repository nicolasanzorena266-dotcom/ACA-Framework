import unicodedata


def normalize_text(value: object) -> str:
    """Normalize user/domain text for matching.

    The function intentionally removes accents using Unicode decomposition
    instead of hardcoded accented characters. This avoids Windows encoding
    issues in source files and keeps matching stable across environments.
    """

    text = str(value or "").lower().strip()
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(without_accents.split())