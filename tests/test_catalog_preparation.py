
import unittest

from src.application.catalog_preparation import prepare_catalog
from src.operations.common import BLOCKED
from src.operations.select_products import INELIGIBLE, NOT_SELECTED


class CatalogPreparationTests(unittest.TestCase):
    def setUp(self):
        self.supplier_rows = [
            {
                "SKU": "NEW-1",
                "Name": "New product",
                "Regular price": "100",
                "Category": "Accessories",
                "Stock": "10",
            },
            {
                "SKU": "OLD-1",
                "Name": "Existing product",
                "Regular price": "200",
                "Category": "Accessories",
                "Stock": "5",
            },
            {
                "SKU": "NEW-2",
                "Name": "Second new product",
                "Regular price": "150",
                "Category": "Accessories",
                "Stock": "8",
            },
            {
                "SKU": "DUP-1",
                "Name": "Duplicate A",
                "Regular price": "50",
                "Category": "Accessories",
                "Stock": "4",
            },
            {
                "SKU": " dup-1 ",
                "Name": "Duplicate B",
                "Regular price": "60",
                "Category": "Accessories",
                "Stock": "3",
            },
        ]

        self.catalog_rows = [
            {"SKU": "OLD-1"},
        ]

        self.selection_config = {
            "category_column": "Category",
            "price_column": "Regular price",
            "category_limits": {"Accessories": 3},
        }

        self.supplier_columns = {
            "sku": "SKU",
            "name": "Name",
            "price": "Regular price",
        }

    def test_exports_only_selected_unique_new_products_ready_for_addition(self):
        result = prepare_catalog(
            self.supplier_rows,
            self.catalog_rows,
            selection_config=self.selection_config,
            supplier_columns=self.supplier_columns,
        )

        exported_skus = [row["SKU"] for row in result["export_rows"]]

        self.assertEqual(exported_skus, ["NEW-1", "NEW-2"])

    def test_existing_products_are_not_exported(self):
        result = prepare_catalog(
            self.supplier_rows,
            self.catalog_rows,
            selection_config=self.selection_config,
            supplier_columns=self.supplier_columns,
        )

        exported_skus = [row["SKU"] for row in result["export_rows"]]

        self.assertNotIn("OLD-1", exported_skus)

    def test_duplicate_supplier_skus_are_not_exported(self):
        result = prepare_catalog(
            self.supplier_rows,
            self.catalog_rows,
            selection_config=self.selection_config,
            supplier_columns=self.supplier_columns,
        )

        exported_skus = [row["SKU"] for row in result["export_rows"]]

        self.assertNotIn("DUP-1", exported_skus)
        self.assertNotIn(" dup-1 ", exported_skus)

    def test_preserves_original_supplier_row_numbers(self):
        result = prepare_catalog(
            self.supplier_rows,
            self.catalog_rows,
            selection_config=self.selection_config,
            supplier_columns=self.supplier_columns,
        )

        exported_rows = result["export_items"]

        self.assertEqual(
            [item["row_number"] for item in exported_rows],
            [2, 4],
        )

    def test_does_not_mutate_input_rows(self):
        original_supplier = [dict(row) for row in self.supplier_rows]
        original_catalog = [dict(row) for row in self.catalog_rows]

        prepare_catalog(
            self.supplier_rows,
            self.catalog_rows,
            selection_config=self.selection_config,
            supplier_columns=self.supplier_columns,
        )

        self.assertEqual(self.supplier_rows, original_supplier)
        self.assertEqual(self.catalog_rows, original_catalog)

    def _prepare(
        self,
        *,
        supplier_rows=None,
        catalog_rows=None,
        selection_config=None,
        supplier_columns=None,
    ):
        return prepare_catalog(
            self.supplier_rows if supplier_rows is None else supplier_rows,
            self.catalog_rows if catalog_rows is None else catalog_rows,
            selection_config=(
                self.selection_config
                if selection_config is None
                else selection_config
            ),
            supplier_columns=(
                self.supplier_columns
                if supplier_columns is None
                else supplier_columns
            ),
        )

    def test_zero_category_limit_exports_nothing(self):
        selection_config = {
            **self.selection_config,
            "category_limits": {"Accessories": 0},
        }

        result = self._prepare(selection_config=selection_config)

        self.assertEqual(result["export_rows"], [])
        self.assertEqual(result["export_items"], [])
        self.assertEqual(result["summary"]["new_ready"], 2)
        self.assertEqual(result["summary"]["exported"], 0)
        self.assertEqual(
            [item["status"] for item in result["selection"]["items"]],
            [NOT_SELECTED, NOT_SELECTED],
        )
        self.assertEqual(
            [item["reason_code"] for item in result["selection"]["items"]],
            ["CATEGORY_LIMIT_REACHED", "CATEGORY_LIMIT_REACHED"],
        )

    def test_minimum_stock_excludes_products_below_threshold(self):
        selection_config = {
            **self.selection_config,
            "stock_column": "Stock",
            "minimum_stock": 9,
        }

        result = self._prepare(selection_config=selection_config)

        self.assertEqual(
            [row["SKU"] for row in result["export_rows"]],
            ["NEW-1"],
        )
        self.assertEqual(
            [item["row_number"] for item in result["export_items"]],
            [2],
        )
        below_minimum = next(
            item
            for item in result["selection"]["items"]
            if item["row"]["SKU"] == "NEW-2"
        )
        self.assertEqual(below_minimum["status"], INELIGIBLE)
        self.assertEqual(below_minimum["reason_code"], "STOCK_BELOW_MINIMUM")

    def test_unenabled_category_is_not_exported(self):
        selection_config = {
            **self.selection_config,
            "category_limits": {"Electronics": 2},
        }

        result = self._prepare(selection_config=selection_config)

        self.assertEqual(result["export_rows"], [])
        self.assertEqual(
            [item["status"] for item in result["selection"]["items"]],
            [NOT_SELECTED, NOT_SELECTED],
        )
        self.assertEqual(
            [item["reason_code"] for item in result["selection"]["items"]],
            ["CATEGORY_NOT_ENABLED", "CATEGORY_NOT_ENABLED"],
        )

    def test_invalid_selection_price_is_not_exported(self):
        supplier_rows = [
            {
                "SKU": "NEW-3",
                "Name": "Invalid selection price",
                "Regular price": "10",
                "Selection price": "not-a-number",
                "Category": "Accessories",
            }
        ]
        selection_config = {
            **self.selection_config,
            "price_column": "Selection price",
        }

        result = self._prepare(
            supplier_rows=supplier_rows,
            selection_config=selection_config,
        )

        self.assertEqual(result["export_rows"], [])
        self.assertEqual(len(result["selection"]["items"]), 1)
        self.assertEqual(result["selection"]["items"][0]["status"], INELIGIBLE)
        self.assertEqual(
            result["selection"]["items"][0]["reason_code"],
            "INVALID_PRICE",
        )

    def test_invalid_supplier_price_is_blocked_and_not_exported(self):
        supplier_rows = [
            {
                "SKU": "BAD-PRICE",
                "Name": "Bad price",
                "Regular price": "12,50",
                "Category": "Accessories",
            }
        ]

        result = self._prepare(supplier_rows=supplier_rows)

        self.assertEqual(result["export_rows"], [])
        self.assertEqual(
            [item["sku"] for item in result["add_products"][BLOCKED]],
            ["BAD-PRICE"],
        )

    def test_export_rows_match_export_items_changes(self):
        result = self._prepare()

        self.assertEqual(len(result["export_items"]), len(result["export_rows"]))
        for item, row in zip(result["export_items"], result["export_rows"]):
            with self.subTest(sku=row["SKU"]):
                self.assertEqual(row, item["changes"])
                self.assertIsNot(row, item["changes"])
                self.assertEqual(row["SKU"], item["sku"])
                self.assertEqual(row["Published"], "0")
                self.assertEqual(row["Type"], "simple")

    def test_selection_preserves_original_supplier_row_numbers(self):
        result = self._prepare()

        self.assertEqual(
            [item["row_number"] for item in result["selection"]["items"]],
            [2, 4],
        )

