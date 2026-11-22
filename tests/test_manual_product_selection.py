import unittest

from src.application.product_selection import (
    initialize_selection_state,
    set_product_selection,
)


class ManualProductSelectionTests(unittest.TestCase):
    def setUp(self):
        self.state = initialize_selection_state([2, 3, 4])
        self.eligible = {2, 3, 4}

    def test_manual_selection_does_not_auto_select_other_products(self):
        updated = set_product_selection(
            self.state, 3, selected=True, eligible_row_numbers=self.eligible
        )
        self.assertEqual(updated, {
            2: "NOT_SELECTED",
            3: "SELECTED",
            4: "NOT_SELECTED",
        })

    def test_manual_exclusion_does_not_auto_fill_any_slot(self):
        selected = set_product_selection(
            self.state, 2, selected=True, eligible_row_numbers=self.eligible
        )
        updated = set_product_selection(
            selected, 2, selected=False, eligible_row_numbers=self.eligible
        )
        self.assertEqual(updated, self.state)

    def test_selection_is_independent_of_destination(self):
        updated = set_product_selection(
            self.state, 2, selected=True, eligible_row_numbers=self.eligible
        )
        self.assertEqual(updated[2], "SELECTED")

    def test_decision_does_not_mutate_original_state(self):
        original = dict(self.state)
        set_product_selection(
            self.state, 2, selected=True, eligible_row_numbers=self.eligible
        )
        self.assertEqual(self.state, original)

    def test_cannot_select_a_non_ready_product(self):
        with self.assertRaisesRegex(ValueError, "READY"):
            set_product_selection(
                self.state, 4, selected=True, eligible_row_numbers={2, 3}
            )


if __name__ == "__main__":
    unittest.main()
