import unittest

from src.application.store_setup import (
    confirm_store_setup,
    inspect_store_file,
)


class StoreSetupServiceTests(unittest.TestCase):
    def setUp(self):
        self.provider = {
            "file_hash": "provider-hash",
            "rows": [
                {"CODIGO": "NEW-1"},
                {"CODIGO": "OLD-1"},
                {"CODIGO": "DUP-1"},
                {"CODIGO": "dup-1"},
                {"CODIGO": ""},
            ],
            "mapping": {"sku": "CODIGO"},
        }

    def test_inspection_detects_woocommerce_columns_and_categories(self):
        content = (
            "SKU,Name,Categories\n"
            "OLD-1,Existing,Hardware > RAM\n"
            "STORE-2,Other,Hardware > Disks\n"
        ).encode()
        result = inspect_store_file(content, "woocommerce-export.csv")
        self.assertEqual(result["suggestions"]["sku"], "SKU")
        self.assertEqual(result["suggestions"]["categories"], "Categories")
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["delimiter"], ",")

    def test_inspection_accepts_explicit_delimiter(self):
        content = "SKU;Name\nA-1;Product\n".encode()
        result = inspect_store_file(content, "store.csv", delimiter=";")
        self.assertEqual(result["delimiter"], ";")
        self.assertEqual(result["headers"], ["SKU", "Name"])

    def test_inspection_rejects_rows_with_inconsistent_column_counts(self):
        content = "SKU,Name\\nA-1,Product,Unexpected\\n".encode()
        with self.assertRaisesRegex(ValueError, "fila 2"):
            inspect_store_file(content, "store.csv")

    def test_inspection_rejects_non_bytes_input(self):
        with self.assertRaises(TypeError):
            inspect_store_file("SKU\nA-1", "store.csv")

    def test_inspection_rejects_file_over_size_limit(self):
        content = b"x" * (50 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(ValueError, "50 MB"):
            inspect_store_file(content, "store.csv")

    def test_inspection_rejects_unsupported_delimiter(self):
        with self.assertRaisesRegex(ValueError, "delimiter"):
            inspect_store_file(b"SKU|Name\nA-1|Product\n", "store.csv", delimiter=":")

    def test_confirmation_requires_store_sku_column(self):
        inspection = inspect_store_file(b"SKU,Name\nA-1,Product\n", "store.csv")
        with self.assertRaisesRegex(ValueError, "SKU"):
            confirm_store_setup(self.provider, inspection, {"sku": None})

    def test_confirmation_rejects_column_not_in_export(self):
        inspection = inspect_store_file(b"SKU,Name\nA-1,Product\n", "store.csv")
        with self.assertRaisesRegex(ValueError, "no existe"):
            confirm_store_setup(self.provider, inspection, {"sku": "Code"})

    def test_confirmation_rejects_same_sku_and_category_column(self):
        inspection = inspect_store_file(b"SKU,Name\nA-1,Product\n", "store.csv")
        with self.assertRaisesRegex(ValueError, "diferentes"):
            confirm_store_setup(
                self.provider, inspection, {"sku": "SKU", "categories": "SKU"}
            )

    def test_confirmation_classifies_supplier_skus_and_extracts_categories(self):
        content = (
            "SKU,Name,Categories\n"
            "OLD-1,Existing,Hardware > RAM\n"
            "STORE-2,Other,Hardware > Disks\n"
        ).encode()
        inspection = inspect_store_file(content, "store.csv")
        result = confirm_store_setup(
            self.provider,
            inspection,
            {"sku": "SKU", "categories": "Categories"},
        )
        self.assertEqual(
            [item["status"] for item in result["classified_supplier_rows"]],
            [
                "NEW_CANDIDATE",
                "SKU_ALREADY_EXISTS",
                "DUPLICATE_SKU_IN_SOURCE",
                "DUPLICATE_SKU_IN_SOURCE",
                "MISSING_SKU",
            ],
        )
        self.assertEqual(
            result["observed_categories"],
            ["Hardware > Disks", "Hardware > RAM"],
        )
        self.assertEqual(result["summary"]["duplicate_store_sku"], 0)
        self.assertEqual(result["summary"]["existing"], 1)
        self.assertEqual(result["summary"]["new_candidates"], 1)

    def test_confirmation_without_category_column_returns_no_categories(self):
        inspection = inspect_store_file(b"SKU,Name\nOLD-1,Existing\n", "store.csv")
        result = confirm_store_setup(self.provider, inspection, {"sku": "SKU"})
        self.assertEqual(result["observed_categories"], [])
        self.assertEqual(result["summary"]["observed_categories"], 0)


if __name__ == "__main__":
    unittest.main()
