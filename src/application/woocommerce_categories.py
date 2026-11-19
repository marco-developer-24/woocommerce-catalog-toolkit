"""Helpers for reading WooCommerce category values from product exports."""


def split_category_cell(value):
    """Split comma-separated WooCommerce categories, respecting escaped commas."""
    text = "" if value is None else str(value)
    parts = []
    current = []
    escaped = False

    for character in text:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\\\":
            escaped = True
        elif character == ",":
            item = "".join(current).strip()
            if item:
                parts.append(item)
            current = []
        else:
            current.append(character)

    if escaped:
        current.append("\\\\")

    item = "".join(current).strip()
    if item:
        parts.append(item)

    return parts


def discover_destination_categories(catalog_rows, category_column):
    """Return distinct observed category paths, preserving their hierarchy."""
    categories = {}
    for row in catalog_rows:
        for path in split_category_cell(row.get(category_column, "")):
            normalized = path.casefold()
            if normalized:
                categories.setdefault(normalized, path)
    return sorted(categories.values(), key=str.casefold)
