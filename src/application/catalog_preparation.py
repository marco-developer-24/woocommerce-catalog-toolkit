"""Prepare new catalog products using explicit, session-scoped selection."""

from src.application.product_selection import (
    SELECTED,
    NOT_SELECTED,
    get_exportable_row_numbers,
    initialize_selection_state,
)
from src.application.woocommerce_categories import escape_category_path
from src.operations.add_products import prepare_add_products
from src.operations.common import BLOCKED, EXCLUDED, READY, REVIEW
from src.operations.select_products import normalize_category


def _validate_mapping(mapping, label, required_keys):
    if not isinstance(mapping, dict):
        raise TypeError(f"{label} must be a dictionary.")
    missing = [key for key in required_keys if key not in mapping]
    if missing:
        raise ValueError(f"{label} is missing required keys: " + ", ".join(missing))
    return mapping


def _validate_columns(mapping, label, keys):
    for key in keys:
        column = mapping[key]
        if not isinstance(column, str) or not column.strip():
            raise ValueError(f"{label} column {key!r} must be a non-empty string.")


def _validate_stock_column(selection_config):
    stock_column = selection_config.get("stock_column")
    if stock_column is not None and (
        not isinstance(stock_column, str) or not stock_column.strip()
    ):
        raise ValueError(
            "selection_config column 'stock_column' must be a non-empty string or None."
        )


def prepare_catalog(
    supplier_rows,
    catalog_rows,
    *,
    selection_config,
    supplier_columns,
    selection_state=None,
):
    """Classify products, apply session selection, and build exportable rows.

    selection_config requires category_column and may contain stock_column and
    category_mappings. Mappings supplied here must already be confirmed by the
    operator. The optional selection_state is keyed by original CSV row_number.
    A missing state initializes all rows as NOT_SELECTED.
    """
    selection_config = _validate_mapping(
        selection_config, "selection_config", ("category_column",)
    )
    supplier_columns = _validate_mapping(
        supplier_columns, "supplier_columns", ("sku", "name", "price")
    )
    _validate_columns(selection_config, "selection_config", ("category_column",))
    _validate_columns(supplier_columns, "supplier_columns", ("sku", "name", "price"))
    _validate_stock_column(selection_config)

    catalog_sku_column = supplier_columns.get("catalog_sku", "SKU")
    if not isinstance(catalog_sku_column, str) or not catalog_sku_column.strip():
        raise ValueError(
            "supplier_columns column 'catalog_sku' must be a non-empty string."
        )

    addition = prepare_add_products(
        supplier_rows,
        catalog_rows,
        supplier_sku_column=supplier_columns["sku"],
        catalog_sku_column=catalog_sku_column,
        name_column=supplier_columns["name"],
        price_column=supplier_columns["price"],
        stock_column=selection_config.get("stock_column"),
        require_positive_stock=True,
    )

    all_row_numbers = list(range(2, len(supplier_rows) + 2))
    initialized_state = initialize_selection_state(all_row_numbers)
    eligible_items = addition[READY]
    eligible_row_numbers = {item["row_number"] for item in eligible_items}

    if selection_state is not None:
        if not isinstance(selection_state, dict):
            raise TypeError("selection_state must be a dictionary.")
        unknown_rows = set(selection_state) - set(initialized_state)
        if unknown_rows:
            raise ValueError("selection_state contains rows outside the current supplier session.")
        for row_number, status in selection_state.items():
            if status not in {SELECTED, NOT_SELECTED}:
                raise ValueError("selection_state contains an invalid selection value.")
            if status == SELECTED and row_number in eligible_row_numbers:
                initialized_state[row_number] = SELECTED
            # Rows no longer READY are deliberately reset to NOT_SELECTED.

    category_column = selection_config["category_column"]
    row_categories = {
        row_number: row.get(category_column, "")
        for row_number, row in enumerate(supplier_rows, start=2)
    }
    category_mappings = selection_config.get("category_mappings", {})
    if not isinstance(category_mappings, dict):
        raise ValueError("selection_config 'category_mappings' must be a dictionary.")

    normalized_destinations = {}
    for category, destination in category_mappings.items():
        key = normalize_category(category)
        if key and isinstance(destination, str) and destination.strip():
            normalized_destinations[key] = destination.strip()

    exportable_row_numbers = get_exportable_row_numbers(
        initialized_state,
        eligible_row_numbers=eligible_row_numbers,
        row_categories=row_categories,
        confirmed_destinations=normalized_destinations,
    )
    ready_by_row = {item["row_number"]: item for item in eligible_items}
    export_items = []
    export_rows = []
    for row_number in exportable_row_numbers:
        item = ready_by_row[row_number]
        row = dict(item["changes"])
        row["Categories"] = escape_category_path(
            normalized_destinations[normalize_category(row_categories[row_number])]
        )
        export_items.append(item)
        export_rows.append(row)

    operation_items_by_row = {
        item["row_number"]: item
        for status in (READY, REVIEW, BLOCKED, EXCLUDED)
        for item in addition[status]
    }
    selection_items = []
    for row_number, row in enumerate(supplier_rows, start=2):
        operation_item = operation_items_by_row.get(row_number)
        status = operation_item["status"] if operation_item else BLOCKED
        category = row.get(category_column, "")
        selection_items.append({
            "row_number": row_number,
            "row": dict(row),
            "category": category,
            "status": initialized_state[row_number],
            "technical_status": status,
            "reason_code": (
                "SELECTED" if initialized_state[row_number] == SELECTED
                else "NOT_SELECTED" if status == READY
                else status
            ),
            "reason": operation_item["reason"] if operation_item else "No technical classification available.",
        })

    selected_count = sum(
        1 for status in initialized_state.values() if status == SELECTED
    )
    summary = {
        "supplier_rows": len(supplier_rows),
        "catalog_rows": len(catalog_rows),
        "new_ready": len(eligible_items),
        "selected": selected_count,
        "exportable": len(export_items),
        "exported": len(export_items),
        "excluded_existing": len(addition[EXCLUDED]),
        "blocked": len(addition[BLOCKED]),
        "review": len(addition[REVIEW]),
        "ready_not_selected": len(eligible_items) - selected_count,
        "selected_without_destination": selected_count - len(export_items),
        "unmapped_category": selected_count - len(export_items),
    }

    return {
        "export_items": export_items,
        "export_rows": export_rows,
        "selection": {
            "items": selection_items,
            "state": dict(initialized_state),
            "summary": {
                "selected": selected_count,
                "not_selected": len(initialized_state) - selected_count,
                "exportable": len(export_items),
            },
        },
        "selection_state": dict(initialized_state),
        "add_products": addition,
        "summary": summary,
    }
