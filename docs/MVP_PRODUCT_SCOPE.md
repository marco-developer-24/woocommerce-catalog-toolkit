# MVP Product Scope

## Product goal

WooCommerce Catalog Toolkit helps store owners and WordPress professionals inspect supplier and store-export CSV files before preparing a WooCommerce import or update.

The toolkit is a local preparation and review tool. It does not connect to a WooCommerce store, execute imports, or modify products.

## Target users

### Primary: store owner or store operator

A person who manages product data but does not necessarily know Python, CSV internals, or WooCommerce's import schema.

The interface should explain what each step does, identify problems in plain language, and make the next action clear.

### Secondary: WordPress / WooCommerce agency

A technical operator who needs repeatable checks, reviewable outputs, and enough detail to investigate data-quality issues.

The same workflows should serve both audiences. The primary interface should not require users to understand internal script names or command-line arguments.

## Core user workflow

1. **Load source files.** Select a supplier CSV and, for comparison workflows, a recent WooCommerce product export.
2. **Inspect the structure.** Detect or select delimiters, preview rows, and map the relevant columns.
3. **Validate.** Identify blocking errors and non-blocking warnings before comparison or import preparation.
4. **Compare.** Identify possible new products or differences in configured fields.
5. **Review.** Inspect classifications, reasons, and source values. Ambiguous cases must remain review items rather than being silently approved.
6. **Export.** Download reports that preserve enough context for a human to continue the workflow safely.

The original input files must remain unchanged.

## MVP modules

| Module | Inputs | Current responsibility | Expected user outcome |
|---|---|---|---|
| Catalog CSV Validator | Supplier CSV and mapped columns | Check required fields, values, headers, duplicate SKUs, and row structure | Understand which data issues must be fixed |
| New-product preflight | Supplier CSV and WooCommerce catalog export | Compare SKUs and classify candidate, review, and existing rows | Identify possible new products without treating candidates as guaranteed new |
| Catalog Update Planner | Supplier CSV and WooCommerce catalog export | Compare configured price and stock fields for unambiguous SKU matches | Review proposed changes before preparing an import |
| Image URL Auditor | CSV containing image URLs | Check URL response details and summarize outcomes | Find inaccessible or suspicious image URLs |

These modules have different input requirements. The interface must explain those requirements before asking the user to upload files.

## Result and safety semantics

- **Error:** a condition that prevents the current operation from producing a trustworthy result.
- **Warning:** a condition that deserves human attention but does not necessarily prevent analysis.
- **Information:** a neutral result that helps explain what was checked.
- **Candidate:** a possible new product, not proof that no equivalent product exists.
- **Update required:** a difference detected in configured fields, not permission to change the store.
- **Review required:** an ambiguous or unsafe-to-classify row that must not be silently promoted to an approved result.

Every report should explain the classification and, where possible, identify the affected row and field.

## Functional acceptance criteria

### Shared file handling

- The user can identify which file each workflow requires before running it.
- The user can inspect a preview and confirm delimiter and column mapping.
- Unsupported or malformed input produces an actionable error.
- The source file is never overwritten.
- Existing report files are not silently overwritten.
- The user can tell which input files and settings produced a report.

### Validation

- Required-column and row-level failures are distinguishable.
- Errors and warnings are presented separately.
- Each issue includes enough context to locate the affected row and field.
- A validation report can be downloaded without requiring command-line use.

### Comparison

- Supplier and catalog exports can use different delimiters and column names.
- Blank or duplicate SKUs are routed to review.
- A stale or incomplete catalog export is identified as a limitation, not hidden.
- Proposed changes are presented as a review plan, never as executed changes.

### Usability

- Users can complete the primary workflow without knowing Python or terminal commands.
- Internal script names and raw exception messages are not the primary interface language.
- Each workflow explains its purpose, required files, and next step.
- Narrow viewports remain usable; tables must not be the only way to understand important findings.

## Explicitly out of scope for this MVP

- Direct WooCommerce REST API connection.
- Creating, updating, deleting, or publishing products.
- Automatic import-file generation that claims to be universally WooCommerce-ready.
- Automatic approval of new-product candidates or proposed updates.
- Fuzzy product matching across different SKUs.
- Multi-user accounts, cloud storage, or hosted processing.

These capabilities can be reconsidered only after the local preparation and review workflows are reliable and tested with real users.

## Product and engineering constraints

- Keep domain logic independent from Streamlit.
- Keep the existing command-line tools usable.
- Reuse existing tested engines instead of duplicating validation or comparison rules in the UI.
- Put workflow orchestration and user-facing error translation outside the domain engines.
- Prefer small, testable changes over a broad rewrite.
- Treat user data as local input; do not transmit catalog files to external services.

## MVP completion signal

A store operator unfamiliar with the repository can load a supplier file, understand validation findings, complete at least one comparison workflow with a WooCommerce export, review the results, and download a report without developer assistance.

This should be verified through observed usability sessions, not assumed from a successful automated test suite.
