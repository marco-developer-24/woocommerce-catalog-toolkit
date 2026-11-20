import unittest

from src.ui_helpers import (
    build_preparation_signature,
    category_widget_key,
    normalize_header,
    suggest_column,
)


class UiHelperTests(unittest.TestCase):
    def test_normalize_header_ignores_accents_and_case(self):
        self.assertEqual(normalize_header("CATEGORÍA"), "categoria")

    def test_suggest_column_returns_exact_normalized_match(self):
        headers = ["CODIGO", "DETALLE", "PRECIO PESOS CON IVA"]
        self.assertEqual(suggest_column(headers, ("Código", "SKU")), 0)
        self.assertEqual(suggest_column(headers, ("PRECIO PESOS CON IVA",)), 2)

    def test_suggest_column_does_not_fall_back_to_first_column(self):
        self.assertIsNone(suggest_column(["DETALLE", "IMPORTE"], ("SKU", "CODIGO")))

    def test_category_widget_keys_do_not_collide_after_normalization(self):
        self.assertNotEqual(
            category_widget_key("Categoria"),
            category_widget_key("Categoría"),
        )
        self.assertEqual(
            category_widget_key("Categoria"),
            category_widget_key("Categoria"),
        )

    def _signature(self, **overrides):
        values = {
            "file_hash": "supplier",
            "catalog_hash": "store",
            "delimiter": ";",
            "catalog_delimiter": ",",
            "columns": ("SKU", "DETALLE", "PRECIO PESOS CON IVA", "CATEGORIA"),
            "selected_categories": ("Hardware",),
            "category_mappings": {"hardware": "Computación > Hardware"},
            "category_limits": {"Hardware": 5},
            "minimum_stock": None,
        }
        values.update(overrides)
        return build_preparation_signature(**values)

    def test_signature_changes_when_category_destination_changes(self):
        original = self._signature()
        changed = self._signature(
            category_mappings={"hardware": "Componentes > Hardware"}
        )
        self.assertNotEqual(original, changed)

    def test_signature_changes_when_enabled_categories_change(self):
        original = self._signature()
        changed = self._signature(selected_categories=("Hardware", "Periféricos"))
        self.assertNotEqual(original, changed)

    def test_signature_is_stable_when_mapping_insertion_order_changes(self):
        first = self._signature(
            category_mappings={"hardware": "Hardware", "audio": "Audio"}
        )
        second = self._signature(
            category_mappings={"audio": "Audio", "hardware": "Hardware"}
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
