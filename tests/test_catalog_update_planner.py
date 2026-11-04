import csv
import tempfile
import unittest
from pathlib import Path

from src.catalog_update_planner import (
    STATUS_NEW,
    STATUS_REVIEW,
    STATUS_UNCHANGED,
    STATUS_UPDATE,
    compare_catalog_updates,
    write_update_plan,
)


class CatalogUpdatePlannerTests(unittest.TestCase):
    def setUp(self):
        self.supplier = [
            {"SKU": "A-1", "Price": "120.00", "Stock": "8", "Name": "Widget A"},
            {"SKU": "B-2", "Price": "90", "Stock": "4", "Name": "Widget B"},
            {"SKU": "C-3", "Price": "75", "Stock": "2", "Name": "Widget C"},
            {"SKU": "D-4", "Price": "50", "Stock": "1", "Name": "Widget D"},
        ]
        self.catalog = [
            {"SKU": "A-1", "Regular price": "100", "Stock quantity": "8"},
            {"SKU": "B-2", "Regular price": "90.00", "Stock quantity": "4"},
            {"SKU": "C-3", "Regular price": "70", "Stock quantity": "2"},
        ]

    def compare(self, supplier=None, catalog=None):
        return compare_catalog_updates(
            supplier if supplier is not None else self.supplier,
            catalog if catalog is not None else self.catalog,
            supplier_sku_column="SKU",
            catalog_sku_column="SKU",
            supplier_price_column="Price",
            catalog_price_column="Regular price",
            supplier_stock_column="Stock",
            catalog_stock_column="Stock quantity",
        )

    def test_identifies_price_change_without_stock_change(self):
        result = self.compare()
        item = next(row for row in result if row["sku"] == "A-1")
        self.assertEqual(item["status"], STATUS_UPDATE)
        self.assertEqual(item["changed_fields"], "price")

    def test_identifies_unchanged_values_despite_decimal_formatting(self):
        result = self.compare()
        item = next(row for row in result if row["sku"] == "B-2")
        self.assertEqual(item["status"], STATUS_UNCHANGED)
        self.assertEqual(item["changed_fields"], "")

    def test_identifies_new_sku_as_candidate_not_update(self):
        result = self.compare()
        item = next(row for row in result if row["sku"] == "D-4")
        self.assertEqual(item["status"], STATUS_NEW)

    def test_identifies_price_and_stock_changes(self):
        supplier = [{"SKU": "A-1", "Price": "125", "Stock": "3"}]
        result = self.compare(supplier=supplier)
        self.assertEqual(result[0]["status"], STATUS_UPDATE)
        self.assertEqual(result[0]["changed_fields"], "price, stock")

    def test_blank_supplier_value_requires_review_and_never_clears(self):
        supplier = [{"SKU": "A-1", "Price": "", "Stock": "8"}]
        result = self.compare(supplier=supplier)
        self.assertEqual(result[0]["status"], STATUS_REVIEW)
        self.assertIn("will not be cleared", result[0]["reason"])

    def test_duplicate_catalog_sku_requires_review(self):
        catalog = self.catalog + [
            {"SKU": "A-1", "Regular price": "100", "Stock quantity": "8"}
        ]
        result = self.compare(supplier=self.supplier[:1], catalog=catalog)
        self.assertEqual(result[0]["status"], STATUS_REVIEW)

    def test_invalid_supplier_price_requires_review(self):
        supplier = [{"SKU": "A-1", "Price": "not-a-price", "Stock": "8"}]
        result = self.compare(supplier=supplier)
        self.assertEqual(result[0]["status"], STATUS_REVIEW)
        self.assertIn("not a valid number", result[0]["reason"])

    def test_fractional_stock_requires_review(self):
        supplier = [{"SKU": "A-1", "Price": "100", "Stock": "2.5"}]
        result = self.compare(supplier=supplier)
        self.assertEqual(result[0]["status"], STATUS_REVIEW)
        self.assertIn("whole number", result[0]["reason"])

    def test_requires_at_least_one_comparable_field(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            compare_catalog_updates(self.supplier, self.catalog)

    def test_report_preserves_supplier_columns_and_adds_decision_metadata(self):
        results = self.compare()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan.csv"
            write_update_plan(results, output, ["SKU", "Price", "Stock", "Name"])
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertIn("Price", rows[0])
            self.assertIn("_PLANNER_STATUS", rows[0])
            self.assertEqual(rows[0]["_PLANNER_STATUS"], STATUS_UPDATE)

    def test_report_refuses_to_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plan.csv"
            output.write_text("preserve", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_update_plan(self.compare(), output, ["SKU", "Price", "Stock"])
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main(verbosity=2)
