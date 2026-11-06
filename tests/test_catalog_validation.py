import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from src.application.catalog_validation import run_catalog_validation


class TestCatalogValidationWorkflow(unittest.TestCase):
    def setUp(self):
        self.file_bytes = (
            b"SKU;PRODUCT_NAME;PRICE;STOCK\n"
            b"A-1;Widget;19.99;4\n"
            b"A-1;Duplicate;12.50;many\n"
        )
        self.mapping = {
            "sku": "SKU",
            "name": "PRODUCT_NAME",
            "price": "PRICE",
            "stock": "STOCK",
        }

    def test_returns_validation_results_and_source_hash(self):
        result = run_catalog_validation(
            self.file_bytes,
            total_products=2,
            delimiter=";",
            mapping=self.mapping,
        )

        self.assertEqual(
            [issue["code"] for issue in result["issues"]],
            ["duplicate_sku", "invalid_stock"],
        )
        self.assertEqual(result["report"]["total_products"], 2)
        self.assertEqual(result["report"]["products_with_errors"], 1)
        self.assertEqual(result["report"]["products_with_warnings"], 1)
        self.assertEqual(
            result["file_hash"],
            hashlib.sha256(self.file_bytes).hexdigest(),
        )

    def test_rejects_missing_mapping_keys_before_validation(self):
        with self.assertRaisesRegex(ValueError, "stock"):
            run_catalog_validation(
                self.file_bytes,
                total_products=2,
                delimiter=";",
                mapping={"sku": "SKU", "name": "PRODUCT_NAME", "price": "PRICE"},
            )

    def test_rejects_non_bytes_input(self):
        with self.assertRaisesRegex(TypeError, "file_bytes"):
            run_catalog_validation(
                "not bytes",
                total_products=0,
                delimiter=";",
                mapping=self.mapping,
            )

    def test_temporary_file_is_removed_when_validation_fails(self):
        temporary_paths = []

        def fail_validation(path, **kwargs):
            temporary_path = Path(path)
            temporary_paths.append(temporary_path)
            self.assertTrue(temporary_path.exists())
            raise RuntimeError("validation failed")

        with patch(
            "src.application.catalog_validation.validate_catalog_csv",
            side_effect=fail_validation,
        ):
            with self.assertRaisesRegex(RuntimeError, "validation failed"):
                run_catalog_validation(
                    self.file_bytes,
                    total_products=2,
                    delimiter=";",
                    mapping=self.mapping,
                )

        self.assertEqual(len(temporary_paths), 1)
        self.assertFalse(temporary_paths[0].exists())


if __name__ == "__main__":
    unittest.main()
