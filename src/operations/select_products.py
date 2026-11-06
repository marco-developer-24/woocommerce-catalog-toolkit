
"""Select supplier products by category, price, and optional stock criteria."""

from .common import parse_non_negative_decimal


SELECTED = "SELECTED"
NOT_SELECTED = "NOT_SELECTED"
INELIGIBLE = "INELIGIBLE"


def normalize_category(value):
    """Normalize category labels without fuzzy matching."""
    return "" if value is None else str(value).strip().casefold()


def select_products(
    supplier_rows,
    *,
    category_column,
    price_column,
    category_limits,
    stock_column=None,
    minimum_stock=None,
):
    """Select the lowest-priced eligible products within each category limit.

    Original input rows are preserved and never mutated.
    Results remain in their original source order.
    """
    if not category_column or not price_column:
        raise ValueError("Category and price columns are required.")

    if not isinstance(category_limits, dict):
        raise ValueError("category_limits must be a dictionary.")

    if stock_column is None and minimum_stock is not None:
        raise ValueError("minimum_stock requires a stock_column.")

    normalized_limits = {}
    for category, limit in category_limits.items():
        normalized = normalize_category(category)
        if not normalized:
            raise ValueError("Category names cannot be blank.")
        if normalized in normalized_limits:
            raise ValueError(f"Duplicate normalized category: {category!r}.")
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 0
        ):
            raise ValueError(f"Invalid limit for category {category!r}.")
        normalized_limits[normalized] = {
            "name": str(category).strip(),
            "limit": limit,
        }

    minimum = None
    if minimum_stock is not None:
        minimum = parse_non_negative_decimal(minimum_stock)
        if minimum is None:
            raise ValueError("minimum_stock must be a non-negative number.")

    items = []
    candidates = {category: [] for category in normalized_limits}
    summary = {
        category: {
            "limit": config["limit"],
            "eligible": 0,
            "selected": 0,
            "not_selected": 0,
            "ineligible": 0,
        }
        for category, config in normalized_limits.items()
    }

    for index, row in enumerate(supplier_rows, start=2):
        category_value = row.get(category_column, "")
        normalized_category = normalize_category(category_value)
        price = parse_non_negative_decimal(row.get(price_column, ""))

        item = {
            "row_number": index,
            "row": dict(row),
            "category": category_value,
            "price": None if price is None else format(price, "f"),
            "status": None,
            "reason_code": None,
            "reason": None,
            "category_position": None,
        }

        if not normalized_category:
            item.update(
                status=INELIGIBLE,
                reason_code="MISSING_CATEGORY",
                reason="Missing category.",
            )
        elif normalized_category not in normalized_limits:
            item.update(
                status=NOT_SELECTED,
                reason_code="CATEGORY_NOT_ENABLED",
                reason="Category is not enabled for selection.",
            )
        elif price is None:
            item.update(
                status=INELIGIBLE,
                reason_code="INVALID_PRICE",
                reason="Missing or invalid non-negative price.",
            )
        else:
            stock = None
            if stock_column is not None and minimum is not None:
                stock = parse_non_negative_decimal(row.get(stock_column, ""))
                if stock is None:
                    item.update(
                        status=INELIGIBLE,
                        reason_code="INVALID_STOCK",
                        reason="Missing or invalid stock value.",
                    )
                elif stock < minimum:
                    item.update(
                        status=INELIGIBLE,
                        reason_code="STOCK_BELOW_MINIMUM",
                        reason="Stock is below the configured minimum.",
                    )

            if item["status"] is None:
                candidates[normalized_category].append((price, index - 1, item))

        items.append(item)

    for category, category_candidates in candidates.items():
        config = normalized_limits[category]
        limit = config["limit"]
        ordered = sorted(category_candidates, key=lambda entry: (entry[0], entry[1]))
        summary[category]["eligible"] = len(ordered)

        for position, (_, _, item) in enumerate(ordered, start=1):
            if limit is None or position <= limit:
                item.update(
                    status=SELECTED,
                    reason_code="SELECTED_BY_PRICE",
                    reason="Selected by ascending price within category limit.",
                    category_position=position,
                )
                summary[category]["selected"] += 1
            else:
                item.update(
                    status=NOT_SELECTED,
                    reason_code="CATEGORY_LIMIT_REACHED",
                    reason="Eligible product is outside the category limit.",
                    category_position=position,
                )
                summary[category]["not_selected"] += 1

    for item in items:
        category = normalize_category(item["category"])
        if category in summary and item["status"] == INELIGIBLE:
            summary[category]["ineligible"] += 1

    return {
        "items": items,
        "summary": summary,
        "total": len(items),
    }
