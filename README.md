# WooCommerce Catalog Toolkit

Small Python utilities for auditing WooCommerce catalog data and reducing avoidable mistakes during product-data preparation.

## Tool 1: Image URL Auditor

Checks image URLs listed in a CSV and reports HTTP status, content type, server-reported length when available, response time, and error details.

It checks response headers; it does not verify the actual image contents.

## Tool 2: New-product preflight

Compares a supplier CSV with a current WooCommerce catalog CSV export and separates:
- **New candidates**: a nonblank SKU appears exactly once in the supplier file and was not found in the catalog snapshot.
- **Review required**: SKU already exists, repeats in the supplier file, or is blank.
- **Full report**: every supplier row with its classification and reason.

The preflight tool is a screening step only. It does not connect to WordPress, map arbitrary supplier columns into WooCommerce's import schema, or import/update/delete/publish products. Different SKUs can still describe the same product, and an outdated catalog export can produce false new candidates. Human review remains mandatory.

### Example

Export the current WooCommerce catalog using WooCommerce's native product exporter. Keep the supplier original unchanged and work on a CSV copy.

```bash
python src/new_product_preflight.py \
  --supplier examples/supplier_products.csv \
  --catalog examples/existing_catalog.csv \
  --output-dir output/preflight-001
```

When supplier and catalog headers/delimiters differ:

```bash
python src/new_product_preflight.py \
  --supplier supplier.csv \
  --catalog catalog-export.csv \
  --supplier-sku-column "Código" \
  --catalog-sku-column "SKU" \
  --supplier-delimiter "," \
  --catalog-delimiter ";" \
  --output-dir output/preflight-002
```

The output directory must be new or empty. The tool refuses to overwrite files in a non-empty directory.

### Output files

- `new_products.csv` — candidate rows, retaining supplier columns and values.
- `review_products.csv` — rows needing review, with `_PREFLIGHT_ROW`, `_PREFLIGHT_STATUS`, and `_PREFLIGHT_REASON`.
- `preflight_report.csv` — all supplier rows with the same review metadata.
- `summary.txt` — row counts and safety notes.

### Safe import procedure

1. Back up the store and export the current catalog immediately before preparing the import.
2. Keep the original supplier workbook unchanged; do all work on copies.
3. Run preflight and manually review the candidate and review files.
4. Resolve possible duplicates that use different SKUs by checking product name, barcode/GTIN, brand, and relevant attributes. The tool does not do fuzzy matching.
5. Map the approved fields to WooCommerce's native product CSV schema; preflight output is **not yet a WooCommerce-ready import file**.
6. Test a very small batch on staging when available, or during a controlled maintenance window after a backup.
7. In the native importer, leave the option to update existing products disabled for a new-only run. Review field mapping before starting.
8. Check importer results, products created, SKUs, images, prices, stock, categories, variations, and existing products after import.

Do not interpret “new candidate” as a guarantee that the product is new. This tool never guarantees that an import cannot affect existing data.

## Requirements

- Python 3.10+
- No third-party Python packages required
- CSV inputs in UTF-8 or UTF-8 with BOM

## Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Tests should not need live external websites; image URL tests use mocked HTTP responses.

## Project status

Early development. The utilities focus on narrow, auditable checks rather than an automatic importer.

## License

No license has been selected yet. All rights reserved unless a license is added to this repository.
