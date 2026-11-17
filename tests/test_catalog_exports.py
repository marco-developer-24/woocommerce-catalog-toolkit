import csv
import io
import unittest
import zipfile

from src.application.catalog_exports import (
    make_dict_rows_csv,
    make_issues_csv,
    make_issues_text,
    make_report_zip,
    make_summary,
)
from src.catalog_csv_report import REPORT_FIELDS


class TestCatalogExports(unittest.TestCase):
    def test_dict_rows_csv_has_bom_headers_and_ignores_extra_fields(self):
        result = make_dict_rows_csv(
            [{"SKU": "A-1", "Name": "Widget", "ignored": "value"}],
            ["SKU", "Name"],
        )

        self.assertTrue(result.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.DictReader(io.StringIO(result.decode("utf-8-sig"))))
        self.assertEqual(rows, [{"SKU": "A-1", "Name": "Widget"}])

    def test_issues_csv_uses_canonical_field_order_and_bom(self):
        issue = {
            "row_number": 2,
            "field": "SKU",
            "value": "A-1",
            "severity": "error",
            "code": "duplicate_sku",
            "message": "Duplicate SKU",
            "extra": "ignored",
        }

        result = make_issues_csv([issue])

        self.assertTrue(result.startswith(b"\xef\xbb\xbf"))
        reader = csv.DictReader(io.StringIO(result.decode("utf-8-sig")))
        self.assertEqual(tuple(reader.fieldnames), REPORT_FIELDS)
        self.assertEqual(list(reader), [{key: str(issue[key]) for key in REPORT_FIELDS}])

    def test_empty_issues_csv_still_contains_header(self):
        result = make_issues_csv([])

        self.assertTrue(result.startswith(b"\xef\xbb\xbf"))
        reader = csv.reader(io.StringIO(result.decode("utf-8-sig")))
        self.assertEqual(next(reader), list(REPORT_FIELDS))
        self.assertEqual(list(reader), [])

    def test_issues_text_preserves_existing_empty_message(self):
        self.assertEqual(
            make_issues_text([]),
            "No se detectaron incidencias según las reglas actuales.",
        )

    def test_issues_text_formats_all_issue_fields_in_order(self):
        issue = {
            "row_number": 3,
            "field": "PRICE",
            "severity": "warning",
            "code": "invalid_price",
            "value": "abc",
            "message": "Price is invalid",
        }

        self.assertEqual(
            make_issues_text([issue]),
            "Fila: 3\nCampo: PRICE\nSeveridad: warning\nCódigo: invalid_price\n"
            "Valor: abc\nDetalle: Price is invalid",
        )

    def test_summary_preserves_report_content_and_trailing_newline(self):
        mapping = {"sku": "CODIGO", "name": "NOMBRE", "price": "PRECIO", "stock": None}
        report = {
            "total_products": 4,
            "ready_products": 3,
            "products_with_errors": 1,
            "products_with_warnings": 2,
            "error_count": 1,
            "warning_count": 2,
        }

        result = make_summary("supplier.csv", "abc123", ";", mapping, report, 1)

        self.assertIn("Archivo analizado: supplier.csv", result)
        self.assertIn("Columna stock: No validada", result)
        self.assertIn("Productos analizados: 4", result)
        self.assertIn("Columnas vacías sin encabezado ignoradas: 1", result)
        self.assertTrue(result.endswith("\n"))

    def test_report_zip_contains_expected_files_and_exact_content(self):
        issues_csv = b"\xef\xbb\xbfrow_number\n2\n"
        summary = "Validation summary\n"

        result = make_report_zip(issues_csv, summary)

        with zipfile.ZipFile(io.BytesIO(result)) as archive:
            self.assertEqual(
                archive.namelist(),
                ["catalog_issues.csv", "summary.txt"],
            )
            self.assertEqual(archive.read("catalog_issues.csv"), issues_csv)
            self.assertEqual(archive.read("summary.txt").decode("utf-8"), summary)


if __name__ == "__main__":
    unittest.main()
