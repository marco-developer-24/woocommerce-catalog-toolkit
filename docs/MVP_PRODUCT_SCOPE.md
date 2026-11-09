# MVP Product Scope

## Product goal

WooCommerce Catalog Toolkit helps store operators and WordPress professionals inspect supplier and store-export CSV files, identify data-quality issues, and prepare controlled product selections or update plans for human review.

The toolkit is a local preparation and review tool. It does not connect to a WooCommerce store, execute imports, or modify products.

## Target users

### Primary: store owner or store operator

A person who manages product data but does not necessarily know Python, CSV internals, or WooCommerce's import schema.

The interface should explain what each step does, identify problems in plain language, and make the next action clear.

### Secondary: WordPress / WooCommerce agency

A technical operator who needs repeatable checks, reviewable outputs, and enough detail to investigate data-quality issues.

The same workflows should serve both audiences. The primary interface should not require users to understand internal script names or command-line arguments.

## Core user workflow

1. **Load source files.** Select a supplier CSV and, for comparison or catalog preparation, a recent WooCommerce product export.
2. **Inspect the structure.** Select delimiters, preview rows, and map the relevant columns.
3. **Validate.** Identify blocking errors and non-blocking warnings before comparison or preparation.
4. **Classify.** Compare supplier SKUs with the catalog snapshot. Existing and ambiguous products must not silently enter a new-product selection.
5. **Configure selection.** Enable relevant categories and set per-category product limits. Optional stock criteria may further restrict eligibility.
6. **Review.** Inspect selected products, excluded existing products, blocked rows, and eligible products outside the configured limits. Every classification should have a reason.
7. **Export.** Download outputs that preserve enough context for a human to continue the workflow safely.

The original input files must remain unchanged.

## MVP modules and implementation status

| Module | Inputs | Current responsibility | Current availability |
|---|---|---|---|
| Catalog CSV Validator | Supplier CSV and mapped columns | Check required fields, values, headers, duplicate SKUs, and row structure | Core logic and Streamlit validation interface |
| New-product preflight | Supplier CSV and WooCommerce catalog export | Compare SKUs and classify candidate, review, and existing rows | Python operation / CLI |
| Catalog Update Planner | Supplier CSV and WooCommerce catalog export | Compare configured price and stock fields for unambiguous SKU matches | Python operation / CLI |
| Image URL Auditor | CSV containing image URLs | Check URL response details and summarize outcomes | Python CLI |
| Catalog Preparation | Supplier rows, catalog rows, column mappings, category limits | Classify new products, apply category selection to eligible rows, and return review data | Python application layer and first Streamlit workflow |

The modules have different input requirements. The interface must explain those requirements before asking the user to upload files.

## Catalog Preparation: current behavior

Catalog Preparation orchestrates two existing operations in sequence:

1. **New-product classification.** Supplier SKUs are compared with the supplied catalog snapshot. Existing SKUs are excluded. Missing or ambiguous SKUs, missing product names, and invalid non-negative prices are blocked from selection.
2. **Category-based selection.** Only rows classified as ready to add are passed to the selection operation. Existing and blocked rows do not consume category limits.

### Selection rules currently implemented

- Categories are normalized by trimming surrounding whitespace and applying case-insensitive matching.
- Category matching is exact after that normalization. Accent normalization and fuzzy matching are not implemented.
- Each enabled category has an integer product limit, or `None` for no limit.
- Eligible products are ordered by ascending non-negative price within each category.
- Equal prices are resolved by original supplier row number.
- An optional stock column and minimum stock can exclude rows with invalid or insufficient stock.
- The result preserves original supplier order and provides source row numbers, statuses, reason codes, category positions, and per-category counts.

This is a deterministic lowest-price selection rule. It is not a recommendation engine and does not yet implement a balanced commercial ranking.

### Current preparation output

The current application workflow returns selected rows prepared with this limited field set:

- `SKU`
- `Name`
- `Regular price`
- `Published` set to `0`
- `Type` set to `simple`

It also returns per-row selection details, the underlying new-product classification, and aggregate counts for supplier rows, catalog rows, new ready rows, exported rows, existing products excluded, blocked rows, review rows, and ready rows not selected.

This output is not a complete WooCommerce import contract. It does not currently map images, categories, attributes, tax, shipping, variations, or arbitrary supplier fields. It does not connect to WooCommerce, import, update, delete, or publish products.

## Result and safety semantics

- **Error:** a condition that prevents the current operation from producing a trustworthy result.
- **Warning:** a condition that deserves human attention but does not necessarily prevent analysis.
- **Information:** a neutral result that helps explain what was checked.
- **Candidate / ready to add:** a unique new SKU with the required fields validated. This is not proof that no equivalent product exists.
- **Selected:** a ready-to-add product that meets the configured category selection limit and optional stock criteria.
- **Not selected:** a row not chosen for the current batch, for example because its category is not enabled or the category limit has been reached.
- **Ineligible / blocked:** a row that cannot safely enter selection due to missing or invalid required data.
- **Excluded existing:** a supplier row whose SKU already exists in the supplied catalog snapshot.
- **Review required:** an ambiguous or unsafe-to-classify row that must not be silently promoted to an approved result.
- **Update required:** a difference detected in configured fields, not permission to change the store.

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

### Catalog preparation

- Supplier rows are classified against a catalog snapshot before category selection.
- Existing SKUs and blocked rows never consume category limits.
- The user can enable categories and define a limit for each enabled category.
- The user can configure an optional stock column and minimum stock.
- The result shows selected, not-selected, ineligible, excluded-existing, and review outcomes with reasons.
- The user can trace each result back to its original supplier row.
- Selection is deterministic: the same inputs and configuration produce the same result.
- The UI does not describe lowest-price selection as a balanced or quality-based recommendation.
- No product is published or sent to WooCommerce by this workflow.
- The Streamlit workflow downloads a selected-products CSV and a row-level review CSV containing all classification outcomes and reasons.
- Preparation results are invalidated when either source file or any relevant mapping, delimiter, category limit, or stock setting changes.

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
- Users can distinguish functionality available in the interface from functionality currently available only through the Python layer or CLI.
- The preparation workflow requires a supplier CSV and a current WooCommerce catalog export, and clearly labels the limited fields included in its output.

## Explicitly out of scope for this MVP

- Direct WooCommerce REST API connection.
- Creating, updating, deleting, or publishing products.
- Automatic import-file generation that claims to be universally WooCommerce-ready.
- Automatic approval of new-product candidates or proposed updates.
- Fuzzy product matching across different SKUs.
- Automatic commercial ranking that claims to optimize margin, demand, quality, or product mix without explicit data and rules.
- Multi-user accounts, cloud storage, or hosted processing.

These capabilities can be reconsidered only after the local preparation and review workflows are reliable and tested with real users.

## Product and engineering constraints

- Keep domain logic independent from Streamlit.
- Keep existing command-line tools usable.
- Reuse existing tested engines instead of duplicating validation, classification, or selection rules in the UI.
- Put workflow orchestration and user-facing error translation outside the domain engines.
- Prefer small, testable changes over a broad rewrite.
- Treat user data as local input; do not transmit catalog files to external services.
- Keep preparation outputs explicit about their supported fields and WooCommerce limitations.

## MVP completion signal

A store operator unfamiliar with the repository can load a supplier file and a current catalog export in the Streamlit interface, understand validation findings, configure category limits, review selected and excluded rows with reasons, and download a traceable preparation report without developer assistance.

This should be verified through observed usability sessions using representative supplier data, not assumed from a successful automated test suite.
