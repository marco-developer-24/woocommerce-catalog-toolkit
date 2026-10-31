#!/usr/bin/env python3
"""Validate product catalog CSV data without modifying the source file."""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path


ISSUE_FIELDS = ("row_number", "field", "value", "severity", "code", "message")


def _issue(row_number, field, value, code, message):
    return {
        "row_number": row_number,
        "field": field,
        "value": value,
        "severity": "error",
        "code": code,
        "message": message,
    }


def _read_rows(input_path, delimiter):
    if not isinstance(delimiter, str) or len(delimiter) != 1:
        raise ValueError("Delimiter must be exactly one character.")

    with open(input_path, encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=delimiter, strict=True)
        headers = reader.fieldnames

        if not headers:
            raise ValueError("Input CSV is empty or has no header row.")
        if any(header is None or not header.strip() for header in headers):
            raise ValueError("CSV contains an empty column name.")
        if len(headers) != len(set(headers)):
            raise ValueError("CSV contains duplicate column names.")

        rows = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"CSV row {row_number} has more fields than the header."
                )
            if any(value is None for value in row.values()):
                raise ValueError(
                    f"CSV row {row_number} has fewer fields than the header."
                )
            rows.append((row_number, row))

    return headers, rows


def validate_catalog_csv(
    input_path,
    delimiter=";",
    sku_column="SKU",
    name_column="PRODUCT_NAME",
    price_column="PRICE",
    stock_column="STOCK",
):
    """Return data-quality issues found in a supplier catalog CSV.

    SKU, product name and price columns are required. Stock is validated only
    when its configured column is present. Column names can be mapped to a
    supplier's headers through the keyword arguments.

    The source file is opened read-only and is never changed.
    """
    configured_columns = [sku_column, name_column, price_column]
    if stock_column is not None:
        configured_columns.append(stock_column)
    if any(not isinstance(column, str) or not column.strip()
           for column in configured_columns):
        raise ValueError("Configured column names must be non-empty strings.")
    if len(configured_columns) != len(set(configured_columns)):
        raise ValueError("Configured column names must be different.")

    headers, rows = _read_rows(input_path, delimiter)
    required = (sku_column, name_column, price_column)
    missing = [column for column in required if column not in headers]
    if missing:
        raise ValueError("Missing required CSV columns: " + ", ".join(missing))

    issues = []
    seen_skus = {}

    for row_number, row in rows:
        sku = row[sku_column].strip()
        name = row[name_column].strip()
        price_text = row[price_column].strip()

        if not sku:
            issues.append(_issue(
                row_number, sku_column, row[sku_column],
                "empty_sku", "SKU must not be empty."
            ))
        else:
            normalized_sku = sku.casefold()
            if normalized_sku in seen_skus:
                issues.append(_issue(
                    row_number, sku_column, sku,
                    "duplicate_sku",
                    f"SKU duplicates the value on row {seen_skus[normalized_sku]}."
                ))
            else:
                seen_skus[normalized_sku] = row_number

        if not name:
            issues.append(_issue(
                row_number, name_column, row[name_column],
                "empty_product_name", "Product name must not be empty."
            ))

        try:
            price = Decimal(price_text)
            if not price.is_finite():
                raise InvalidOperation
            if price < 0:
                issues.append(_issue(
                    row_number, price_column, price_text,
                    "negative_price", "Price must not be negative."
                ))
        except (InvalidOperation, ValueError):
            issues.append(_issue(
                row_number, price_column, price_text,
                "invalid_price", "Price must be a finite numeric value."
            ))

        if stock_column is not None and stock_column in headers:
            stock_text = row[stock_column].strip()
            try:
                stock = Decimal(stock_text)
                if not stock.is_finite() or stock != stock.to_integral_value():
                    raise InvalidOperation
                if stock < 0:
                    issues.append(_issue(
                        row_number, stock_column, stock_text,
                        "negative_stock", "Stock must not be negative."
                    ))
            except (InvalidOperation, ValueError):
                issues.append(_issue(
                    row_number, stock_column, stock_text,
                    "invalid_stock", "Stock must be a non-negative integer."
                ))

    return issues
