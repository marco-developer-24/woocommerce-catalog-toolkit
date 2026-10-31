import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalog_csv_validator import validate_catalog_csv


class TestCatalogCsvValidator(unittest.TestCase):
    def write_csv(self, content):
        temp = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", suffix=".csv", delete=False
        )
        self.addCleanup(Path(temp.name).unlink, missing_ok=True)
        with temp:
            temp.write(content)
        return Path(temp.name)

    def test_valid_catalog_returns_no_issues(self):
        path = self.write_csv(
            "SKU;PRODUCT_NAME;PRICE;STOCK\nA-1;Widget;19.99;4\n"
        )
        self.assertEqual(validate_catalog_csv(path), [])

    def test_reports_empty_sku_and_product_name(self):
        path = self.write_csv(
            "SKU;PRODUCT_NAME;PRICE\n ; ;12.50\n"
        )
        issues = validate_catalog_csv(path)
        self.assertEqual(
            {issue["code"] for issue in issues},
            {"empty_sku", "empty_product_name"},
        )
        self.assertTrue(all(issue["row_number"] == 2 for issue in issues))

    def test_duplicate_sku_is_case_insensitive_and_ignores_outer_spaces(self):
        path = self.write_csv(
            "SKU;PRODUCT_NAME;PRICE\nABC;First;10\n abc ;Second;12\n"
        )
        issues = validate_catalog_csv(path)
        self.assertEqual([issue["code"] for issue in issues], ["duplicate_sku"])
        self.assertEqual(issues[0]["row_number"], 3)
        self.assertIn("row 2", issues[0]["message"])

    def test_rejects_invalid_and_negative_prices(self):
        path = self.write_csv(
            "SKU;PRODUCT_NAME;PRICE\nA;Text;abc\nB;Negative;-1\n"
        )
        issues = validate_catalog_csv(path)
        self.assertEqual(
            [issue["code"] for issue in issues],
            ["invalid_price", "negative_price"],
        )

    def test_rejects_invalid_negative_and_fractional_stock(self):
        path = self.write_csv(
            "SKU;PRODUCT_NAME;PRICE;STOCK\n"
            "A;Invalid;10;many\nB;Negative;10;-2\nC;Fraction;10;1.5\n"
        )
        issues = validate_catalog_csv(path)
        self.assertEqual(
            [issue["code"] for issue in issues],
            ["invalid_stock", "negative_stock", "invalid_stock"],
        )

    def test_stock_column_is_optional(self):
        path = self.write_csv("SKU;PRODUCT_NAME;PRICE\nA;Widget;10\n")
        self.assertEqual(validate_catalog_csv(path), [])

    def test_supplier_column_mapping_is_configurable(self):
        path = self.write_csv(
            "CODIGO;DESCRIPCION;PRECIO;EXISTENCIA\nA;Widget;10;3\n"
        )
        self.assertEqual(
            validate_catalog_csv(
                path,
                sku_column="CODIGO",
                name_column="DESCRIPCION",
                price_column="PRECIO",
                stock_column="EXISTENCIA",
            ),
            [],
        )

    def test_missing_required_column_fails_before_validation(self):
        path = self.write_csv("SKU;PRODUCT_NAME\nA;Widget\n")
        with self.assertRaisesRegex(ValueError, "PRICE"):
            validate_catalog_csv(path)

    def test_duplicate_headers_are_rejected(self):
        path = self.write_csv("SKU;SKU;PRODUCT_NAME;PRICE\nA;B;Widget;10\n")
        with self.assertRaisesRegex(ValueError, "duplicate column"):
            validate_catalog_csv(path)

    def test_malformed_row_width_is_rejected(self):
        path = self.write_csv("SKU;PRODUCT_NAME;PRICE\nA;Widget;10;extra\n")
        with self.assertRaisesRegex(ValueError, "row 2"):
            validate_catalog_csv(path)

    def test_invalid_delimiter_is_rejected(self):
        path = self.write_csv("SKU;PRODUCT_NAME;PRICE\nA;Widget;10\n")
        with self.assertRaisesRegex(ValueError, "one character"):
            validate_catalog_csv(path, delimiter="||")


if __name__ == "__main__":
    unittest.main(verbosity=2)
