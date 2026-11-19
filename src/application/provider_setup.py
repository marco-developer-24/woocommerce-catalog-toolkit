"""Application service for inspecting and confirming supplier setup."""

import hashlib

from src.application.catalog_input import detect_delimiter, read_csv_data
from src.application.provider_profile import (
    detect_provider_profile,
    provider_mapping_fingerprint,
    stock_review_policy,
    suggest_provider_columns,
    validate_provider_mapping,
)


MAX_PROVIDER_FILE_BYTES = 50 * 1024 * 1024


def inspect_provider_file(file_bytes, filename, *, delimiter=None, profile=None):
    """Inspect supplier CSV bytes and return data needed to configure its mapping.

    This service is UI-independent. It does not persist files, cache results, or
    modify the supplied bytes.
    """
    if not isinstance(file_bytes, bytes):
        raise TypeError("file_bytes must be bytes.")
    if len(file_bytes) > MAX_PROVIDER_FILE_BYTES:
        raise ValueError("El archivo supera el límite de 50 MB.")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must be a non-empty string.")

    try:
        sample = file_bytes[:8192].decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            "No se pudo leer el archivo como UTF-8. Exportalo como CSV UTF-8."
        ) from exc

    detected_delimiter = detect_delimiter(sample)
    selected_delimiter = detected_delimiter if delimiter is None else delimiter
    if selected_delimiter not in (";", ",", "\t", "|"):
        raise ValueError("Unsupported CSV delimiter.")

    selected_profile = (
        detect_provider_profile(filename) if profile is None else profile
    )
    if selected_profile not in ("NB", "Genérico"):
        raise ValueError(f"Unknown provider profile: {selected_profile}")

    headers, rows, ignored_empty_columns = read_csv_data(
        file_bytes, selected_delimiter
    )
    return {
        "filename": filename,
        "file_hash": hashlib.sha256(file_bytes).hexdigest(),
        "file_bytes": file_bytes,
        "detected_delimiter": detected_delimiter,
        "delimiter": selected_delimiter,
        "profile": selected_profile,
        "headers": headers,
        "rows": rows,
        "ignored_empty_columns": ignored_empty_columns,
        "suggestions": suggest_provider_columns(headers, selected_profile),
    }


def confirm_provider_setup(inspection, mapping):
    """Validate a user-reviewed mapping and build its confirmed provider data."""
    if not isinstance(inspection, dict):
        raise TypeError("inspection must be a dictionary.")
    if not isinstance(mapping, dict):
        raise TypeError("mapping must be a dictionary.")

    valid, message = validate_provider_mapping(mapping)
    if not valid:
        raise ValueError(message)

    required = (
        "filename",
        "file_hash",
        "file_bytes",
        "delimiter",
        "profile",
        "headers",
        "rows",
    )
    missing = [key for key in required if key not in inspection]
    if missing:
        raise ValueError(
            "inspection is missing required keys: " + ", ".join(missing)
        )

    confirmed_mapping = {
        field: mapping.get(field)
        for field in ("sku", "name", "category", "price", "stock")
    }
    return {
        "filename": inspection["filename"],
        "file_hash": inspection["file_hash"],
        "file_bytes": inspection["file_bytes"],
        "delimiter": inspection["delimiter"],
        "profile": inspection["profile"],
        "headers": list(inspection["headers"]),
        "rows": inspection["rows"],
        "mapping": confirmed_mapping,
        "stock_policy": stock_review_policy(confirmed_mapping),
        "mapping_fingerprint": provider_mapping_fingerprint(
            inspection["file_hash"],
            inspection["delimiter"],
            inspection["profile"],
            confirmed_mapping,
        ),
    }
