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
        elif character == "\\":
            escaped = True
        elif character == ",":
            item = "".join(current).strip()
            if item:
                parts.append(item)
            current = []
        else:
            current.append(character)

    if escaped:
        current.append("\\")

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


def escape_category_path(value):
    """Escape literal commas for WooCommerce's comma-separated Categories field."""
    text = "" if value is None else str(value).strip()
    return text.replace("\\", "\\\\").replace(",", "\\,")

 
def suggest_destination_categories(source_categories, destination_categories):
    """Suggest only unambiguous exact category-name matches.

    Full paths are preferred. A source category may also match a destination
    leaf name when that leaf occurs exactly once. No fuzzy matching is used.
    """
    def normalize(value):
        return " ".join(str(value or "").strip().casefold().split())

    destinations = list(destination_categories or [])
    by_full_path = {}
    by_leaf = {}
    for destination in destinations:
        path = str(destination or "").strip()
        if not path:
            continue
        full_key = normalize(path)
        by_full_path.setdefault(full_key, []).append(path)
        leaf = path.split(">")[-1].strip()
        by_leaf.setdefault(normalize(leaf), []).append(path)

    suggestions = {}
    for source in source_categories:
        source_name = str(source or "").strip()
        source_key = normalize(source_name)
        if not source_key:
            continue

        exact = by_full_path.get(source_key, [])
        if len(exact) == 1:
            suggestions[source_key] = {
                "status": "suggested",
                "destination": exact[0],
                "match_type": "exact_path",
            }
            continue
        if len(exact) > 1:
            suggestions[source_key] = {
                "status": "ambiguous",
                "destination": None,
                "match_type": None,
            }
            continue

        leaf_matches = by_leaf.get(source_key, [])
        if len(leaf_matches) == 1:
            suggestions[source_key] = {
                "status": "suggested",
                "destination": leaf_matches[0],
                "match_type": "unique_name",
            }
        elif len(leaf_matches) > 1:
            suggestions[source_key] = {
                "status": "ambiguous",
                "destination": None,
                "match_type": None,
            }
        else:
            suggestions[source_key] = {
                "status": "unmatched",
                "destination": None,
                "match_type": None,
            }

    return suggestions


def is_destination_selection_confirmed(
    suggestion, selected_destination, confirmed_destination
):
    """Validate a selected destination against its suggestion confirmation.

    A suggested destination requires explicit confirmation only while it remains
    selected. Choosing a different destination is an explicit manual decision.
    """
    if suggestion.get("status") != "suggested":
        return True
    suggested_destination = suggestion.get("destination")
    if not selected_destination:
        return False
    if selected_destination != suggested_destination:
        return True
    return confirmed_destination == selected_destination
