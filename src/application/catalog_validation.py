"""Application workflow for validating a supplier catalog CSV."""

import hashlib
import tempfile
from pathlib import Path

from src.catalog_csv_report import build_catalog_report
from src.catalog_csv_validator import validate_catalog_csv


def run_catalog_validation(
    file_bytes,
    *,
    total_products,
    delimiter,
    mapping,
):
    """Validate uploaded CSV bytes and return domain results for a UI or CLI.

    The source bytes are written to a temporary file because the existing
    validator accepts a filesystem path. The temporary file is always removed.
    This function does not depend on Streamlit and never modifies the source.
    """
    if not isinstance(file_bytes, bytes):
        raise TypeError("file_bytes must be bytes.")
    if not isinstance(mapping, dict):
        raise TypeError("mapping must be a dictionary.")

    required_mapping_keys = {"sku", "name", "price", "stock"}
    missing_keys = required_mapping_keys - mapping.keys()
    if missing_keys:
        raise ValueError(
            "Mapping is missing required keys: " + ", ".join(sorted(missing_keys))
        )

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temporary:
            temporary.write(file_bytes)
            temp_path = Path(temporary.name)

        issues = validate_catalog_csv(
            temp_path,
            delimiter=delimiter,
            sku_column=mapping["sku"],
            name_column=mapping["name"],
            price_column=mapping["price"],
            stock_column=mapping["stock"],
        )
        report = build_catalog_report(total_products, issues)

        return {
            "issues": issues,
            "report": report,
            "file_hash": hashlib.sha256(file_bytes).hexdigest(),
        }
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
