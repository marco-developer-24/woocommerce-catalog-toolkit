"""Session-scoped commercial selection, independent of technical eligibility."""

from src.operations.select_products import normalize_category


SELECTED = "SELECTED"
NOT_SELECTED = "NOT_SELECTED"


def _validate_row_number(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 2:
        raise ValueError("row_number must be an original CSV row number (>= 2).")


def initialize_selection_state(row_numbers):
    """Initialize every source row as NOT_SELECTED for a new supplier session."""
    state = {}
    for row_number in row_numbers:
        _validate_row_number(row_number)
        if row_number in state:
            raise ValueError(f"Duplicate row_number: {row_number}.")
        state[row_number] = NOT_SELECTED
    return state


def set_product_selection(
    selection_state,
    row_number,
    *,
    selected,
    eligible_row_numbers,
):
    """Return an updated selection mapping without mutating the input mapping.

    Eligibility is supplied by the technical classification layer. A product
    can be selected only while its original row is classified READY. A product
    can always be deselected, including after it ceases to be READY.
    """
    if not isinstance(selection_state, dict):
        raise TypeError("selection_state must be a dictionary.")
    _validate_row_number(row_number)
    if row_number not in selection_state:
        raise ValueError("row_number does not belong to the current supplier session.")
    if not isinstance(selected, bool):
        raise TypeError("selected must be a boolean.")
    if selection_state[row_number] not in {SELECTED, NOT_SELECTED}:
        raise ValueError("selection_state contains an invalid selection value.")

    eligible = set(eligible_row_numbers)
    if selected and row_number not in eligible:
        raise ValueError("Only products classified as READY can be selected.")

    updated = dict(selection_state)
    updated[row_number] = SELECTED if selected else NOT_SELECTED
    return updated


def get_exportable_row_numbers(
    selection_state,
    *,
    eligible_row_numbers,
    row_categories,
    confirmed_destinations,
):
    """Return source row numbers meeting all three export prerequisites."""
    if not isinstance(selection_state, dict):
        raise TypeError("selection_state must be a dictionary.")
    if not isinstance(row_categories, dict):
        raise TypeError("row_categories must be a dictionary.")
    if not isinstance(confirmed_destinations, dict):
        raise TypeError("confirmed_destinations must be a dictionary.")

    eligible = set(eligible_row_numbers)
    exportable = []
    for row_number, status in selection_state.items():
        _validate_row_number(row_number)
        if status not in {SELECTED, NOT_SELECTED}:
            raise ValueError("selection_state contains an invalid selection value.")
        if status != SELECTED or row_number not in eligible:
            continue

        category = normalize_category(row_categories.get(row_number))
        destination = confirmed_destinations.get(category)
        if isinstance(destination, str) and destination.strip():
            exportable.append(row_number)

    return sorted(exportable)