class CatalogPreparationValidationTests(unittest.TestCase):
    def setUp(self):
        self.supplier_rows = [
            {
                "SKU": "NEW-1",
                "Name": "New product",
                "Regular price": "10",
                "Category": "Accessories",
                "Stock": "5",
            }
        ]
        self.catalog_rows = []
        self.selection_config = {
            "category_column": "Category",
            "price_column": "Regular price",
            "category_limits": {"Accessories": 1},
        }
        self.supplier_columns = {
            "sku": "SKU",
            "name": "Name",
            "price": "Regular price",
        }

    def _prepare(self, *, selection_config=None, supplier_columns=None):
        return prepare_catalog(
            self.supplier_rows,
            self.catalog_rows,
            selection_config=(
                self.selection_config
                if selection_config is None
                else selection_config
            ),
            supplier_columns=(
                self.supplier_columns
                if supplier_columns is None
                else supplier_columns
            ),
        )

    def test_rejects_incomplete_selection_config(self):
        for key in ("category_column", "price_column", "category_limits"):
            with self.subTest(key=key):
                selection_config = dict(self.selection_config)
                del selection_config[key]

                with self.assertRaisesRegex(ValueError, key):
                    self._prepare(selection_config=selection_config)

    def test_rejects_incomplete_supplier_columns(self):
        for key in ("sku", "name", "price"):
            with self.subTest(key=key):
                supplier_columns = dict(self.supplier_columns)
                del supplier_columns[key]

                with self.assertRaisesRegex(ValueError, key):
                    self._prepare(supplier_columns=supplier_columns)

    def test_rejects_non_dictionary_configurations(self):
        with self.assertRaisesRegex(TypeError, "selection_config"):
            prepare_catalog(
                self.supplier_rows,
                self.catalog_rows,
                selection_config=[],
                supplier_columns=self.supplier_columns,
            )

        with self.assertRaisesRegex(TypeError, "supplier_columns"):
            prepare_catalog(
                self.supplier_rows,
                self.catalog_rows,
                selection_config=self.selection_config,
                supplier_columns=[],
            )

    def test_rejects_blank_required_columns(self):
        for key in ("category_column", "price_column"):
            with self.subTest(key=key):
                selection_config = {**self.selection_config, key: "  "}

                with self.assertRaisesRegex(ValueError, key):
                    self._prepare(selection_config=selection_config)

        for key in ("sku", "name", "price"):
            with self.subTest(key=key):
                supplier_columns = {**self.supplier_columns, key: ""}

                with self.assertRaisesRegex(ValueError, key):
                    self._prepare(supplier_columns=supplier_columns)

    def test_rejects_invalid_stock_column_when_provided(self):
        for value in ("", "  ", 123, False):
            with self.subTest(value=value):
                selection_config = {
                    **self.selection_config,
                    "stock_column": value,
                }

                with self.assertRaisesRegex(ValueError, "stock_column"):
                    self._prepare(selection_config=selection_config)

    def test_allows_none_stock_column(self):
        selection_config = {
            **self.selection_config,
            "stock_column": None,
        }

        result = self._prepare(selection_config=selection_config)

        self.assertEqual(
            [row["SKU"] for row in result["export_rows"]],
            ["NEW-1"],
        )

    def test_rejects_non_dictionary_category_limits(self):
        for value in (None, [], "Accessories", 3):
            with self.subTest(value=value):
                selection_config = {
                    **self.selection_config,
                    "category_limits": value,
                }

                with self.assertRaisesRegex(ValueError, "category_limits"):
                    self._prepare(selection_config=selection_config)

    def test_delegates_invalid_category_limit_values_to_selection(self):
        for limits in (
            {"Accessories": -1},
            {"Accessories": 1.5},
            {"Accessories": True},
            {"Accessories": "1"},
        ):
            with self.subTest(limits=limits):
                selection_config = {
                    **self.selection_config,
                    "category_limits": limits,
                }

                with self.assertRaisesRegex(ValueError, "limit"):
                    self._prepare(selection_config=selection_config)

    def test_minimum_stock_requires_stock_column(self):
        selection_config = {
            **self.selection_config,
            "minimum_stock": 1,
        }

        with self.assertRaisesRegex(ValueError, "minimum_stock"):
            self._prepare(selection_config=selection_config)

    def test_delegates_invalid_minimum_stock_values_to_selection(self):
        for value in (-1, "invalid", float("inf")):
            with self.subTest(value=value):
                selection_config = {
                    **self.selection_config,
                    "stock_column": "Stock",
                    "minimum_stock": value,
                }

                with self.assertRaisesRegex(ValueError, "minimum_stock"):
                    self._prepare(selection_config=selection_config)


if __name__ == "__main__":
    unittest.main()
