# WooCommerce Catalog Toolkit

Small Python utilities for auditing WooCommerce catalog data and reducing avoidable mistakes during product-data preparation.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Input](https://img.shields.io/badge/Input-CSV-3B82C4)
![Status](https://img.shields.io/badge/Status-Early%20development-64748)

---

## Choose the right tool

| If you need to... | Use | What you get |
|---|---|---|
| Check whether supplier image URLs respond as expected | Image URL Auditor | A CSV with per-URL response details and an aggregate summary |
| Find data-quality issues in a supplier catalog | Catalog CSV Validator | Validation issues and a summary before import |
| Identify SKUs that may be new compared with a store export | New-product preflight | Candidate, review, and full-report CSV files |
| Review CSV validation in a browser without using the CLI | Streamlit interface | A local upload, preview, validation, and report-download workflow |

These tools address separate preparation tasks. The image auditor checks URL responses; it does not inspect image contents. The validator checks catalog fields; it does not determine whether a product already exists. The preflight compares SKUs; it does not validate every field required by WooCommerce's importer.

## Recommended catalog-preparation workflow

For a supplier file that may contain products to add to an existing store:

1. **Preserve the source.** Keep the supplier's original file unchanged and work with a copy.
2. **Validate the data.** Run the Catalog CSV Validator and resolve errors before moving forward. Review warnings as well.
3. **Compare SKUs.** Export the current WooCommerce catalog and run New-product preflight against the supplier copy.
4. **Review candidates manually.** Check repeated or blank SKUs and look for possible duplicates that use different SKUs. The preflight result is a screening aid, not proof that a product is new.
5. **Prepare the import separately.** Map approved fields to WooCommerce's native CSV format. Preflight output is not a ready-to-import file.
6. **Check image URLs when needed.** Run the Image URL Auditor against the relevant image URL column. A successful HTTP response does not guarantee that the file is a valid or suitable product image.
7. **Test cautiously.** Back up the store, test a small batch on staging when possible, and verify the importer mapping and resulting products before processing the full batch.

The toolkit prepares and reviews data locally. It does not connect to a store or perform the import.


## Tool 1: Image URL Auditor

Checks image URLs listed in a CSV and reports HTTP status, content type, server-reported length when available, response time, and error details.

It checks response headers; it does not verify the actual image contents.

### Run the auditor

\`\`\`bash
python src/image_url_auditor.py \\
  --input supplier_images.csv \\
  --output image_audit.csv \\
  --delimiter ";" \\
  --summary-output image_audit_summary.txt
\`\`\`

The CSV report keeps the configured SKU, product-name, and image-URL columns and appends the per-URL audit fields. The console always displays an aggregate summary with counts for `OK`, `CHECK`, `HTTP_ERROR`, `CONNECTION_ERROR`, `INVALID_URL`, and `UNKNOWN`, plus the success rate. Unexpected or unrecognized result values are grouped under `UNKNOWN`, so the result counts always add up to the total number of audited URLs.

The optional `--summary-output` writes the same aggregate summary to a separate plain-text file. Existing output files are never overwritten. The success rate is the percentage of audited URLs classified as `OK`; a `CHECK` response is not counted as a valid image. The CSV report is published before the optional text summary, so a summary-publication error can leave the CSV report available even when the command exits with an error.

## Tool 2: Catalog CSV Validator

Validates supplier catalog files before any import or update. It runs offline, does not connect to WooCommerce, and never modifies the input file.

### Current checks

- Required SKU, product name, and price columns.
- Empty SKUs and product names (errors).
- Duplicate SKUs (case-insensitive, ignoring surrounding whitespace).
- Non-numeric, non-finite, or negative prices (errors).
- Invalid, fractional, or negative stock values (warnings).
- Missing required headers, duplicate headers, and malformed row widths.

Supplier column names can be mapped through function arguments.

### Python example

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

The validator can also generate a summary and export detected issues to a CSV report.

## Tool 3: New-product preflight

Compares a supplier CSV with a current WooCommerce catalog CSV export and separates:

- **New candidates**: a nonblank SKU appears exactly once in the supplier file and was not found in the catalog snapshot.
- **Review required**: SKU already exists, repeats in the supplier file, or is blank.
- **Full report**: every supplier row with its classification and reason.

### Scope and limitations

The preflight tool is a screening step only. It does not connect to WordPress, map arbitrary supplier columns into WooCommerce's import schema, or import, update, delete, or publish products.

Different SKUs can still describe the same product, and an outdated catalog export can produce false new candidates. Human review remains mandatory.

### Example

Export the current WooCommerce catalog using WooCommerce's native product exporter. Keep the supplier original unchanged and work on a CSV copy.

```bash
python src/new_product_preflight.py \
  --supplier examples/supplier_products.csv \
  --catalog examples/existing_catalog.csv \
  --output-dir output/preflight-001
```

When supplier and catalog headers or delimiters differ:

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

The output directory must be new or empty. The tool refuses to overwrite files in a non-empty directory. The summary records SHA-256 hashes of the exact input bytes parsed, the UTC execution time, Python version, SKU columns, delimiters, and supplier row count.

### Output files

- `new_products.csv` — candidate rows, retaining supplier columns and values.
- `review_products.csv` — rows needing review, with `_PREFLIGHT_ROW`, `_PREFLIGHT_STATUS`, and `_PREFLIGHT_REASON`.
- `preflight_report.csv` — all supplier rows with the same review metadata.
- `summary.txt` — row counts, safety notes, execution details, input SHA-256 hashes, and the SKU/delimiter configuration used.

### Safe import procedure

1. Back up the store and export the current catalog immediately before preparing the import.
2. Keep the original supplier workbook unchanged; do all work on copies.
3. Run preflight and manually review the candidate and review files.
4. Resolve possible duplicates that use different SKUs by checking product name, barcode/GTIN, brand, and relevant attributes. The tool does not do fuzzy matching.
5. Map the approved fields to WooCommerce's native product CSV schema; preflight output is **not yet a WooCommerce-ready import file**.
6. Test a very small batch on staging when available, or during a controlled maintenance window after a backup.
7. In the native importer, leave the option to update existing products disabled for a new-only run. Review field mapping before starting.
8. Check importer results, products created, SKUs, images, prices, stock, categories, variations, and existing products after import.

Do not interpret "new candidate" as a guarantee that the product is new. This tool never guarantees that an import cannot affect existing data.

## Tool 4: Catalog Update Planner

Compares supplier values with a WooCommerce catalog export for products whose SKU appears exactly once in both files. It creates a review report; it does not connect to WooCommerce or update products.

### What it classifies

- `UPDATE_REQUIRED`: at least one configured value differs.
- `NO_CHANGE`: all configured values match.
- `NEW_CANDIDATE`: the supplier SKU is not present in the catalog snapshot.
- `REVIEW_REQUIRED`: blank or duplicate SKUs, invalid numeric values, or blank supplier values that must not clear existing data.

Price and stock comparisons are optional, but each comparison requires a supplier and catalog column. Numeric comparison uses decimal values, so `100` and `100.00` are treated as equal. Values must use a plain numeric format; the tool does not guess decimal or thousands separators from locale-specific formats. Stock must be a non-negative whole number.

### Example

Compare supplier price and stock against a WooCommerce CSV export:

```bash
python src/catalog_update_planner.py \
  --supplier supplier.csv \
  --catalog catalog-export.csv \
  --output output/catalog-update-plan.csv \
  --supplier-price-column "Precio" \
  --catalog-price-column "Regular price" \
  --supplier-stock-column "Existencia" \
  --catalog-stock-column "Stock quantity"
```

Use `--supplier-delimiter` and `--catalog-delimiter` when the files use different separators. SKU columns can be mapped independently with `--supplier-sku-column` and `--catalog-sku-column`.

The output preserves supplier columns and appends the supplier row, matched catalog row, planner status, changed fields, and review reason. Existing output files are never overwritten.

**Safety boundary:** this is a planning report, not an import file. Review every proposed change, verify that the catalog export is current, map approved values to WooCommerce's native importer, and test a small batch on staging. Blank supplier values are never treated as instructions to clear existing price or stock values.

## Local graphical interface (first version)

The repository includes an optional Streamlit interface for the Catalog CSV Validator. It lets you upload a supplier CSV, inspect a preview, choose the delimiter, map supplier columns, run the existing validation rules, and download the issue CSV or a ZIP report.

The interface runs locally and does not connect to WordPress or WooCommerce. It does not import, update, delete, or publish products. The uploaded source file is kept unchanged.

### Run the interface

Python 3.10+ is required.

```bash
python -m pip install -r requirements-ui.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit in your browser. The first version accepts UTF-8 CSV files (with or without BOM) up to 50 MB.

The Streamlit dependency is kept separate from the core toolkit. CLI users and automated tests do not need to install it.

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
