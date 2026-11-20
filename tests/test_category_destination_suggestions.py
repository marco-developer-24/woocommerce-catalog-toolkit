import unittest

from src.application.woocommerce_categories import (
    is_destination_selection_confirmed,
    suggest_destination_categories,
)


class CategoryDestinationSuggestionTests(unittest.TestCase):
    def test_prefers_exact_full_path_match(self):
        result = suggest_destination_categories(
            ["Hardware > RAM"],
            ["Hardware > RAM", "Other > RAM"],
        )
        self.assertEqual(result["hardware > ram"]["status"], "suggested")
        self.assertEqual(result["hardware > ram"]["destination"], "Hardware > RAM")
        self.assertEqual(result["hardware > ram"]["match_type"], "exact_path")

    def test_suggests_unique_destination_leaf_name(self):
        result = suggest_destination_categories(["RAM"], ["Components > RAM", "Storage > SSD"])
        self.assertEqual(result["ram"]["status"], "suggested")
        self.assertEqual(result["ram"]["destination"], "Components > RAM")
        self.assertEqual(result["ram"]["match_type"], "unique_name")

    def test_does_not_guess_when_leaf_name_is_ambiguous(self):
        result = suggest_destination_categories(["RAM"], ["Components > RAM", "Notebooks > RAM"])
        self.assertEqual(result["ram"]["status"], "ambiguous")
        self.assertIsNone(result["ram"]["destination"])

    def test_leaves_unmatched_category_without_destination(self):
        result = suggest_destination_categories(["ACCESORIOS"], ["PERIFERICOS > MOUSES", "Computadoras"])
        self.assertEqual(result["accesorios"]["status"], "unmatched")
        self.assertIsNone(result["accesorios"]["destination"])

    def test_normalizes_case_and_repeated_whitespace(self):
        result = suggest_destination_categories(["  memorias   ram "], ["Componentes > MEMORIAS RAM"])
        self.assertEqual(result["memorias ram"]["destination"], "Componentes > MEMORIAS RAM")

    def test_suggested_destination_requires_confirmation_when_kept(self):
        suggestion = {"status": "suggested", "destination": "Components > RAM"}
        self.assertFalse(
            is_destination_selection_confirmed(
                suggestion, "Components > RAM", None
            )
        )

    def test_confirmed_suggested_destination_is_valid(self):
        suggestion = {"status": "suggested", "destination": "Components > RAM"}
        self.assertTrue(
            is_destination_selection_confirmed(
                suggestion, "Components > RAM", "Components > RAM"
            )
        )

    def test_cleared_suggested_destination_is_not_valid(self):
        suggestion = {"status": "suggested", "destination": "Components > RAM"}
        self.assertFalse(
            is_destination_selection_confirmed(suggestion, None, None)
        )

    def test_manual_destination_does_not_require_suggestion_confirmation(self):
        suggestion = {"status": "suggested", "destination": "Components > RAM"}
        self.assertTrue(
            is_destination_selection_confirmed(
                suggestion, "Hardware > Memory", None
            )
        )

    def test_unmatched_or_ambiguous_manual_destination_is_valid(self):
        for status in ("unmatched", "ambiguous"):
            with self.subTest(status=status):
                suggestion = {"status": status, "destination": None}
                self.assertTrue(
                    is_destination_selection_confirmed(
                        suggestion, "Hardware > Memory", None
                    )
                )

    def test_skips_blank_source_categories(self):
        self.assertEqual(suggest_destination_categories(["", "  "], ["Hardware > RAM"]), {})


if __name__ == "__main__":
    unittest.main()
