"""Apply explicit, safe manual decisions to category-based product selection."""

from copy import deepcopy

from src.application.woocommerce_categories import escape_category_path
from src.operations.common import READY
from src.operations.select_products import NOT_SELECTED, SELECTED, normalize_category


def set_manual_product_selection(
    result,
    row_number,
    *,
    include,
    category_mappings,
    category_limits,
):
    """Include or exclude one eligible product without bypassing selection rules.

    Inclusion is limited to products omitted only because their category quota
    was reached. It requires a confirmed destination and an available slot.
    Exclusion never causes another product to be selected automatically.
    The input result is not mutated.
    """
    if not isinstance(result, dict):
        raise TypeError("result must be a dictionary.")
    if not isinstance(row_number, int) or isinstance(row_number, bool) or row_number < 2:
        raise ValueError("row_number must be a valid CSV row number.")
    if not isinstance(include, bool):
        raise TypeError("include must be a boolean.")
    if not isinstance(category_mappings, dict):
        raise TypeError("category_mappings must be a dictionary.")
    if not isinstance(category_limits, dict):
        raise TypeError("category_limits must be a dictionary.")

    updated = deepcopy(result)
    selection = updated["selection"]
    items = selection["items"]
    matches = [item for item in items if item["row_number"] == row_number]
    if len(matches) != 1:
        raise ValueError("The selected source row does not identify one product.")

    item = matches[0]
    category_key = normalize_category(item["category"])
    category_summary = selection["summary"].get(category_key)
    if category_summary is None:
        raise ValueError("The product category is not part of this selection.")

    ready_items = updated["add_products"][READY]
    ready_matches = [
        ready_item for ready_item in ready_items
        if ready_item["row_number"] == row_number
    ]
    if len(ready_matches) != 1:
        raise ValueError("Only products classified as eligible can be changed manually.")
    ready_item = ready_matches[0]

    export_items = updated["export_items"]
    export_rows = updated["export_rows"]
    summary = updated["summary"]

    if include:
        if item["status"] == SELECTED:
            return updated
        if (
            item["status"] != NOT_SELECTED
            or item["reason_code"] != "CATEGORY_LIMIT_REACHED"
        ):
            raise ValueError(
                "Only eligible products omitted by the category limit can be included manually."
            )

        destination = category_mappings.get(category_key)
        if not isinstance(destination, str) or not destination.strip():
            raise ValueError("A confirmed WooCommerce destination is required.")
        limit = next(
            (
                value for category, value in category_limits.items()
                if normalize_category(category) == category_key
            ),
            None,
        )
        if not any(normalize_category(category) == category_key for category in category_limits):
            raise ValueError("The product category has no configured selection limit.")

        selected_count = sum(
            1 for candidate in items
            if normalize_category(candidate["category"]) == category_key
            and candidate["status"] == SELECTED
        )
        if limit is not None and selected_count >= limit:
            raise ValueError(
                "The category quota is full. Exclude another product or increase the quota first."
            )

        export_row = dict(ready_item["changes"])
        export_row["Categories"] = escape_category_path(destination)
        export_items.append(ready_item)
        export_rows.append(export_row)
        paired = sorted(zip(export_items, export_rows), key=lambda pair: pair[0]["row_number"])
        updated["export_items"] = [pair[0] for pair in paired]
        updated["export_rows"] = [pair[1] for pair in paired]

        item.update(
            status=SELECTED,
            reason_code="MANUALLY_SELECTED",
            reason="Included manually by the operator within the category quota.",
        )
        category_summary["selected"] += 1
        category_summary["not_selected"] -= 1
        summary["exported"] += 1
        summary["ready_not_selected"] -= 1
    else:
        if item["status"] == NOT_SELECTED:
            return updated
        if item["status"] != SELECTED:
            raise ValueError("Only currently selected products can be excluded manually.")

        positions = [
            index for index, export_item in enumerate(export_items)
            if export_item["row_number"] == row_number
        ]
        if len(positions) != 1 or len(export_rows) != len(export_items):
            raise ValueError("The export selection is inconsistent; no change was applied.")
        position = positions[0]
        del export_items[position]
        del export_rows[position]

        item.update(
            status=NOT_SELECTED,
            reason_code="MANUALLY_EXCLUDED",
            reason="Excluded manually by the operator; quota was not auto-filled.",
        )
        category_summary["selected"] -= 1
        category_summary["not_selected"] += 1
        summary["exported"] -= 1
        summary["ready_not_selected"] += 1

    return updated
