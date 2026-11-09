import unittest

from src.application.catalog_preparation_report import build_preparation_review


class CatalogPreparationReviewTests(unittest.TestCase):
    def test_includes_all_classification_outcomes_and_preserves_source_order(self):
        def item(row_number, status, match_status, reason, sku):
            return {
                "row_number": row_number,
                "row": {
                    "SKU": sku,
                    "Category": "Notebooks",
                    "Price": "100",
                },
                "sku": sku,
                "status": status,
                "match_status": match_status,
                "reason": reason,
            }

        result = {
            "add_products": {
                "READY": [item(2, "READY", "MISSING", "Ready for selection", "NEW-1")],
                "REVIEW": [item(6, "REVIEW", "AMBIGUOUS", "Needs review", "CHECK-1")],
                "BLOCKED": [item(4, "BLOCKED", "DUPLICATE", "Duplicate SKU", "DUP-1")],
                "EXCLUDED": [item(3, "EXCLUDED", "EXISTS", "Already exists", "OLD-1")],
            },
            "selection": {
                "items": [{
                    "row_number": 2,
                    "status": "SELECTED",
                    "reason_code": "SELECTED_BY_PRICE",
                    "reason": "Selected by ascending price.",
                    "category_position": 1,
                }]
            },
        }

        rows = build_preparation_review(result, "Category", "Price")

        self.assertEqual([row["CSV row"] for row in rows], [2, 3, 4, 6])
        self.assertEqual(
            [row["Status"] for row in rows],
            ["SELECTED", "EXCLUDED", "BLOCKED", "REVIEW"],
        )
        self.assertEqual(rows[0]["Reason code"], "SELECTED_BY_PRICE")
        self.assertEqual(rows[1]["Reason"], "Already exists")
        self.assertEqual(rows[2]["Reason"], "Duplicate SKU")
        self.assertEqual(rows[3]["Reason"], "Needs review")

    def test_ready_product_outside_selection_is_reported(self):
        result = {
            "add_products": {
                "READY": [{
                    "row_number": 2,
                    "row": {"SKU": "NEW", "Category": "Notebooks", "Price": "50"},
                    "sku": "NEW",
                    "status": "READY",
                    "match_status": "MISSING",
                    "reason": "Ready for selection",
                }],
                "REVIEW": [],
                "BLOCKED": [],
                "EXCLUDED": [],
            },
            "selection": {
                "items": [{
                    "row_number": 2,
                    "status": "NOT_SELECTED",
                    "reason_code": "CATEGORY_LIMIT_REACHED",
                    "reason": "Category limit reached.",
                    "category_position": 2,
                }]
            },
        }

        rows = build_preparation_review(result, "Category", "Price")

        self.assertEqual(rows[0]["Status"], "NOT_SELECTED")
        self.assertEqual(rows[0]["Reason code"], "CATEGORY_LIMIT_REACHED")


if __name__ == "__main__":
    unittest.main()
