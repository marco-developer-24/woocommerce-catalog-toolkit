import unittest

from src.application.catalog_input import detect_delimiter, read_csv_preview, read_csv_rows


class TestDetectDelimiter(unittest.TestCase):
    def test_detects_supported_delimiters(self):
        samples = [
            ("sku;name\n1;Keyboard", ";"),
            ("sku,name\n1,Keyboard", ","),
            ("sku\tname\n1\tKeyboard", "\t"),
            ("sku|name\n1|Keyboard", "|"),
        ]

        for sample, expected in samples:
            with self.subTest(delimiter=repr(expected)):
                self.assertEqual(detect_delimiter(sample), expected)

    def test_falls_back_to_semicolon_when_sample_is_ambiguous(self):
        self.assertEqual(detect_delimiter(""), ";")


class TestReadCsvPreview(unittest.TestCase):
    def test_reads_utf8_csv(self):
        content = "sku,name\n1,Teclado\n".encode("utf-8")

        result = read_csv_preview(content, ",")

        self.assertEqual(
            result,
            (["sku", "name"], [{"sku": "1", "name": "Teclado"}], 1, 0),
        )

    def test_reads_utf8_bom_csv(self):
        content = "\ufeffsku,name\n1,Teclado\n".encode("utf-8")

        headers, preview, total_rows, blank_columns = read_csv_preview(content, ",")

        self.assertEqual(headers, ["sku", "name"])
        self.assertEqual(preview[0]["sku"], "1")
        self.assertEqual(total_rows, 1)
        self.assertEqual(blank_columns, 0)

    def test_preview_limit_does_not_limit_total_rows(self):
        content = "sku,name\n1,A\n2,B\n3,C\n".encode("utf-8")

        headers, preview, total_rows, blank_columns = read_csv_preview(
            content, ",", limit=2
        )

        self.assertEqual(len(preview), 2)
        self.assertEqual(total_rows, 3)
        self.assertEqual(blank_columns, 0)

    def test_ignores_empty_header_only_when_its_column_has_no_data(self):
        content = "sku,,name\n1,,Keyboard\n".encode("utf-8")

        headers, preview, total_rows, blank_columns = read_csv_preview(content, ",")

        self.assertEqual(headers, ["sku", "name"])
        self.assertEqual(preview, [{"sku": "1", "name": "Keyboard"}])
        self.assertEqual(total_rows, 1)
        self.assertEqual(blank_columns, 1)

    def test_rejects_empty_csv(self):
        with self.assertRaisesRegex(ValueError, "vacío"):
            read_csv_preview(b"", ",")

    def test_rejects_headers_without_names(self):
        with self.assertRaisesRegex(ValueError, "no contiene columnas"):
            read_csv_preview(b",\n,\n", ",")

    def test_rejects_duplicate_headers(self):
        with self.assertRaisesRegex(ValueError, "duplicados"):
            read_csv_preview(b"sku,sku\n1,2\n", ",")

    def test_rejects_data_in_column_without_header(self):
        content = "sku,,name\n1,unexpected,Keyboard\n".encode("utf-8")

        with self.assertRaisesRegex(ValueError, "no tiene encabezado"):
            read_csv_preview(content, ",")

    def test_rejects_rows_with_different_column_count(self):
        content = "sku,name\n1,Keyboard\n2\n".encode("utf-8")

        with self.assertRaisesRegex(ValueError, "fila 3"):
            read_csv_preview(content, ",")

    def test_does_not_modify_original_bytes(self):
        content = b"\xef\xbb\xbfsku,name\n1,Keyboard\n"
        original = content[:]

        read_csv_preview(content, ",")

        self.assertEqual(content, original)

    def test_validates_rows_beyond_preview_limit(self):
        content = "sku,name\n1,A\n2,B\n3\n".encode("utf-8")

        with self.assertRaisesRegex(ValueError, "fila 4"):
            read_csv_preview(content, ",", limit=1)



class TestReadCsvRows(unittest.TestCase):
    def test_reads_all_rows_and_utf8_bom(self):
        content = "\ufeffsku,name\n1,First\n2,Second\n".encode("utf-8")

        headers, rows = read_csv_rows(content, ",")

        self.assertEqual(headers, ["sku", "name"])
        self.assertEqual(rows, [
            {"sku": "1", "name": "First"},
            {"sku": "2", "name": "Second"},
        ])

    def test_rejects_malformed_rows_after_preview_range(self):
        content = b"sku,name\n1,First\n2\n"

        with self.assertRaisesRegex(ValueError, "fila 3"):
            read_csv_rows(content, ",")

    def test_does_not_modify_source_bytes(self):
        content = b"sku,name\n1,First\n"
        original = content[:]

        read_csv_rows(content, ",")

        self.assertEqual(content, original)

if __name__ == "__main__":
    unittest.main()