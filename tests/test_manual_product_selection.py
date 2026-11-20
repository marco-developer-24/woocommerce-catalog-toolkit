import unittest

from src.application.catalog_preparation import prepare_catalog
from src.application.manual_product_selection import set_manual_product_selection


class ManualProductSelectionTests(unittest.TestCase):
    def setUp(self):
        self.supplier_rows = [
            {"SKU": "RAM-1", "Name": "RAM one", "Price": "100", "Category": "RAM", "Stock": "5"},
            {"SKU": "RAM-2", "Name": "RAM two", "Price": "200", "Category": "RAM", "Stock": "5"},
            {"SKU": "RAM-3", "Name": "RAM three", "Price": "300", "Category": "RAM", "Stock": "5"},
        ]
        self.category_mappings = {"ram": "Hardware > RAM"}
        self.category_limits = {"RAM": 2}
        self.result = prepare_catalog(
            self.supplier_rows,
            [],
            selection_config={
                "category_column": "Category",
                "price_column": "Price",
                "category_limits": self.category_limits,
                "stock_column": "Stock",
                "category_mappings": self.category_mappings,
                "require_category_mapping": True,
            },
            supplier_columns={"sku": "SKU", "name": "Name", "price": "Price"},
        )

    def _change(self, result, row_number, include):
        return set_manual_product_selection(
            result,
            row_number,
            include=include,
            category_mappings=self.category_mappings,
            category_limits=self.category_limits,
        )

    def test_manual_exclusion_does_not_auto_fill_quota(self):
        updated = self._change(self.result, 2, False)

        self.assertEqual([row["SKU"] for row in updated["export_rows"]], ["RAM-2"])
        self.assertEqual(updated["summary"]["exported"], 1)
        self.assertEqual(updated["summary"]["ready_not_selected"], 2)
        self.assertEqual(
            next(item for item in updated["selection"]["items"] if item["row_number"] == 2)["reason_code"],
            "MANUALLY_EXCLUDED",
        )
        self.assertEqual(
            next(item for item in updated["selection"]["items"] if item["row_number"] == 4)["status"],
            "NOT_SELECTED",
        )

    def test_manual_inclusion_uses_free_quota_and_preserves_destination(self):
        without_first = self._change(self.result, 2, False)
        updated = self._change(without_first, 4, True)

        self.assertEqual(
            [row["SKU"] for row in updated["export_rows"]],
            ["RAM-2", "RAM-3"],
        )
        self.assertEqual(
            [row["Categories"] for row in updated["export_rows"]],
            ["Hardware > RAM", "Hardware > RAM"],
        )
        self.assertEqual(updated["summary"]["exported"], 2)
        self.assertEqual(updated["summary"]["ready_not_selected"], 1)
        self.assertEqual(
            next(item for item in updated["selection"]["items"] if item["row_number"] == 4)["reason_code"],
            "MANUALLY_SELECTED",
        )

    def test_manual_inclusion_cannot_exceed_category_quota(self):
        with self.assertRaisesRegex(ValueError, "quota is full"):
            self._change(self.result, 4, True)

    def test_manual_inclusion_requires_confirmed_destination(self):
        with self.assertRaisesRegex(ValueError, "destination is required"):
            set_manual_product_selection(
                self.result,
                4,
                include=True,
                category_mappings={},
                category_limits=self.category_limits,
            )

    def test_manual_decision_does_not_mutate_original_result(self):
        original_export = [dict(row) for row in self.result["export_rows"]]
        original_statuses = [
            (item["row_number"], item["status"])
            for item in self.result["selection"]["items"]
        ]

        self._change(self.result, 2, False)

        self.assertEqual(self.result["export_rows"], original_export)
        self.assertEqual(
            [
                (item["row_number"], item["status"])
                for item in self.result["selection"]["items"]
            ],
            original_statuses,
        )

    def test_manual_inclusion_cannot_override_non_quota_exclusion(self):
        selection = self.result["selection"]["items"]
        target = next(item for item in selection if item["row_number"] == 4)
        target["reason_code"] = "CATEGORY_NOT_ENABLED"

        with self.assertRaisesRegex(ValueError, "category limit"):
            self._change(self.result, 4, True)


if __name__ == "__main__":
    unittest.main()
