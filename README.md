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
