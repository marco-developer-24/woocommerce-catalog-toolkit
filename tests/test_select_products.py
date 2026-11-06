
import unittest

from src.operations.select_products import (
    INELIGIBLE,
    NOT_SELECTED,
    SELECTED,
    normalize_category,
    select_products,
)


class NormalizeCategoryTests(unittest.TestCase):
    def test_ignores_case_and_outer_whitespace(self):
        self.assertEqual(normalize_category("  NOTEBOOKS "), "notebooks")
        self.assertEqual(normalize_category("Notebooks"), "notebooks")

    def test_does_not_use_fuzzy_matching(self):
        self.assertNotEqual(
            normalize_category("NOTEBOOK"),
            normalize_category("NOTEBOOKS"),
        )

    def test_zero_is_not_treated_as_blank(self):
        self.assertEqual(normalize_category(0), "0")

    def test_none_is_treated_as_blank(self):
        self.assertEqual(normalize_category(None), "")


class SelectProductsTests(unittest.TestCase):
    def test_selects_lowest_prices_within_category_limit(self):
        rows = [
            {"Category": "Notebooks", "Price": "300"},
            {"Category": "Notebooks", "Price": "100"},
            {"Category": "Notebooks", "Price": "200"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"NOTEBOOKS": 2},
        )

        self.assertEqual(
            [item["status"] for item in result["items"]],
            [NOT_SELECTED, SELECTED, SELECTED],
        )
        self.assertEqual(
            [item["category_position"] for item in result["items"]],
            [3, 1, 2],
        )
        self.assertEqual(result["summary"]["notebooks"]["eligible"], 3)
        self.assertEqual(result["summary"]["notebooks"]["selected"], 2)
        self.assertEqual(result["summary"]["notebooks"]["not_selected"], 1)

    def test_category_limits_are_independent(self):
        rows = [
            {"Category": "Notebooks", "Price": "100"},
            {"Category": "RAM", "Price": "50"},
            {"Category": "Notebooks", "Price": "200"},
            {"Category": "RAM", "Price": "75"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={
                "Notebooks": 1,
                "RAM": 2,
            },
        )

        self.assertEqual(
            [item["status"] for item in result["items"]],
            [SELECTED, SELECTED, NOT_SELECTED, SELECTED],
        )
        self.assertEqual(result["summary"]["notebooks"]["selected"], 1)
        self.assertEqual(result["summary"]["ram"]["selected"], 2)

    def test_invalid_prices_are_ineligible_and_do_not_use_quota(self):
        rows = [
            {"Category": "RAM", "Price": ""},
            {"Category": "RAM", "Price": "-10"},
            {"Category": "RAM", "Price": "invalid"},
            {"Category": "RAM", "Price": "50"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"RAM": 1},
        )

        self.assertEqual(
            [item["status"] for item in result["items"]],
            [INELIGIBLE, INELIGIBLE, INELIGIBLE, SELECTED],
        )
        self.assertEqual(result["summary"]["ram"]["eligible"], 1)
        self.assertEqual(result["summary"]["ram"]["ineligible"], 3)

    def test_applies_minimum_stock_before_selection(self):
        rows = [
            {"Category": "RAM", "Price": "10", "Stock": "2"},
            {"Category": "RAM", "Price": "20", "Stock": "5"},
            {"Category": "RAM", "Price": "30", "Stock": "8"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"RAM": 1},
            stock_column="Stock",
            minimum_stock=5,
        )

        self.assertEqual(
            [item["status"] for item in result["items"]],
            [INELIGIBLE, SELECTED, NOT_SELECTED],
        )
        self.assertEqual(
            result["items"][0]["reason_code"],
            "STOCK_BELOW_MINIMUM",
        )

    def test_invalid_stock_is_ineligible_when_minimum_is_configured(self):
        rows = [
            {"Category": "RAM", "Price": "10", "Stock": ""},
            {"Category": "RAM", "Price": "20", "Stock": "5"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"RAM": 1},
            stock_column="Stock",
            minimum_stock=1,
        )

        self.assertEqual(
            [item["status"] for item in result["items"]],
            [INELIGIBLE, SELECTED],
        )
        self.assertEqual(
            result["items"][0]["reason_code"],
            "INVALID_STOCK",
        )

    def test_equal_prices_keep_original_order_for_selection(self):
        rows = [
            {"Category": "RAM", "Price": "10", "SKU": "FIRST"},
            {"Category": "RAM", "Price": "10.00", "SKU": "SECOND"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"RAM": 1},
        )

        self.assertEqual(
            [item["status"] for item in result["items"]],
            [SELECTED, NOT_SELECTED],
        )
        self.assertEqual(result["items"][0]["row"]["SKU"], "FIRST")

    def test_preserves_original_rows_without_mutating_input(self):
        rows = [
            {"Category": "RAM", "Price": "10", "Extra": "original"},
        ]
        original = [dict(row) for row in rows]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"RAM": 1},
        )

        self.assertEqual(rows, original)
        self.assertEqual(result["items"][0]["row"], original[0])
        self.assertIsNot(result["items"][0]["row"], rows[0])

    def test_unconfigured_category_is_not_selected(self):
        rows = [
            {"Category": "SSD", "Price": "10"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"RAM": 1},
        )

        self.assertEqual(result["items"][0]["status"], NOT_SELECTED)
        self.assertEqual(
            result["items"][0]["reason_code"],
            "CATEGORY_NOT_ENABLED",
        )

    def test_missing_category_is_ineligible(self):
        rows = [
            {"Category": "", "Price": "10"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"RAM": 1},
        )

        self.assertEqual(result["items"][0]["status"], INELIGIBLE)
        self.assertEqual(
            result["items"][0]["reason_code"],
            "MISSING_CATEGORY",
        )

    def test_unlimited_category_limit_selects_all_eligible_products(self):
        rows = [
            {"Category": "RAM", "Price": "30"},
            {"Category": "RAM", "Price": "10"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"RAM": None},
        )

        self.assertEqual(
            [item["status"] for item in result["items"]],
            [SELECTED, SELECTED],
        )

    def test_row_numbers_start_at_two_to_match_csv_lines(self):
        rows = [
            {"Category": "RAM", "Price": "10"},
            {"Category": "RAM", "Price": "20"},
        ]

        result = select_products(
            rows,
            category_column="Category",
            price_column="Price",
            category_limits={"RAM": 2},
        )

        self.assertEqual(
            [item["row_number"] for item in result["items"]],
            [2, 3],
        )


