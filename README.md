# WooCommerce Catalog Toolkit

Python utilities for auditing WooCommerce catalog data.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Input](https://img.shields.io/badge/Input-CSV-3B82C4)
![Status](https://img.shields.io/badge/Status-Early%20development-64748B)

---

## Current tool: Image URL Auditor

Checks image URLs listed in a CSV file and generates an audit report.

The report includes:
- HTTP status code
- Response content type
- Server-reported content length, when available
- Response time
- Result classification and error details

The tool identifies empty or invalid URLs, HTTP errors, and successful responses that do not declare an image content type.

> **Scope note:** the auditor checks response headers. It does not verify the actual image contents.

## Catalog CSV Validator

Validates supplier catalog files before any import or update. It runs offline,
does not connect to WooCommerce, and never modifies the input file.

Current checks:
- Required SKU, product name, and price columns.
- Empty SKUs and product names (errors).
- Duplicate SKUs (case-insensitive, ignoring surrounding whitespace).
- Non-numeric, non-finite, or negative prices (errors).
- Invalid, fractional, or negative stock values (warnings).
- Missing required headers, duplicate headers, and malformed row widths.

Supplier column names can be mapped through function arguments. For example:

```python
from src.catalog_csv_validator import validate_catalog_csv
from src.catalog_csv_report import build_catalog_report, export_issues_csv

issues = validate_catalog_csv(
    "supplier_catalog.csv",
    delimiter=",",
    sku_column="ProductCode",
    name_column="Description",
    price_column="NetPrice",
    stock_column="Available",
)

summary = build_catalog_report(total_products=120, issues=issues)
print(summary)
export_issues_csv(issues, "catalog_issues.csv")
```

The summary reports total products, products without errors, products with
errors or warnings, and issue counts by severity. Stock issues are warnings:
they can be reviewed separately without treating the entire product row as
invalid for other fields.

The CSV report contains the row number, field, original value, severity,
machine-readable code, and explanation. Existing report files are protected
by default; pass `overwrite=True` explicitly to replace one.

Structural CSV errors (such as missing required columns or malformed rows)
raise `ValueError`. Example input: `examples/sample_catalog.csv`.

## Requirements

- Python 3.10 or newer
- No third-party packages required

## Input CSV

By default, the CSV must contain these columns:

- SKU
- PRODUCT_NAME
- IMAGE_URL

The default delimiter is a semicolon. Column names, delimiter, and timeout can be customized through command-line arguments.

## Usage

    python src/image_url_auditor.py --input examples/sample_products.csv --output image_audit.csv

## Tests

    python -m unittest discover -s tests -p "test_*.py" -v

The automated tests use mocked HTTP responses and do not require external websites.

## Project status

Early development. The focus is on small, reusable tools for catalog auditing and data quality.

## License

No license has been selected yet. All rights reserved unless a license is added to this repository.
