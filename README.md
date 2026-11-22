<div align="center">

# WooCommerce Catalog Toolkit

**Local catalog preparation for WooCommerce: inspect supplier data, compare SKUs, select products, and review a controlled CSV export.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Interface](https://img.shields.io/badge/Interface-NiceGUI-2563EB)
![Processing](https://img.shields.io/badge/Processing-Local-15803d)
![Store access](https://img.shields.io/badge/WooCommerce-No%20direct%20writes-64748b)

</div>

WooCommerce Catalog Toolkit is a local Python application for preparing **new product listings** from a supplier CSV. It helps inspect source data, map columns, compare supplier SKUs against a WooCommerce product export, classify rows, select products manually, map supplier categories to observed WooCommerce categories, and generate a CSV for review.

The application does not connect to a WooCommerce store, write to its database, or import products. The generated file must be reviewed and imported separately through WooCommerce.

## What the application does

The current NiceGUI workflow is organized into four stages:

1. **Files**: load a supplier CSV and, optionally, a WooCommerce product export.
2. **Validation and comparison**: confirm column mappings, compare SKUs, and classify supplier rows for new-product preparation.
3. **Product selection**: review supplier categories, configure WooCommerce destination categories, and select eligible products individually.
4. **Review and export**: inspect the exportable selection and download a WooCommerce CSV for new products.

### Selection rules

- Products start **unselected**. The operator chooses products individually.
- There are no automatic category quotas or category-level bulk selection.
- Initial product ordering is by ascending supplier price; price does not decide which products are selected.
- Only technically eligible products can be selected.
- Selection is preserved while searching, sorting, or opening and closing categories during the session.
- Supplier category and WooCommerce destination are separate concepts. A suggested destination must be confirmed; changing a destination invalidates its previous confirmation.
- A product is exportable only when it is selected, technically eligible, and its destination category is confirmed.

### Product classification

Supplier rows are classified before commercial selection:

- **Ready**: required data and SKU checks pass for a potential new product.
- **Review**: a value needs human review before it can be used.
- **Blocked**: required data is invalid or insufficient.
- **Existing**: the SKU was found in the supplied WooCommerce export and is excluded from new-product preparation.

The WooCommerce CSV is a snapshot, not a live connection or necessarily a complete inventory of every category or product in the store. Its freshness and completeness affect comparison quality.

## Run locally

Python 3.10 or newer is required.

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-ui.txt
python app.py
```

If PowerShell activation is restricted, invoke the virtual environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
.\.venv\Scripts\python.exe app.py
```

The interface runs locally in a browser. The optional UI dependencies are separate from the core Python modules.

## Input files

### Supplier CSV

- UTF-8 or UTF-8 with BOM.
- Maximum upload size: 50 MB.
- The application inspects the delimiter and suggests a supplier profile and column mappings.
- Review the suggested SKU, product name, category, price, and optional stock columns before confirming.

### WooCommerce product export

Export products from **WooCommerce → Products → Export**.

- The export is used as a reference for SKU comparison and observed destination categories.
- Confirm the SKU column and, where available, the category column.
- If the store export is omitted, the application can continue only after the omission is explicit. Existing SKUs cannot then be checked, and destination categories cannot be verified from that file.
- An export is a snapshot. Re-export close to the time of the eventual import to reduce the risk of stale comparisons.

## Export and operational safety

The current export is intended for **new simple products**. It does not implement a general-purpose WooCommerce update workflow.

Before importing:

1. Keep the original supplier file unchanged.
2. Review all rows classified as ready, review, blocked, or existing.
3. Confirm every selected product and its destination category.
4. Inspect the generated CSV and verify its columns and values against the target store.
5. Back up the store and preferably test a small batch on a staging site.
6. In WooCommerce's native importer, verify the field mapping and ensure the option to update existing products is disabled for a new-products-only import.
7. Check the import results, SKUs, prices, stock, categories, images, and product publication status.

**The toolkit does not guarantee that an external WooCommerce import is risk-free.** The operator remains responsible for reviewing the file, importer settings, and results.

## Current scope and limitations

Included:

- Local supplier CSV inspection and column mapping.
- WooCommerce CSV inspection and SKU comparison.
- New-product technical classification.
- Manual, per-product selection.
- Category destination suggestions and explicit confirmation.
- Review summaries and CSV export for eligible selected products.
- Automated unit tests for core processing and selection logic.

Not currently included:

- Direct WooCommerce API access or database writes.
- Importing products into a store.
- Product update CSV workflow.
- Automatic category-wide selection, quotas, or price-based selection.
- Variations and a complete mapping of all WooCommerce product fields.
- Automatic creation of WooCommerce categories.
- Persistent sessions or selection state across application restarts.

## Core Python tools

The repository also contains standalone CSV utilities:

| Tool | Purpose |
|---|---|
| Image URL Auditor | Checks HTTP responses for image URLs listed in a CSV. It does not inspect image contents. |
| Catalog CSV Validator | Detects common supplier CSV data-quality issues. |
| New-product preflight | Screens supplier SKUs against a catalog export and reports candidate and review rows. |
| Catalog Update Planner | Produces a review report of supplier price/stock differences. It does not update products. |

These utilities are separate from the current four-stage NiceGUI new-product workflow.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

The core test suite should not require a live WooCommerce store.

## Dependencies

- Python 3.10+
- Core CSV utilities use the Python standard library.
- NiceGUI and pywebview are installed separately through `requirements-ui.txt`.

## Project status

The guided local workflow for **new product preparation** is implemented. The next development priorities are documentation and workflow verification, then a separately specified product-update workflow. Treat this project as an evolving preparation tool, not as a direct store-management or import automation system.

## License

No license has been selected yet. All rights reserved unless a license is added to this repository.
