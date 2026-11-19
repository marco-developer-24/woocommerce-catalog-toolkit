"""Application service for inspecting and matching a WooCommerce catalog export."""

import hashlib

from src.application.catalog_input import detect_delimiter, read_csv_data
from src.application.column_mapping import suggest_column
from src.application.woocommerce_categories import discover_destination_categories
from src.catalog_matcher import (
    STATUS_DUPLICATE_CATALOG,
    STATUS_DUPLICATE_SOURCE,
    STATUS_EXISTS,
    STATUS_MISSING,
    STATUS_NEW,
    classify_catalog_rows,
)


MAX_STORE_FILE_BYTES = 50 * 1024 * 1024
STORE_COLUMN_ALIASES = {
    "sku": ("SKU", "Product SKU", "Código SKU", "Codigo SKU"),
    "categories": ("Categories", "Categorías", "Categorias", "Category"),
}


def inspect_store_file(file_bytes, filename, *, delimiter=None):
    """Read a WooCommerce export and suggest SKU/category columns.

    The result represents only the uploaded snapshot. It does not imply that
    the export contains every product or every category in the live store.
    """
    if not isinstance(file_bytes, bytes):
        raise TypeError("file_bytes must be bytes.")
    if len(file_bytes) > MAX_STORE_FILE_BYTES:
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

    headers, rows, ignored_empty_columns = read_csv_data(
        file_bytes, selected_delimiter
    )
    suggestions = {}
    for field, aliases in STORE_COLUMN_ALIASES.items():
        index = suggest_column(headers, aliases)
        suggestions[field] = headers[index] if index is not None else None

    return {
        "filename": filename,
        "file_hash": hashlib.sha256(file_bytes).hexdigest(),
        "file_bytes": file_bytes,
        "detected_delimiter": detected_delimiter,
        "delimiter": selected_delimiter,
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
        "ignored_empty_columns": ignored_empty_columns,
        "suggestions": suggestions,
    }


def confirm_store_setup(provider, inspection, mapping):
    """Validate the store SKU mapping and compare it with the confirmed provider."""
    if not isinstance(provider, dict):
        raise TypeError("provider must be a dictionary.")
    if not isinstance(inspection, dict):
        raise TypeError("inspection must be a dictionary.")
    if not isinstance(mapping, dict):
        raise TypeError("mapping must be a dictionary.")

    required_provider_keys = ("file_hash", "rows", "mapping")
    missing_provider = [
        key for key in required_provider_keys if key not in provider
    ]
    if missing_provider:
        raise ValueError(
            "provider is missing required keys: " + ", ".join(missing_provider)
        )

    required_inspection_keys = (
        "filename", "file_hash", "delimiter", "headers", "rows"
    )
    missing_inspection = [
        key for key in required_inspection_keys if key not in inspection
    ]
    if missing_inspection:
        raise ValueError(
            "inspection is missing required keys: "
            + ", ".join(missing_inspection)
        )

    sku_column = mapping.get("sku")
    category_column = mapping.get("categories")
    headers = inspection["headers"]
    if not isinstance(sku_column, str) or not sku_column.strip():
        raise ValueError("La columna SKU de WooCommerce es obligatoria.")
    if sku_column not in headers:
        raise ValueError("La columna SKU seleccionada no existe en el archivo.")
    if category_column and category_column not in headers:
        raise ValueError("La columna de categorías seleccionada no existe en el archivo.")
    if category_column == sku_column:
        raise ValueError("SKU y categorías deben usar columnas diferentes.")

    supplier_sku_column = provider["mapping"].get("sku")
    if not supplier_sku_column:
        raise ValueError("El proveedor confirmado no tiene una columna SKU válida.")

    classified = classify_catalog_rows(
        provider["rows"],
        inspection["rows"],
        supplier_sku_column=supplier_sku_column,
        catalog_sku_column=sku_column,
    )
    counts = {
        STATUS_NEW: 0,
        STATUS_EXISTS: 0,
        STATUS_DUPLICATE_SOURCE: 0,
        STATUS_DUPLICATE_CATALOG: 0,
        STATUS_MISSING: 0,
    }
    for item in classified:
        counts[item["status"]] += 1

    categories = (
        discover_destination_categories(inspection["rows"], category_column)
        if category_column
        else []
    )
    confirmed_mapping = {"sku": sku_column, "categories": category_column}
    return {
        "filename": inspection["filename"],
        "file_hash": inspection["file_hash"],
        "delimiter": inspection["delimiter"],
        "headers": list(headers),
        "rows": inspection["rows"],
        "mapping": confirmed_mapping,
        "provider_file_hash": provider["file_hash"],
        "classified_supplier_rows": classified,
        "summary": {
            "supplier_rows": len(provider["rows"]),
            "store_rows": len(inspection["rows"]),
            "new_candidates": counts[STATUS_NEW],
            "existing": counts[STATUS_EXISTS],
            "duplicate_supplier_sku": counts[STATUS_DUPLICATE_SOURCE],
            "duplicate_store_sku": counts[STATUS_DUPLICATE_CATALOG],
            "missing_supplier_sku": counts[STATUS_MISSING],
            "observed_categories": len(categories),
        },
        "observed_categories": categories,
    }
