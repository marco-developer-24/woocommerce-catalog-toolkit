"""Review-report helpers for catalog preparation results."""


def build_preparation_review(result, category_column, price_column):
    """Return every supplier-row outcome in original CSV row order.

    Technical eligibility remains authoritative for REVIEW, BLOCKED, and
    EXCLUDED rows. Commercial selection only changes the presentation of READY
    rows; it never masks a technical status.
    """
    selected_by_row = {
        item["row_number"]: item
        for item in result["selection"]["items"]
    }
    rows = []
    for status in ("READY", "REVIEW", "BLOCKED", "EXCLUDED"):
        for operation_item in result["add_products"][status]:
            row_number = operation_item["row_number"]
            source_row = operation_item["row"]
            selection_item = selected_by_row.get(row_number)

            if status == "READY" and selection_item is not None:
                display_status = selection_item["status"]
                reason_code = selection_item["reason_code"]
                reason = selection_item["reason"]
            else:
                display_status = status
                reason_code = (
                    "STOCK_REVIEW"
                    if status == "REVIEW"
                    else operation_item.get("match_status", status)
                )
                reason = operation_item["reason"]

            rows.append({
                "CSV row": row_number,
                "SKU": operation_item["sku"],
                "Category": source_row.get(category_column, ""),
                "Price": source_row.get(price_column, ""),
                "Status": display_status,
                "Reason code": reason_code,
                "Reason": reason,
                "Category position": None,
            })
    return sorted(rows, key=lambda item: item["CSV row"])
