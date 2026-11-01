"""Select and validate supplier rows for the add-products operation."""

from src.catalog_matcher import (
    STATUS_DUPLICATE_CATALOG,
    STATUS_DUPLICATE_SOURCE,
    STATUS_EXISTS,
    STATUS_MISSING,
    STATUS_NEW,
    classify_catalog_rows,
)
from .common import BLOCKED, EXCLUDED, READY, build_result, decimal_to_text, operation_item, parse_non_negative_decimal


def prepare_add_products(
    supplier_rows,
    catalog_rows,
    *,
    supplier_sku_column="SKU",
    catalog_sku_column="SKU",
    name_column="Name",
    price_column="Regular price",
):
    """Classify rows for a new-products run; never changes existing products.

    Existing SKUs are excluded. Missing or ambiguous SKUs and invalid required
    fields are blocked. Only unique new SKUs with a name and a finite,
    non-negative price are marked READY. Input dictionaries are not mutated.
    """
    classified = classify_catalog_rows(
        supplier_rows, catalog_rows, supplier_sku_column, catalog_sku_column
    )
    items = []
    for match in classified:
        row = match["row"]
        if match["status"] == STATUS_EXISTS:
            items.append(operation_item(match, EXCLUDED, "SKU already exists; add operation will not overwrite it."))
            continue
        if match["status"] in {STATUS_DUPLICATE_SOURCE, STATUS_DUPLICATE_CATALOG, STATUS_MISSING}:
            items.append(operation_item(match, BLOCKED, match["reason"]))
            continue
        name = str(row.get(name_column, "") or "").strip()
        price = parse_non_negative_decimal(row.get(price_column, ""))
        problems = []
        if not name:
            problems.append(f"Missing required product name in {name_column!r}.")
        raw_price = str(row.get(price_column, "") or "").strip()
        if price is None:
            problems.append(f"Missing or invalid non-negative price in {price_column!r}.")
        if problems:
            items.append(operation_item(match, BLOCKED, " ".join(problems)))
            continue
        items.append(operation_item(
            match,
            READY,
            "Unique new SKU with required fields validated; product remains unpublished.",
            {
                "SKU": str(row.get(supplier_sku_column, "")).strip(),
                "Name": name,
                "Regular price": decimal_to_text(price),
                "Published": "0",
                "Type": "simple",
            },
        ))
    return build_result(items)
