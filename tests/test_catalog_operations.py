import unittest

from src.operations.add_products import prepare_add_products
from src.operations.update_price_stock import prepare_price_stock_updates
from src.operations.common import READY, REVIEW, BLOCKED, EXCLUDED


class AddProductsOperationTests(unittest.TestCase):
    def test_only_unique_new_valid_products_are_ready_and_unpublished(self):
        supplier = [
            {"SKU": "NEW-1", "Name": "New item", "Regular price": "125.50"},
            {"SKU": "OLD-1", "Name": "Existing", "Regular price": "50"},
            {"SKU": "", "Name": "No SKU", "Regular price": "10"},
            {"SKU": "BAD-1", "Name": "Bad price", "Regular price": "12,50"},
        ]
        catalog = [{"SKU": "OLD-1"}]
        result = prepare_add_products(supplier, catalog)
        self.assertEqual([x["status"] for x in result[READY]], [READY])
        self.assertEqual(result[READY][0]["changes"], {
            "SKU": "NEW-1", "Name": "New item", "Regular price": "125.5",
            "Published": "0", "Type": "simple",
        })
        self.assertEqual(len(result[EXCLUDED]), 1)
        self.assertEqual(len(result[BLOCKED]), 2)

    def test_duplicate_supplier_skus_are_blocked(self):
        rows = [
            {"SKU": "DUP", "Name": "One", "Regular price": "1"},
            {"SKU": "dup", "Name": "Two", "Regular price": "2"},
        ]
        result = prepare_add_products(rows, [])
        self.assertEqual(len(result[BLOCKED]), 2)
        self.assertEqual(len(result[READY]), 0)

    def test_custom_sku_column_is_preserved_in_operation_result(self):
        row = {"ProductCode": "NEW-7", "Title": "Item", "Price": "7.50"}
        result = prepare_add_products(
            [row], [],
            supplier_sku_column="ProductCode",
            name_column="Title",
            price_column="Price",
        )
        self.assertEqual(result[READY][0]["sku"], "NEW-7")
        self.assertEqual(result[READY][0]["changes"]["SKU"], "NEW-7")

    def test_does_not_mutate_input_rows(self):
        row = {"SKU": "NEW", "Name": "Item", "Regular price": "10"}
        original = dict(row)
        prepare_add_products([row], [])
        self.assertEqual(row, original)


class UpdatePriceStockOperationTests(unittest.TestCase):
    def test_prepares_only_price_and_managed_stock_fields(self):
        supplier = [{"SKU": "A-1", "Regular price": "99.90", "Stock": "0", "Name": "Ignored"}]
        catalog = [{"SKU": "A-1", "Manage stock?": "1", "Name": "Original name"}]
        result = prepare_price_stock_updates(supplier, catalog)
        self.assertEqual(len(result[READY]), 1)
        self.assertEqual(result[READY][0]["changes"], {"Regular price": "99.9", "Stock": "0"})

    def test_blank_values_do_not_create_changes(self):
        result = prepare_price_stock_updates(
            [{"SKU": "A-1", "Regular price": "", "Stock": ""}],
            [{"SKU": "A-1", "Manage stock?": "1"}],
        )
        self.assertEqual(len(result[EXCLUDED]), 1)
        self.assertEqual(result[EXCLUDED][0]["changes"], {})

    def test_invalid_price_is_reviewed_but_valid_stock_can_be_prepared(self):
        result = prepare_price_stock_updates(
            [{"SKU": "A-1", "Regular price": "12,50", "Stock": "3"}],
            [{"SKU": "A-1", "Manage stock?": "yes"}],
        )
        self.assertEqual(len(result[REVIEW]), 1)
        self.assertEqual(result[REVIEW][0]["changes"], {"Stock": "3"})

    def test_stock_is_not_prepared_when_woocommerce_does_not_manage_it(self):
        result = prepare_price_stock_updates(
            [{"SKU": "A-1", "Regular price": "", "Stock": "5"}],
            [{"SKU": "A-1", "Manage stock?": "0"}],
        )
        self.assertEqual(len(result[REVIEW]), 1)
        self.assertEqual(result[REVIEW][0]["changes"], {})

    def test_new_products_are_excluded_from_update_operation(self):
        result = prepare_price_stock_updates(
            [{"SKU": "NEW", "Regular price": "10", "Stock": "2"}],
            [],
        )
        self.assertEqual(len(result[EXCLUDED]), 1)

    def test_duplicate_catalog_sku_blocks_update(self):
        result = prepare_price_stock_updates(
            [{"SKU": "A-1", "Regular price": "10", "Stock": "2"}],
            [{"SKU": "A-1", "Manage stock?": "1"}, {"SKU": "a-1", "Manage stock?": "1"}],
        )
        self.assertEqual(len(result[BLOCKED]), 1)


if __name__ == "__main__":
    unittest.main()
