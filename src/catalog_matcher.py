"""Shared SKU matching logic for supplier and WooCommerce catalog snapshots.

The matcher is deliberately conservative: only a unique, nonblank SKU on both
sides is considered an existing-product match.
"""

STATUS_NEW = "NEW_CANDIDATE"
STATUS_EXISTS = "SKU_ALREADY_EXISTS"
STATUS_DUPLICATE_SOURCE = "DUPLICATE_SKU_IN_SOURCE"
STATUS_DUPLICATE_CATALOG = "DUPLICATE_SKU_IN_CATALOG"
STATUS_MISSING = "MISSING_SKU"


def normalize_sku(value):
    """Normalize only surrounding whitespace and letter case."""
    return (value or "").strip().casefold()


def _validate_column_name(column, label):
    if not isinstance(column, str) or not column.strip():
        raise ValueError(f"{label} SKU column must be a non-empty string.")


def classify_catalog_rows(
    supplier_rows,
    catalog_rows,
    supplier_sku_column="SKU",
    catalog_sku_column="SKU",
):
    """Classify every supplier row against a WooCommerce catalog snapshot.

    Returned items preserve source row values and include the supplier CSV row
    number, normalized SKU, status, explanation, and matching catalog row
    numbers. A product is a safe match only when its SKU occurs exactly once
    in each file.
    """
    _validate_column_name(supplier_sku_column, "Supplier")
    _validate_column_name(catalog_sku_column, "Catalog")

    catalog_occurrences = {}
    for row_number, row in enumerate(catalog_rows, start=2):
        sku = normalize_sku(row.get(catalog_sku_column, ""))
        if sku:
            catalog_occurrences.setdefault(sku, []).append(row_number)

    supplier_counts = {}
    for row in supplier_rows:
        sku = normalize_sku(row.get(supplier_sku_column, ""))
        if sku:
            supplier_counts[sku] = supplier_counts.get(sku, 0) + 1

    classified = []
    for row_number, row in enumerate(supplier_rows, start=2):
        sku = normalize_sku(row.get(supplier_sku_column, ""))
        catalog_rows_for_sku = catalog_occurrences.get(sku, []) if sku else []

        if not sku:
            status = STATUS_MISSING
            reason = "SKU is blank; the product cannot be safely identified."
        elif supplier_counts[sku] > 1:
            status = STATUS_DUPLICATE_SOURCE
            reason = (
                "SKU appears more than once in the supplier file; "
                "review all matching rows."
            )
        elif len(catalog_rows_for_sku) > 1:
            status = STATUS_DUPLICATE_CATALOG
            reason = (
                "SKU appears more than once in the WooCommerce catalog export; "
                "the matching product is ambiguous."
            )
        elif len(catalog_rows_for_sku) == 1:
            status = STATUS_EXISTS
            reason = "SKU appears exactly once in the WooCommerce catalog export."
        else:
            status = STATUS_NEW
            reason = (
                "SKU was not found in the supplied catalog export; "
                "verify the catalog snapshot before import."
            )

        classified.append({
            "row_number": row_number,
            "row": row,
            "normalized_sku": sku,
            "status": status,
            "reason": reason,
            "catalog_row_numbers": catalog_rows_for_sku,
        })

    return classified
