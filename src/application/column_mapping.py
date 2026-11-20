"""Pure helpers for exact, normalized CSV column matching."""

import unicodedata


def normalize_header(value):
    """Normalize labels for accent-insensitive, exact alias matching."""
    normalized = unicodedata.normalize("NFKD", str(value))
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return "".join(
        char.casefold() for char in without_accents if char.isalnum()
    )


def suggest_column(headers, aliases):
    """Return the index of an exact normalized alias match, or None."""
    normalized_aliases = {normalize_header(alias) for alias in aliases}
    for index, header in enumerate(headers):
        if normalize_header(header) in normalized_aliases:
            return index
    return None
