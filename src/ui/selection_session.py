"""State transitions for manual product-selection sessions."""


def clear_provider_selection_state(state):
    """Clear all selection data when the provider source is replaced or removed."""
    state["selection_state"] = {}
    state["selection_category_mappings"] = {}
    state["selection_confirmations"] = {}


def update_category_destination(
    state,
    category_key,
    destination,
    *,
    suggestion_status,
    suggested_destination,
):
    """Update a category mapping and invalidate any prior explicit confirmation."""
    state["selection_confirmations"].pop(category_key, None)

    if destination and (
        suggestion_status != "suggested"
        or destination != suggested_destination
    ):
        state["selection_category_mappings"][category_key] = destination
    else:
        state["selection_category_mappings"].pop(category_key, None)
