import unittest

from src.application.provider_profile import (
    detect_provider_profile,
    provider_mapping_fingerprint,
    stock_review_policy,
    suggest_provider_columns,
    validate_provider_mapping,
)


class ProviderWizardHelperTests(unittest.TestCase):
    def test_nb_filename_suggests_nb_profile(self):
        self.assertEqual(
            detect_provider_profile("NB-Lista-Precios-18_11.csv"),
            "NB",
        )

    def test_non_nb_filename_suggests_generic_profile(self):
        self.assertEqual(detect_provider_profile("catalog.csv"), "Genérico")

    def test_nb_profile_suggests_exact_price_with_tax(self):
        headers = ["CODIGO", "DETALLE", "CATEGORIA", "PRECIO PESOS CON IVA"]
        suggestions = suggest_provider_columns(headers, "NB")
        self.assertEqual(suggestions["sku"], "CODIGO")
        self.assertEqual(suggestions["name"], "DETALLE")
        self.assertEqual(suggestions["category"], "CATEGORIA")
        self.assertEqual(suggestions["price"], "PRECIO PESOS CON IVA")

    def test_missing_required_alias_remains_unassigned(self):
        suggestions = suggest_provider_columns(["DETALLE", "IMPORTE"], "NB")
        self.assertIsNone(suggestions["sku"])
        self.assertIsNone(suggestions["price"])

    def test_mapping_requires_all_required_fields(self):
        valid, message = validate_provider_mapping({
            "sku": "CODIGO",
            "name": "DETALLE",
            "category": None,
            "price": "PRECIO PESOS CON IVA",
            "stock": None,
        })
        self.assertFalse(valid)
        self.assertIn("category", message)

    def test_mapping_rejects_reused_columns(self):
        valid, _ = validate_provider_mapping({
            "sku": "CODIGO",
            "name": "CODIGO",
            "category": "CATEGORIA",
            "price": "PRECIO PESOS CON IVA",
            "stock": None,
        })
        self.assertFalse(valid)

    def test_stock_absence_requires_global_review(self):
        self.assertEqual(stock_review_policy({"stock": None}), "review_all")
        self.assertEqual(stock_review_policy({"stock": "STOCK"}), "validate_column")

    def test_fingerprint_changes_when_mapping_changes(self):
        original = provider_mapping_fingerprint(
            "hash", ";", "NB",
            {"sku": "CODIGO", "name": "DETALLE", "category": "CATEGORIA",
             "price": "PRECIO PESOS CON IVA", "stock": None},
        )
        changed = provider_mapping_fingerprint(
            "hash", ";", "NB",
            {"sku": "SKU", "name": "DETALLE", "category": "CATEGORIA",
             "price": "PRECIO PESOS CON IVA", "stock": None},
        )
        self.assertNotEqual(original, changed)


if __name__ == "__main__":
    unittest.main()
