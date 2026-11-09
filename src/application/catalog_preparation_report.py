"""Review-report helpers for catalog preparation results."""


def build_preparation_review(result, category_column, price_column):
    """Return every supplier-row outcome in original CSV row order."""
    selected_by_row = {
        item["row_number"]: item
        for item in result["selection"]["items"]
    }
    rows = []
    for status in ("READY", "REVIEW", "BLOCKED", "EXCLUDED"):
        for operation_item in result["add_products"][status]:
            source_row = operation_item["row"]
            selection_item = selected_by_row.get(operation_item["row_number"])
            rows.append({
                "CSV row": operation_item["row_number"],
                "SKU": operation_item["sku"],
                "Category": source_row.get(category_column, ""),
                "Price": source_row.get(price_column, ""),
                "Status": (
                    selection_item["status"]
                    if selection_item is not None
                    else operation_item["status"]
                ),
                "Reason code": (
                    selection_item["reason_code"]
                    if selection_item is not None
                    else operation_item["match_status"]
                ),
                "Reason": (
                    selection_item["reason"]
                    if selection_item is not None
                    else operation_item["reason"]
                ),
                "Category position": (
                    selection_item["category_position"]
                    if selection_item is not None
                    else None
                ),
            })
    return sorted(rows, key=lambda item: item["CSV row"])
