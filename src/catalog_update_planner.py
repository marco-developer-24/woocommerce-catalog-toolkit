"""Plan safe catalog updates by comparing supplier values with a WooCommerce export.

This tool is a report-only planner. It never connects to or modifies a WooCommerce store.
"""

import argparse
import csv
import os
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:
    from .new_product_preflight import read_csv
    from .catalog_matcher import (
        STATUS_DUPLICATE_CATALOG,
        STATUS_DUPLICATE_SOURCE,
        STATUS_EXISTS,
        STATUS_MISSING,
        STATUS_NEW,
        classify_catalog_rows,
    )
except ImportError:  # Support direct execution as a CLI script.
    from new_product_preflight import read_csv
    from catalog_matcher import (
        STATUS_DUPLICATE_CATALOG,
        STATUS_DUPLICATE_SOURCE,
        STATUS_EXISTS,
        STATUS_MISSING,
        STATUS_NEW,
        classify_catalog_rows,
    )


STATUS_UPDATE = "UPDATE_REQUIRED"
STATUS_UNCHANGED = "NO_CHANGE"
STATUS_REVIEW = "REVIEW_REQUIRED"


def normalize_decimal(value, field_label, row_number, allow_negative=False):
    """Parse a plain decimal value without guessing locale-specific separators."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(
            f"Row {row_number}: {field_label} value {raw!r} is not a valid number."
        ) from exc
    if not number.is_finite():
        raise ValueError(
            f"Row {row_number}: {field_label} must be a finite number."
        )
    if not allow_negative and number < 0:
        raise ValueError(
            f"Row {row_number}: {field_label} cannot be negative."
        )
    return number.normalize()


def compare_catalog_updates(
    supplier_rows,
    catalog_rows,
    supplier_sku_column="SKU",
    catalog_sku_column="SKU",
    supplier_price_column=None,
    catalog_price_column=None,
    supplier_stock_column=None,
    catalog_stock_column=None,
):
    """Compare selected supplier fields against unique SKU matches.

    Blank supplier price/stock values are never interpreted as instructions to
    clear existing values. They cause manual review instead.
    """
    if not any((supplier_price_column, supplier_stock_column)):
        raise ValueError("Configure at least one comparable field: price or stock.")
    if bool(supplier_price_column) != bool(catalog_price_column):
        raise ValueError("Configure both supplier and catalog price columns.")
    if bool(supplier_stock_column) != bool(catalog_stock_column):
        raise ValueError("Configure both supplier and catalog stock columns.")

    classified = classify_catalog_rows(
        supplier_rows, catalog_rows, supplier_sku_column, catalog_sku_column
    )
    catalog_by_row = {
        row_number: row for row_number, row in enumerate(catalog_rows, start=2)
    }
    results = []

    for item in classified:
        status = item["status"]
        changed_fields = []
        reason = item["reason"]
        catalog_row = None

        if status == STATUS_NEW:
            planner_status = STATUS_NEW
            reason = "SKU was not found in the catalog snapshot; review before adding."
        elif status != STATUS_EXISTS:
            planner_status = STATUS_REVIEW
            reason = item["reason"]
        else:
            catalog_row_number = item["catalog_row_numbers"][0]
            catalog_row = catalog_by_row[catalog_row_number]
            review_reasons = []

            for label, supplier_column, catalog_column in (
                ("price", supplier_price_column, catalog_price_column),
                ("stock", supplier_stock_column, catalog_stock_column),
            ):
                if not supplier_column:
                    continue

                supplier_value = str(item["row"].get(supplier_column, "")).strip()
                catalog_value = str(catalog_row.get(catalog_column, "")).strip()
                if not supplier_value:
                    review_reasons.append(
                        f"Supplier {label} is blank; existing value will not be cleared."
                    )
                    continue

                try:
                    supplier_number = normalize_decimal(
                        supplier_value, f"Supplier {label}", item["row_number"]
                    )
                    catalog_number = normalize_decimal(
                        catalog_value, f"Catalog {label}", catalog_row_number
                    ) if catalog_value else None
                except ValueError as exc:
                    review_reasons.append(str(exc))
                    continue

                if label == "stock" and supplier_number is not None:
                    if supplier_number != supplier_number.to_integral_value():
                        review_reasons.append(
                            f"Supplier stock at row {item['row_number']} must be a whole number."
                        )
                        continue
                if label == "stock" and catalog_number is not None:
                    if catalog_number != catalog_number.to_integral_value():
                        review_reasons.append(
                            f"Catalog stock at row {catalog_row_number} is not a whole number."
                        )
                        continue

                if catalog_number is None or supplier_number != catalog_number:
                    changed_fields.append(label)

            if review_reasons:
                planner_status = STATUS_REVIEW
                reason = " ".join(review_reasons)
            elif changed_fields:
                planner_status = STATUS_UPDATE
                reason = "Supplier values differ from the catalog snapshot."
            else:
                planner_status = STATUS_UNCHANGED
                reason = "Compared values match the catalog snapshot."

        results.append({
            "supplier_row_number": item["row_number"],
            "catalog_row_number": (
                item["catalog_row_numbers"][0]
                if len(item["catalog_row_numbers"]) == 1 else ""
            ),
            "sku": item["row"].get(supplier_sku_column, ""),
            "status": planner_status,
            "changed_fields": ", ".join(changed_fields),
            "reason": reason,
            "supplier_row": item["row"],
        })

    return results


def write_update_plan(results, output_path, supplier_headers):
    """Publish a complete update plan without overwriting an existing file."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        *supplier_headers,
        "_PLANNER_SUPPLIER_ROW",
        "_PLANNER_CATALOG_ROW",
        "_PLANNER_STATUS",
        "_PLANNER_CHANGED_FIELDS",
        "_PLANNER_REASON",
    ]
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temp_path = Path(temporary.name)
            writer = csv.DictWriter(
                temporary, fieldnames=headers, extrasaction="ignore"
            )
            writer.writeheader()
            for result in results:
                row = {
                    **result["supplier_row"],
                    "_PLANNER_SUPPLIER_ROW": result["supplier_row_number"],
                    "_PLANNER_CATALOG_ROW": result["catalog_row_number"],
                    "_PLANNER_STATUS": result["status"],
                    "_PLANNER_CHANGED_FIELDS": result["changed_fields"],
                    "_PLANNER_REASON": result["reason"],
                }
                writer.writerow(row)

        # Atomic no-overwrite publication; fails if another process created the file.
        os.link(temp_path, destination)
        temp_path.unlink()
        return destination
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compare supplier price and/or stock values with a WooCommerce CSV export. "
            "Creates a review report only; does not update products."
        )
    )
    parser.add_argument("--supplier", required=True, help="Supplier CSV path")
    parser.add_argument("--catalog", required=True, help="WooCommerce catalog CSV export")
    parser.add_argument("--output", required=True, help="New CSV report path")
    parser.add_argument("--supplier-sku-column", default="SKU")
    parser.add_argument("--catalog-sku-column", default="SKU")
    parser.add_argument("--supplier-delimiter", default=";")
    parser.add_argument("--catalog-delimiter", default=";")
    parser.add_argument("--supplier-price-column")
    parser.add_argument("--catalog-price-column")
    parser.add_argument("--supplier-stock-column")
    parser.add_argument("--catalog-stock-column")
    args = parser.parse_args()

    if len(args.supplier_delimiter) != 1 or len(args.catalog_delimiter) != 1:
        parser.error("Each delimiter must be exactly one character.")
    if not any((args.supplier_price_column, args.supplier_stock_column)):
        parser.error("Configure at least one pair of price or stock columns.")
    if bool(args.supplier_price_column) != bool(args.catalog_price_column):
        parser.error("Configure both supplier and catalog price columns.")
    if bool(args.supplier_stock_column) != bool(args.catalog_stock_column):
        parser.error("Configure both supplier and catalog stock columns.")

    supplier_path = Path(args.supplier).expanduser().resolve()
    catalog_path = Path(args.catalog).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if supplier_path == catalog_path or output_path in (supplier_path, catalog_path):
        parser.error("Supplier, catalog, and output paths must be different.")
    if not supplier_path.is_file() or not catalog_path.is_file():
        parser.error("Both supplier and catalog input files must exist.")
    if output_path.exists():
        parser.error(f"Output file already exists; refusing to overwrite: {output_path}")

    try:
        supplier_headers, supplier_rows, _ = read_csv(
            supplier_path, args.supplier_delimiter, "Supplier CSV"
        )
        catalog_headers, catalog_rows, _ = read_csv(
            catalog_path, args.catalog_delimiter, "Catalog CSV"
        )
        required_supplier = [
            args.supplier_sku_column,
            args.supplier_price_column,
            args.supplier_stock_column,
        ]
        required_catalog = [
            args.catalog_sku_column,
            args.catalog_price_column,
            args.catalog_stock_column,
        ]
        for column in filter(None, required_supplier):
            if column not in supplier_headers:
                raise ValueError(f"Supplier CSV is missing column {column!r}.")
        for column in filter(None, required_catalog):
            if column not in catalog_headers:
                raise ValueError(f"Catalog CSV is missing column {column!r}.")

        results = compare_catalog_updates(
            supplier_rows,
            catalog_rows,
            args.supplier_sku_column,
            args.catalog_sku_column,
            args.supplier_price_column,
            args.catalog_price_column,
            args.supplier_stock_column,
            args.catalog_stock_column,
        )
        write_update_plan(results, output_path, supplier_headers)

        counts = {}
        for result in results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        print(f"Supplier rows reviewed: {len(results)}")
        for status, count in sorted(counts.items()):
            print(f"{status}: {count}")
        print(f"Update plan written to: {output_path}")
    except (OSError, csv.Error, UnicodeError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
