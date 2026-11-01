"""Prepare narrowly scoped price and stock updates for existing products."""

from src.catalog_matcher import (
    STATUS_DUPLICATE_CATALOG,
    STATUS_DUPLICATE_SOURCE,
    STATUS_MISSING,
    STATUS_NEW,
    classify_catalog_rows,
)
from .common import BLOCKED, EXCLUDED, READY, REVIEW, build_result, decimal_to_text, is_truthy_export_value, operation_item, parse_non_negative_decimal


def _parse_stock(value):
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    number = parse_non_negative_decimal(text)
    if number is None or number != number.to_integral_value():
        return None
    return int(number)


def prepare_price_stock_updates(
    supplier_rows,
    catalog_rows,
    *,
    supplier_sku_column="SKU",
    catalog_sku_column="SKU",
    price_column="Regular price",
    stock_column="Stock",
    catalog_manage_stock_column="Manage stock?",
):
    """Prepare updates limited to Regular price and Stock for unique SKU matches.

    Blank supplier fields are left unchanged. Invalid values are omitted and
    marked REVIEW. Stock is only prepared when the catalog export explicitly
    confirms that WooCommerce already manages stock for that product.
    """
    classified = classify_catalog_rows(
        supplier_rows, catalog_rows, supplier_sku_column, catalog_sku_column
    )
    catalog_by_row = {number: row for number, row in enumerate(catalog_rows, start=2)}
    items = []
    for match in classified:
        if match["status"] in {STATUS_DUPLICATE_SOURCE, STATUS_DUPLICATE_CATALOG, STATUS_MISSING}:
            items.append(operation_item(match, BLOCKED, match["reason"], sku_column=supplier_sku_column))
            continue
        if match["status"] == STATUS_NEW:
            items.append(operation_item(match, EXCLUDED, "SKU was not found in the WooCommerce catalog; update operation skips new products.", sku_column=supplier_sku_column))
            continue

        catalog_row = catalog_by_row[match["catalog_row_numbers"][0]]
        source = match["row"]
        changes = {}
        issues = []

        raw_price = str(source.get(price_column, "") or "").strip()
        if raw_price:
            price = parse_non_negative_decimal(raw_price)
            if price is None:
                issues.append(f"Invalid price in {price_column!r}; price was not included in the update.")
            else:
                changes["Regular price"] = decimal_to_text(price)

        raw_stock = str(source.get(stock_column, "") or "").strip()
        if raw_stock:
            stock = _parse_stock(raw_stock)
            if stock is None:
                issues.append(f"Invalid stock in {stock_column!r}; stock was not included in the update.")
            elif catalog_manage_stock_column not in catalog_row:
                issues.append("Stock management state is absent from the catalog export; stock was not included.")
            else:
                manages_stock = is_truthy_export_value(catalog_row.get(catalog_manage_stock_column))
                if manages_stock is True:
                    changes["Stock"] = str(stock)
                elif manages_stock is False:
                    issues.append("WooCommerce does not currently manage stock for this product; stock was not included.")
                else:
                    issues.append("Could not interpret WooCommerce stock-management state; stock was not included.")

        if issues:
            status = REVIEW
            reason = " ".join(issues)
        elif not changes:
            status = EXCLUDED
            reason = "No non-empty price or stock values were supplied; nothing to update."
        else:
            status = READY
            reason = "Unique existing SKU; only authorized price/stock fields are prepared."
        items.append(operation_item(match, status, reason, changes, sku_column=supplier_sku_column))
    return build_result(items)
