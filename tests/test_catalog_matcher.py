import unittest

from src.catalog_matcher import (
    STATUS_DUPLICATE_CATALOG,
    STATUS_DUPLICATE_SOURCE,
    STATUS_EXISTS,
    STATUS_MISSING,
    STATUS_NEW,
    classify_catalog_rows,
    normalize_sku,
)


class CatalogMatcherTests(unittest.TestCase):
    def test_normalizes_case_and_outer_whitespace_only(self):
        self.assertEqual(normalize_sku("  AbC-01  "), "abc-01")
        self.assertEqual(normalize_sku("A  B"), "a  b")
        self.assertEqual(normalize_sku(""), "")

    def test_classifies_new_existing_duplicate_and_missing_supplier_skus(self):
        supplier = [
            {"SKU": "NEW-1"},
            {"SKU": "OLD-1"},
            {"SKU": "DUP-1"},
            {"SKU": " dup-1 "},
            {"SKU": ""},
        ]
        catalog = [{"SKU": "OLD-1"}]

        result = classify_catalog_rows(supplier, catalog)
        self.assertEqual(
            [item["status"] for item in result],
            [
                STATUS_NEW,
                STATUS_EXISTS,
                STATUS_DUPLICATE_SOURCE,
                STATUS_DUPLICATE_SOURCE,
                STATUS_MISSING,
            ],
        )

    def test_flags_duplicate_sku_in_woocommerce_catalog(self):
        supplier = [{"SKU": "MATCH-1"}, {"SKU": "NEW-1"}]
        catalog = [
            {"SKU": "MATCH-1"},
            {"SKU": " match-1 "},
        ]

        result = classify_catalog_rows(supplier, catalog)
        self.assertEqual(result[0]["status"], STATUS_DUPLICATE_CATALOG)
        self.assertEqual(result[0]["catalog_row_numbers"], [2, 3])
        self.assertEqual(result[1]["status"], STATUS_NEW)

    def test_matches_sku_case_insensitively_and_ignores_outer_spaces(self):
        result = classify_catalog_rows(
            [{"SupplierCode": "  AbC-01 "}],
            [{"Product SKU": "abc-01"}],
            supplier_sku_column="SupplierCode",
            catalog_sku_column="Product SKU",
        )
        self.assertEqual(result[0]["status"], STATUS_EXISTS)
        self.assertEqual(result[0]["normalized_sku"], "abc-01")
        self.assertEqual(result[0]["catalog_row_numbers"], [2])

    def test_empty_catalog_skus_do_not_match(self):
        result = classify_catalog_rows(
            [{"SKU": "A-1"}],
            [{"SKU": ""}, {"SKU": "   "}],
        )
        self.assertEqual(result[0]["status"], STATUS_NEW)

    def test_rejects_invalid_sku_column_names(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            classify_catalog_rows([], [], supplier_sku_column=" ")


if __name__ == "__main__":
    unittest.main()
