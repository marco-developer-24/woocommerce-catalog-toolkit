import unittest

from src.application.woocommerce_categories import (
    discover_destination_categories,
    split_category_cell,
)


class WooCommerceCategoryParsingTests(unittest.TestCase):
    def test_splits_multiple_categories_and_preserves_hierarchy(self):
        self.assertEqual(
            split_category_cell("Computación > Procesadores, Componentes > RAM"),
            ["Computación > Procesadores", "Componentes > RAM"],
        )

    def test_preserves_escaped_commas_inside_category_names(self):
        self.assertEqual(
            split_category_cell(r"Audio\\, Video > Cables, Hogar"),
            ["Audio, Video > Cables", "Hogar"],
        )

    def test_ignores_blank_values(self):
        self.assertEqual(split_category_cell(" ,  , "), [])

    def test_discovers_distinct_paths_case_insensitively(self):
        rows = [
            {"Categories": "Hardware > RAM, Components > Storage"},
            {"Categories": "hardware > ram"},
            {"Categories": ""},
        ]
        self.assertEqual(
            discover_destination_categories(rows, "Categories"),
            ["Components > Storage", "Hardware > RAM"],
        )


if __name__ == "__main__":
    unittest.main()
