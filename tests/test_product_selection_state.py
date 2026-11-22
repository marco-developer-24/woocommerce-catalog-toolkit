import unittest

from src.application.product_selection import (
    get_exportable_row_numbers,
    initialize_selection_state,
    set_product_selection,
)


class ProductSelectionStateTests(unittest.TestCase):
    def test_initializes_every_product_as_not_selected(self):
        self.assertEqual(
            initialize_selection_state([2, 3, 8]),
            {2: "NOT_SELECTED", 3: "NOT_SELECTED", 8: "NOT_SELECTED"},
        )

    def test_rejects_duplicate_or_invalid_row_numbers(self):
        for row_numbers in ([2, 2], [1], [2, True], ["2"]):
            with self.subTest(row_numbers=row_numbers):
                with self.assertRaises(ValueError):
                    initialize_selection_state(row_numbers)

    def test_selects_only_a_technically_ready_product(self):
        state = initialize_selection_state([2, 3, 4])
        updated = set_product_selection(
            state, 2, selected=True, eligible_row_numbers={2, 4}
        )
        self.assertEqual(updated[2], "SELECTED")
        self.assertEqual(updated[3], "NOT_SELECTED")
        self.assertEqual(state[2], "NOT_SELECTED")

    def test_rejects_selection_of_non_ready_product(self):
        state = initialize_selection_state([2, 3])
        with self.assertRaisesRegex(ValueError, "READY"):
            set_product_selection(
                state, 3, selected=True, eligible_row_numbers={2}
            )

    def test_deselects_a_product_without_changing_other_decisions(self):
        state = initialize_selection_state([2, 3, 4])
        selected = set_product_selection(
            state, 2, selected=True, eligible_row_numbers={2, 3, 4}
        )
        selected = set_product_selection(
            selected, 3, selected=True, eligible_row_numbers={2, 3, 4}
        )
        updated = set_product_selection(
            selected, 2, selected=False, eligible_row_numbers={2, 3, 4}
        )
        self.assertEqual(updated, {
            2: "NOT_SELECTED",
            3: "SELECTED",
            4: "NOT_SELECTED",
        })

    def test_export_requires_selection_readiness_and_confirmed_destination(self):
        state = {2: "SELECTED", 3: "SELECTED", 4: "NOT_SELECTED", 5: "SELECTED"}
        eligible = {2, 3, 4}
        categories = {
            2: "RAM",
            3: "SSD",
            4: "RAM",
            5: "RAM",
        }
        destinations = {"ram": "Hardware > RAM"}
        self.assertEqual(
            get_exportable_row_numbers(
                state,
                eligible_row_numbers=eligible,
                row_categories=categories,
                confirmed_destinations=destinations,
            ),
            [2],
        )

    def test_export_does_not_mutate_selection_state(self):
        state = {2: "SELECTED"}
        original = dict(state)
        get_exportable_row_numbers(
            state,
            eligible_row_numbers={2},
            row_categories={2: "RAM"},
            confirmed_destinations={"ram": "Hardware > RAM"},
        )
        self.assertEqual(state, original)

    def test_export_order_is_independent_of_visual_order(self):
        state = {8: "SELECTED", 2: "SELECTED", 5: "SELECTED"}
        self.assertEqual(
            get_exportable_row_numbers(
                state,
                eligible_row_numbers={2, 5, 8},
                row_categories={2: "RAM", 5: "RAM", 8: "RAM"},
                confirmed_destinations={"ram": "Hardware > RAM"},
            ),
            [2, 5, 8],
        )


if __name__ == "__main__":
    unittest.main()
