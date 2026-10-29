#!/usr/bin/env python3
"""Classify supplier CSV rows before adding products to a WooCommerce catalog.

This tool does not import products or convert supplier columns to WooCommerce's
import schema. It creates candidate and review files for human approval.
"""

import argparse
import csv
from pathlib import Path


STATUS_NEW = "NEW_CANDIDATE"
STATUS_EXISTS = "SKU_ALREADY_EXISTS"
STATUS_DUPLICATE = "DUPLICATE_SKU_IN_SOURCE"
STATUS_MISSING = "MISSING_SKU"
OUTPUT_NAMES = (
    "new_products.csv",
    "review_products.csv",
    "preflight_report.csv",
    "summary.txt",
)


def read_csv(path, delimiter, label):
    """Read a complete CSV and reject structurally ambiguous input."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, delimiter=delimiter, strict=True)
            headers = reader.fieldnames
            if not headers:
                raise ValueError(f"{label}: CSV is empty or has no header row.")
            if any(header is None or not header.strip() for header in headers):
                raise ValueError(f"{label}: CSV contains an empty column name.")
            if len(headers) != len(set(headers)):
                raise ValueError(f"{label}: CSV contains duplicate column names.")

            rows = []
            for line_number, row in enumerate(reader, start=2):
                if None in row:
                    raise ValueError(
                        f"{label}: row {line_number} has more fields than the header."
                    )
                if any(value is None for value in row.values()):
                    raise ValueError(
                        f"{label}: row {line_number} has fewer fields than the header."
                    )
                rows.append(row)
            return headers, rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"{label}: could not read CSV: {exc}") from exc


def normalize_sku(value):
    """Normalize whitespace and case for conservative duplicate detection."""
    return (value or "").strip().casefold()


def classify_rows(supplier_headers, supplier_rows, catalog_rows, sku_column):
    """Return classified supplier rows and counts without changing source fields."""
    if sku_column not in supplier_headers:
        raise ValueError(
            f"Supplier CSV is missing SKU column {sku_column!r}. "
            f"Available columns: {', '.join(supplier_headers)}"
        )

    catalog_skus = {
        normalize_sku(row.get(sku_column, ""))
        for row in catalog_rows
        if normalize_sku(row.get(sku_column, ""))
    }

    source_counts = {}
    for row in supplier_rows:
        sku = normalize_sku(row.get(sku_column, ""))
        if sku:
            source_counts[sku] = source_counts.get(sku, 0) + 1

    classified = []
    for row_number, row in enumerate(supplier_rows, start=2):
        sku = normalize_sku(row.get(sku_column, ""))
        if not sku:
            status, reason = STATUS_MISSING, "SKU is blank; cannot safely identify product."
        elif source_counts[sku] > 1:
            status, reason = (
                STATUS_DUPLICATE,
                "SKU appears more than once in the supplier file; review all matching rows.",
            )
        elif sku in catalog_skus:
            status, reason = (
                STATUS_EXISTS,
                "SKU already appears in the catalog export; not included as a new candidate.",
            )
        else:
            status, reason = (
                STATUS_NEW,
                "SKU was not found in the supplied catalog export; verify before import.",
            )

        classified.append({
            "row_number": row_number,
            "row": row,
            "status": status,
            "reason": reason,
        })

    return classified


def write_csv_exclusive(path, headers, rows, delimiter):
    """Create a CSV without overwriting an existing file."""
    with path.open("x", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=headers,
            delimiter=delimiter,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compare a supplier CSV with a WooCommerce catalog export and "
            "separate likely new products from rows requiring review. "
            "This tool does not import products."
        )
    )
    parser.add_argument("--supplier", required=True, help="Supplier CSV path")
    parser.add_argument("--catalog", required=True, help="Existing catalog CSV export")
    parser.add_argument("--output-dir", required=True, help="Directory for new reports")
    parser.add_argument("--sku-column", default="SKU", help="SKU column name in both files")
    parser.add_argument("--supplier-delimiter", default=";", help="Supplier CSV delimiter")
    parser.add_argument("--catalog-delimiter", default=";", help="Catalog CSV delimiter")
    args = parser.parse_args()

    if len(args.supplier_delimiter) != 1 or len(args.catalog_delimiter) != 1:
        parser.error("Each delimiter must be exactly one character.")

    supplier_path = Path(args.supplier).expanduser().resolve()
    catalog_path = Path(args.catalog).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if supplier_path == catalog_path:
        parser.error("Supplier and catalog files must be different.")
    if not supplier_path.is_file():
        parser.error(f"Supplier file does not exist: {supplier_path}")
    if not catalog_path.is_file():
        parser.error(f"Catalog file does not exist: {catalog_path}")
    if output_dir == supplier_path.parent or output_dir == catalog_path.parent:
        parser.error("Choose a dedicated output directory, not an input file's directory.")
    if output_dir.exists() and not output_dir.is_dir():
        parser.error(f"Output path is not a directory: {output_dir}")

    try:
        supplier_headers, supplier_rows = read_csv(
            supplier_path, args.supplier_delimiter, "Supplier CSV"
        )
        catalog_headers, catalog_rows = read_csv(
            catalog_path, args.catalog_delimiter, "Catalog CSV"
        )
        if args.sku_column not in catalog_headers:
            raise ValueError(
                f"Catalog CSV is missing SKU column {args.sku_column!r}. "
                f"Available columns: {', '.join(catalog_headers)}"
            )

        classified = classify_rows(
            supplier_headers, supplier_rows, catalog_rows, args.sku_column
        )

        if output_dir.exists() and any(output_dir.iterdir()):
            raise ValueError(
                f"Output directory is not empty; refusing to overwrite files: {output_dir}"
            )
        output_dir.mkdir(parents=True, exist_ok=True)

        new_rows = [item["row"] for item in classified if item["status"] == STATUS_NEW]
        review_rows = [
            {**item["row"], "_PREFLIGHT_ROW": item["row_number"],
             "_PREFLIGHT_STATUS": item["status"], "_PREFLIGHT_REASON": item["reason"]}
            for item in classified if item["status"] != STATUS_NEW
        ]
        report_rows = [
            {**item["row"], "_PREFLIGHT_ROW": item["row_number"],
             "_PREFLIGHT_STATUS": item["status"], "_PREFLIGHT_REASON": item["reason"]}
            for item in classified
        ]
        report_headers = [
            *supplier_headers, "_PREFLIGHT_ROW", "_PREFLIGHT_STATUS", "_PREFLIGHT_REASON"
        ]
        output_delimiter = args.supplier_delimiter

        write_csv_exclusive(output_dir / "new_products.csv", supplier_headers, new_rows, output_delimiter)
        write_csv_exclusive(
            output_dir / "review_products.csv", report_headers, review_rows, output_delimiter
        )
        write_csv_exclusive(
            output_dir / "preflight_report.csv", report_headers, report_rows, output_delimiter
        )

        counts = {status: sum(item["status"] == status for item in classified)
                  for status in (STATUS_NEW, STATUS_EXISTS, STATUS_DUPLICATE, STATUS_MISSING)}
        summary = [
            "WooCommerce Catalog Toolkit — supplier preflight",
            "",
            f"Supplier file: {supplier_path.name}",
            f"Catalog snapshot: {catalog_path.name}",
            f"Supplier rows checked: {len(classified)}",
            "",
            f"New candidates (not confirmed): {counts[STATUS_NEW]}",
            f"SKU already in catalog: {counts[STATUS_EXISTS]}",
            f"Duplicate SKU in supplier file: {counts[STATUS_DUPLICATE]}",
            f"Missing SKU: {counts[STATUS_MISSING]}",
            "",
            "IMPORTANT:",
            "- This is a preflight report, not an import operation.",
            "- New candidates may still be duplicates under a different SKU.",
            "- The catalog export can be stale or incomplete.",
            "- Review the output and map columns to WooCommerce's import schema.",
            "- Import a small test batch first and verify the live catalog.",
            "",
        ]
        with (output_dir / "summary.txt").open("x", encoding="utf-8", newline="\n") as target:
            target.write("\n".join(summary))

        print(f"Checked {len(classified)} supplier rows.")
        print(f"New candidates: {counts[STATUS_NEW]}")
        print(f"Rows requiring review: {len(review_rows)}")
        print(f"Reports written to: {output_dir}")
    except (OSError, csv.Error, UnicodeError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
