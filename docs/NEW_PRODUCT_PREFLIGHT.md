# Supplier preflight: safe new-product additions

This workflow prepares a supplier CSV for review before importing new products into WooCommerce. It does not connect to WordPress and does not import or update products.

## Workflow

1. Export the existing WooCommerce catalog to CSV. The export must contain a `SKU` column.
2. Keep the original supplier file unchanged and save a copy as CSV if it is an Excel workbook.
3. Run the preflight tool against the supplier CSV and the catalog export.
4. Review `summary.txt` and `preflight_report.csv`.
5. Inspect `review_products.csv` and resolve missing/duplicate/existing SKU cases.
6. Map the approved new-product data to WooCommerce's product CSV schema. The output is not automatically schema-mapped yet.
7. Import a small sample first, with WooCommerce's option to update existing products disabled.
8. Verify the created products in the store and check that existing products were not modified.

## Requirements

- Python 3.10+
- CSV inputs saved as UTF-8 or UTF-8 with BOM
- Supplier and catalog export must use a `SKU` column by default
- Delimiter defaults to semicolon (`;`); set the appropriate delimiter for each input when needed

## Example

```bash
python src/new_product_preflight.py \
  --supplier examples/supplier_products.csv \
  --catalog examples/existing_catalog.csv \
  --output-dir output/preflight-001
```

If the supplier file uses commas and the WooCommerce export uses semicolons:

```bash
python src/new_product_preflight.py \
  --supplier examples/supplier_products.csv \
  --catalog examples/existing_catalog.csv \
  --supplier-delimiter "," \
  --catalog-delimiter ";" \
  --output-dir output/preflight-001
```

## Generated files

- `new_products.csv`: rows whose nonblank SKU occurs exactly once in the supplier file and was not found in the catalog export.
- `review_products.csv`: rows with missing SKU, repeated supplier SKU, or SKU already found in the catalog export.
- `preflight_report.csv`: all supplier rows with classification and reason.
- `summary.txt`: counts and important caveats.

The tool refuses to overwrite files in a non-empty output directory.

## Important limitations

- A product is classified as a new candidate only by SKU comparison. Different SKUs can still represent the same product.
- Comparison uses a catalog export snapshot. If the export is stale, missing SKUs can go undetected.
- SKU matching trims surrounding whitespace and ignores case; the original SKU values in output are preserved.
- It does not infer product categories, brands, attributes, variations, image URLs, tax, prices, or WooCommerce-specific field mappings.
- It does not import, publish, update, delete, or call WooCommerce.
- Do not treat a candidate as safe without review. Back up the store, test a small batch, disable WooCommerce's update-existing option for new-only runs, and verify the result.