class SelectProductsValidationTests(unittest.TestCase):
    def test_requires_category_and_price_columns(self):
        with self.assertRaises(ValueError):
            select_products(
                [],
                category_column="",
                price_column="Price",
                category_limits={},
            )

    def test_category_limits_must_be_a_dictionary(self):
        with self.assertRaises(ValueError):
            select_products(
                [],
                category_column="Category",
                price_column="Price",
                category_limits=[],
            )

    def test_rejects_blank_category_names(self):
        with self.assertRaises(ValueError):
            select_products(
                [],
                category_column="Category",
                price_column="Price",
                category_limits={" ": 1},
            )

    def test_rejects_duplicate_normalized_categories(self):
        with self.assertRaises(ValueError):
            select_products(
                [],
                category_column="Category",
                price_column="Price",
                category_limits={
                    "RAM": 1,
                    " ram ": 2,
                },
            )

    def test_rejects_negative_or_non_integer_limits(self):
        invalid_limits = [-1, 1.5, True, "2"]

        for limit in invalid_limits:
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    select_products(
                        [],
                        category_column="Category",
                        price_column="Price",
                        category_limits={"RAM": limit},
                    )

    def test_minimum_stock_requires_stock_column(self):
        with self.assertRaises(ValueError):
            select_products(
                [],
                category_column="Category",
                price_column="Price",
                category_limits={"RAM": 1},
                minimum_stock=5,
            )

    def test_rejects_invalid_minimum_stock(self):
        for value in ("invalid", -1, float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    select_products(
                        [],
                        category_column="Category",
                        price_column="Price",
                        category_limits={"RAM": 1},
                        stock_column="Stock",
                        minimum_stock=value,
                    )


if __name__ == "__main__":
    unittest.main()
