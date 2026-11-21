import unittest

from src.application.catalog_preparation import prepare_catalog
from src.application.product_selection import SELECTED, NOT_SELECTED
from src.operations.common import BLOCKED, READY, REVIEW


class CatalogPreparationTests(unittest.TestCase):
    def setUp(self):
        self.supplier_rows = [
            {"SKU": "NEW-1", "Name": "New product", "Regular price": "100", "Category": "Accessories", "Stock": "10"},
            {"SKU": "OLD-1", "Name": "Existing product", "Regular price": "200", "Category": "Accessories", "Stock": "5"},
            {"SKU": "NEW-2", "Name": "Second new product", "Regular price": "150", "Category": "Accessories", "Stock": "8"},
            {"SKU": "DUP-1", "Name": "Duplicate A", "Regular price": "50", "Category": "Accessories", "Stock": "4"},
            {"SKU": " dup-1 ", "Name": "Duplicate B", "Regular price": "60", "Category": "Accessories", "Stock": "3"},
        ]
        self.catalog_rows = [{"SKU": "OLD-1"}]
        self.config = {
            "category_column": "Category",
            "stock_column": "Stock",
            "category_mappings": {"accessories": "Hardware > Accessories"},
        }
        self.columns = {"sku": "SKU", "name": "Name", "price": "Regular price"}

    def prepare(self, *, rows=None, state=None, config=None, catalog=None):
        return prepare_catalog(
            self.supplier_rows if rows is None else rows,
            self.catalog_rows if catalog is None else catalog,
            selection_config=self.config if config is None else config,
            supplier_columns=self.columns,
            selection_state=state,
        )

    def test_all_products_start_not_selected_and_nothing_exports(self):
        result = self.prepare()
        self.assertTrue(all(value == NOT_SELECTED for value in result["selection_state"].values()))
        self.assertEqual(result["export_rows"], [])
        self.assertEqual(result["summary"]["new_ready"], 2)

    def test_exports_only_selected_ready_products_with_confirmed_destination(self):
        result = self.prepare(state={2: SELECTED, 4: SELECTED})
        self.assertEqual([row["SKU"] for row in result["export_rows"]], ["NEW-1", "NEW-2"])
        self.assertEqual([item["row_number"] for item in result["export_items"]], [2, 4])
        self.assertEqual([row["Categories"] for row in result["export_rows"]], ["Hardware > Accessories"] * 2)

    def test_existing_and_duplicate_skus_never_export(self):
        result = self.prepare(state={2: SELECTED, 3: SELECTED, 4: SELECTED, 5: SELECTED, 6: SELECTED})
        exported = [row["SKU"] for row in result["export_rows"]]
        self.assertEqual(exported, ["NEW-1", "NEW-2"])
        self.assertNotIn("OLD-1", exported)
        self.assertNotIn("DUP-1", exported)

    def test_selection_without_destination_is_retained_but_not_exported(self):
        result = self.prepare(
            state={2: SELECTED},
            config={**self.config, "category_mappings": {}},
        )
        self.assertEqual(result["selection_state"][2], SELECTED)
        self.assertEqual(result["export_rows"], [])
        self.assertEqual(result["summary"]["selected_without_destination"], 1)

    def test_destination_does_not_select_products(self):
        result = self.prepare(config={**self.config, "category_mappings": {"accessories": "Hardware > Accessories"}})
        self.assertEqual(result["selection_state"][2], NOT_SELECTED)
        self.assertEqual(result["export_rows"], [])

    def test_rows_that_are_no_longer_ready_are_reset_to_not_selected(self):
        result = self.prepare(state={2: SELECTED, 3: SELECTED, 4: SELECTED})
        self.assertEqual(result["selection_state"][3], NOT_SELECTED)
        self.assertEqual(result["selection_state"][5], NOT_SELECTED)
        self.assertEqual(result["selection_state"][6], NOT_SELECTED)

    def test_rejects_selection_rows_outside_current_supplier_session(self):
        with self.assertRaisesRegex(ValueError, "outside the current supplier session"):
            self.prepare(state={99: SELECTED})

    def test_rejects_invalid_selection_status(self):
        with self.assertRaisesRegex(ValueError, "invalid selection"):
            self.prepare(state={2: "MAYBE"})

    def test_minimum_stock_review_status_is_not_selectable(self):
        rows = [{"SKU": "LOW", "Name": "Low stock", "Regular price": "10", "Category": "Accessories", "Stock": "0"}]
        result = self.prepare(rows=rows, state={2: SELECTED})
        self.assertEqual(result["add_products"][REVIEW][0]["sku"], "LOW")
        self.assertEqual(result["selection_state"][2], NOT_SELECTED)
        self.assertEqual(result["export_rows"], [])

    def test_invalid_supplier_price_is_blocked(self):
        rows = [{"SKU": "BAD", "Name": "Bad price", "Regular price": "12,50", "Category": "Accessories", "Stock": "5"}]
        result = self.prepare(rows=rows, state={2: SELECTED})
        self.assertEqual([item["sku"] for item in result["add_products"][BLOCKED]], ["BAD"])
        self.assertEqual(result["selection_state"][2], NOT_SELECTED)

    def test_does_not_mutate_input_rows_or_selection_state(self):
        original_rows = [dict(row) for row in self.supplier_rows]
        state = {2: SELECTED}
        original_state = dict(state)
        self.prepare(state=state)
        self.assertEqual(self.supplier_rows, original_rows)
        self.assertEqual(state, original_state)

    def test_export_preserves_woocommerce_add_format(self):
        result = self.prepare(state={2: SELECTED})
        row = result["export_rows"][0]
        self.assertEqual(row["Published"], "-1")
        self.assertEqual(row["Type"], "simple")
        self.assertEqual(row["Regular price"], "100")


class CatalogPreparationValidationTests(unittest.TestCase):
    def test_requires_category_column(self):
        with self.assertRaisesRegex(ValueError, "category_column"):
            prepare_catalog([], [], selection_config={}, supplier_columns={"sku": "SKU", "name": "Name", "price": "Price"})

    def test_requires_supplier_columns(self):
        with self.assertRaisesRegex(ValueError, "price"):
            prepare_catalog([], [], selection_config={"category_column": "Category"}, supplier_columns={"sku": "SKU", "name": "Name"})


if __name__ == "__main__":
    unittest.main()
