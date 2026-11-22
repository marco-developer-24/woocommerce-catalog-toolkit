import unittest

from src.application.catalog_preparation_report import build_preparation_review


class CatalogPreparationReviewTests(unittest.TestCase):
    def test_report_preserves_technical_status_and_applies_selection_only_to_ready(self):
        def operation_item(row_number, status, match_status, reason, sku):
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
                "READY": [
                    operation_item(2, "READY", "MISSING", "Ready for selection", "NEW-1"),
                    operation_item(5, "READY", "MISSING", "Ready for selection", "NEW-2"),
                ],
                "REVIEW": [
                    operation_item(6, "REVIEW", "AMBIGUOUS", "Needs review", "CHECK-1")
                ],
                "BLOCKED": [
                    operation_item(4, "BLOCKED", "DUPLICATE", "Duplicate SKU", "DUP-1")
                ],
                "EXCLUDED": [
                    operation_item(3, "EXCLUDED", "EXISTS", "Already exists", "OLD-1")
                ],
            },
            "selection": {
                "items": [
                    {
                        "row_number": 2,
                        "status": "SELECTED",
                        "reason_code": "SELECTED",
                        "reason": "Selected by the operator.",
                    },
                    {
                        "row_number": 5,
                        "status": "NOT_SELECTED",
                        "reason_code": "NOT_SELECTED",
                        "reason": "Not selected by the operator.",
                    },
                    {
                        "row_number": 3,
                        "status": "NOT_SELECTED",
                        "technical_status": "EXCLUDED",
                        "reason_code": "EXCLUDED",
                        "reason": "Already exists",
                    },
                    {
                        "row_number": 4,
                        "status": "NOT_SELECTED",
                        "technical_status": "BLOCKED",
                        "reason_code": "BLOCKED",
                        "reason": "Duplicate SKU",
                    },
                    {
                        "row_number": 6,
                        "status": "NOT_SELECTED",
                        "technical_status": "REVIEW",
                        "reason_code": "REVIEW",
                        "reason": "Needs review",
                    },
                ]
            },
        }

        rows = build_preparation_review(result, "Category", "Price")

        self.assertEqual([row["CSV row"] for row in rows], [2, 3, 4, 5, 6])
        self.assertEqual(
            [row["Status"] for row in rows],
            ["SELECTED", "EXCLUDED", "BLOCKED", "NOT_SELECTED", "REVIEW"],
        )
        self.assertEqual(rows[0]["Reason code"], "SELECTED")
        self.assertEqual(rows[1]["Reason"], "Already exists")
        self.assertEqual(rows[2]["Reason"], "Duplicate SKU")
        self.assertEqual(rows[3]["Reason code"], "NOT_SELECTED")
        self.assertEqual(rows[4]["Reason code"], "STOCK_REVIEW")
        self.assertIsNone(rows[0]["Category position"])

    def test_report_handles_missing_selection_item_for_technical_row(self):
        result = {
            "add_products": {
                "READY": [],
                "REVIEW": [{
                    "row_number": 2,
                    "row": {"SKU": "CHECK", "Category": "Notebooks", "Price": "50"},
                    "sku": "CHECK",
                    "status": "REVIEW",
                    "match_status": "AMBIGUOUS",
                    "reason": "Needs review",
                }],
                "BLOCKED": [],
                "EXCLUDED": [],
            },
            "selection": {"items": []},
        }

        rows = build_preparation_review(result, "Category", "Price")
        self.assertEqual(rows[0]["Status"], "REVIEW")
        self.assertEqual(rows[0]["Price"], "50")


if __name__ == "__main__":
    unittest.main()
