import unittest

from src.application.woocommerce_categories import suggest_destination_categories


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

    def test_skips_blank_source_categories(self):
        self.assertEqual(suggest_destination_categories(["", "  "], ["Hardware > RAM"]), {})


if __name__ == "__main__":
    unittest.main()
