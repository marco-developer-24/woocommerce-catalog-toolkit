"""Pure helpers for stable Streamlit catalog UI behavior."""

import hashlib
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


def category_widget_key(source_category):
    """Build a readable, collision-resistant key from the original category."""
    label = normalize_header(source_category) or "category"
    digest = hashlib.sha256(str(source_category).encode("utf-8")).hexdigest()[:12]
    return f"prep_category_map_{label}_{digest}"


def build_preparation_signature(
    *,
    file_hash,
    catalog_hash,
    delimiter,
    catalog_delimiter,
    columns,
    selected_categories,
    category_mappings,
    category_limits,
    minimum_stock,
):
    """Fingerprint every input that can change the prepared catalog result."""
    return (
        file_hash,
        catalog_hash,
        delimiter,
        catalog_delimiter,
        tuple(columns),
        tuple(sorted(selected_categories, key=str.casefold)),
        tuple(sorted(category_mappings.items())),
        tuple(sorted(category_limits.items(), key=lambda item: item[0].casefold())),
        minimum_stock,
    )
