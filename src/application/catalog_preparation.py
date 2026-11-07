"""Application workflow for selecting and preparing new products.

New-product classification runs before commercial selection so that existing
products and duplicate SKUs do not consume category limits. Only selected,
ready-to-add products are exported; nothing is published or sent to WooCommerce.
"""

from src.operations.add_products import prepare_add_products
from src.operations.common import BLOCKED, EXCLUDED, READY, REVIEW
from src.operations.select_products import SELECTED, select_products


def _validate_mapping(mapping, label, required_keys):
    if not isinstance(mapping, dict):
        raise TypeError(f"{label} must be a dictionary.")

    missing = [key for key in required_keys if key not in mapping]
    if missing:
        raise ValueError(
            f"{label} is missing required keys: " + ", ".join(missing)
        )
    return mapping


def _validate_columns(mapping, label, keys):
    for key in keys:
        column = mapping[key]
        if not isinstance(column, str) or not column.strip():
            raise ValueError(
                f"{label} column {key!r} must be a non-empty string."
            )


def _validate_selection_options(selection_config):
    """Validate application-level option shapes; value rules stay in selection."""
    if not isinstance(selection_config["category_limits"], dict):
        raise ValueError(
            "selection_config 'category_limits' must be a dictionary."
        )

    if "stock_column" not in selection_config:
        return

    stock_column = selection_config["stock_column"]
    if stock_column is None:
        return
    if not isinstance(stock_column, str) or not stock_column.strip():
        raise ValueError(
            "selection_config column 'stock_column' must be a non-empty string "
            "or None."
        )


def prepare_catalog(
    supplier_rows,
    catalog_rows,
    *,
    selection_config,
    supplier_columns,
):
    """Select new products for a WooCommerce addition run.

    Products are first classified against the supplied catalog snapshot.
    Commercial selection is then applied only to rows that are READY for
    addition, so existing products and blocked duplicate SKUs never consume a
    category limit. Selected READY items keep their original supplier row
    numbers, and inputs are never mutated.

    ``selection_config`` requires ``category_column``, ``price_column``, and
    ``category_limits``. It may also define ``stock_column`` and
    ``minimum_stock``. ``supplier_columns`` requires ``sku``, ``name``, and
    ``price``; the optional ``catalog_sku`` key defaults to ``"SKU"``.
    """
    selection_config = _validate_mapping(
        selection_config,
        "selection_config",
        ("category_column", "price_column", "category_limits"),
    )
    supplier_columns = _validate_mapping(
        supplier_columns,
        "supplier_columns",
        ("sku", "name", "price"),
    )
    _validate_columns(
        selection_config,
        "selection_config",
        ("category_column", "price_column"),
    )
    _validate_columns(
        supplier_columns,
        "supplier_columns",
        ("sku", "name", "price"),
    )
    _validate_selection_options(selection_config)

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
    )
    ready_items = addition[READY]

    selection = select_products(
        [item["row"] for item in ready_items],
        category_column=selection_config["category_column"],
        price_column=selection_config["price_column"],
        category_limits=selection_config["category_limits"],
        stock_column=selection_config.get("stock_column"),
        minimum_stock=selection_config.get("minimum_stock"),
    )

    # select_products preserves input order, so each selection item maps back to
    # its original ready item and original supplier row number by position.
    export_items = [
        ready_item
        for selection_item, ready_item in zip(selection["items"], ready_items)
        if selection_item["status"] == SELECTED
    ]
    export_rows = [dict(item["changes"]) for item in export_items]

    summary = {
        "supplier_rows": len(supplier_rows),
        "catalog_rows": len(catalog_rows),
        "new_ready": len(ready_items),
        "exported": len(export_items),
        "excluded_existing": len(addition[EXCLUDED]),
        "blocked": len(addition[BLOCKED]),
        "review": len(addition[REVIEW]),
        "ready_not_selected": len(ready_items) - len(export_items),
    }

    return {
        "export_items": export_items,
        "export_rows": export_rows,
        "selection": selection,
        "add_products": addition,
        "summary": summary,
    }
