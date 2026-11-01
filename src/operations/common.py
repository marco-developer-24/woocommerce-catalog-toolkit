"""Shared statuses and parsing helpers for catalog operations."""

from decimal import Decimal, InvalidOperation

READY = "READY"
REVIEW = "REVIEW"
BLOCKED = "BLOCKED"
EXCLUDED = "EXCLUDED"


def parse_non_negative_decimal(value):
    """Parse a non-negative finite decimal; return None for blank or invalid."""
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or number < 0:
        return None
    return number


def decimal_to_text(value):
    """Render Decimal without scientific notation or insignificant zeroes."""
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def operation_item(classification, status, reason, changes=None):
    return {
        "row_number": classification["row_number"],
        "row": dict(classification["row"]),
        "sku": classification["row"].get("SKU", ""),
        "normalized_sku": classification["normalized_sku"],
        "match_status": classification["status"],
        "status": status,
        "reason": reason,
        "catalog_row_numbers": list(classification["catalog_row_numbers"]),
        "changes": dict(changes or {}),
    }


def build_result(items):
    """Group operation rows without losing their original order."""
    result = {READY: [], REVIEW: [], BLOCKED: [], EXCLUDED: []}
    for item in items:
        result[item["status"]].append(item)
    result["total"] = len(items)
    return result


def is_truthy_export_value(value):
    text = "" if value is None else str(value).strip().casefold()
    if text in {"1", "yes", "true"}:
        return True
    if text in {"0", "no", "false"}:
        return False
    return None
