"""Compatibility exports for helpers used by the legacy Streamlit interface."""

import hashlib

from src.application.column_mapping import normalize_header, suggest_column


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
