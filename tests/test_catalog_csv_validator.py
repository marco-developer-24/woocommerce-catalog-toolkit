import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from catalog_csv_validator import validate_catalog_csv
from catalog_csv_report import build_catalog_report, export_issues_csv


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

    def test_reports_empty_sku_and_product_name_as_errors(self):
        path = self.write_csv("SKU;PRODUCT_NAME;PRICE\n ; ;12.50\n")
        issues = validate_catalog_csv(path)
        self.assertEqual(
            {issue["code"] for issue in issues},
            {"empty_sku", "empty_product_name"},
        )
        self.assertTrue(all(issue["severity"] == "error" for issue in issues))

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

    def test_stock_issues_are_warnings(self):
        path = self.write_csv(
            "SKU;PRODUCT_NAME;PRICE;STOCK\n"
            "A;Invalid;10;many\nB;Negative;10;-2\nC;Fraction;10;1.5\n"
        )
        issues = validate_catalog_csv(path)
        self.assertEqual(
            [issue["code"] for issue in issues],
            ["invalid_stock", "negative_stock", "invalid_stock"],
        )
        self.assertTrue(all(issue["severity"] == "warning" for issue in issues))

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


class TestCatalogCsvReport(unittest.TestCase):
    def test_summary_counts_products_and_issues_by_severity(self):
        issues = [
            {"row_number": 2, "severity": "error"},
            {"row_number": 2, "severity": "warning"},
            {"row_number": 3, "severity": "warning"},
            {"row_number": 4, "severity": "error"},
        ]
        self.assertEqual(
            build_catalog_report(4, issues),
            {
                "total_products": 4,
                "ready_products": 2,
                "products_with_errors": 2,
                "products_with_warnings": 2,
                "total_issues": 4,
                "error_count": 2,
                "warning_count": 2,
            },
        )

    def test_summary_rejects_issue_row_outside_input(self):
        with self.assertRaisesRegex(ValueError, "exceeds"):
            build_catalog_report(1, [{"row_number": 3, "severity": "error"}])

    def test_report_csv_contains_header_and_all_issue_fields(self):
        issues = [{
            "row_number": 3,
            "field": "STOCK",
            "value": "many",
            "severity": "warning",
            "code": "invalid_stock",
            "message": "Stock must be a non-negative integer.",
        }]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.csv"
            self.assertEqual(export_issues_csv(issues, output), output)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["row_number"], "3")
            self.assertEqual(rows[0]["severity"], "warning")
            self.assertEqual(rows[0]["code"], "invalid_stock")

    def test_report_does_not_overwrite_existing_file_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.csv"
            output.write_text("keep this", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                export_issues_csv([], output)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep this")


if __name__ == "__main__":
    unittest.main(verbosity=2)
