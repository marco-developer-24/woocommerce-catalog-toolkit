import unittest

from src.ui.selection_session import (
    clear_provider_selection_state,
    update_category_destination,
)


class TestSelectionSessionTransitions(unittest.TestCase):
    def setUp(self):
        self.state = {
            "selection_state": {12: "SELECTED", 18: "SELECTED"},
            "selection_category_mappings": {"ropa": "Ropa"},
            "selection_confirmations": {"ropa": "Ropa"},
        }

    def test_replacing_provider_clears_selection_destinations_and_confirmations(self):
        clear_provider_selection_state(self.state)

        self.assertEqual(self.state["selection_state"], {})
        self.assertEqual(self.state["selection_category_mappings"], {})
        self.assertEqual(self.state["selection_confirmations"], {})

    def test_changing_destination_invalidates_confirmation_but_preserves_products(self):
        update_category_destination(
            self.state,
            "ropa",
            "Indumentaria",
            suggestion_status="suggested",
            suggested_destination="Ropa",
        )

        self.assertEqual(self.state["selection_state"], {12: "SELECTED", 18: "SELECTED"})
        self.assertEqual(
            self.state["selection_category_mappings"],
            {"ropa": "Indumentaria"},
        )
        self.assertEqual(self.state["selection_confirmations"], {})

    def test_accepting_suggested_destination_does_not_create_confirmation(self):
        update_category_destination(
            self.state,
            "ropa",
            "Ropa",
            suggestion_status="suggested",
            suggested_destination="Ropa",
        )

        self.assertEqual(self.state["selection_state"], {12: "SELECTED", 18: "SELECTED"})
        self.assertEqual(self.state["selection_category_mappings"], {})
        self.assertEqual(self.state["selection_confirmations"], {})

    def test_clearing_destination_removes_mapping_and_confirmation(self):
        update_category_destination(
            self.state,
            "ropa",
            None,
            suggestion_status="manual",
            suggested_destination=None,
        )

        self.assertEqual(self.state["selection_state"], {12: "SELECTED", 18: "SELECTED"})
        self.assertEqual(self.state["selection_category_mappings"], {})
        self.assertEqual(self.state["selection_confirmations"], {})


if __name__ == "__main__":
    unittest.main()
