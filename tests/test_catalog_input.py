import unittest
from unittest.mock import patch

import src.application.catalog_input as catalog_input
from src.application.catalog_input import (
    detect_delimiter,
    get_cached_csv_data,
    read_csv_preview,
    read_csv_rows,
)


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

    def test_removes_repeated_utf8_bom_markers_at_file_start(self):
        content = b"\xef\xbb\xbf\xef\xbb\xbfSKU,Name\nA-1,Product\n"

        headers, rows = read_csv_rows(content, ",")

        self.assertEqual(headers, ["SKU", "Name"])
        self.assertEqual(rows[0]["SKU"], "A-1")

    def test_pads_missing_trailing_columns_with_empty_values(self):
        content = b"SKU,Name,Attribute 1,Attribute 2\nA-1,Product,Color\n"

        headers, rows = read_csv_rows(content, ",")

        self.assertEqual(headers, ["SKU", "Name", "Attribute 1", "Attribute 2"])
        self.assertEqual(rows[0], {
            "SKU": "A-1",
            "Name": "Product",
            "Attribute 1": "Color",
            "Attribute 2": "",
        })

    def test_preview_limit_does_not_limit_total_rows(self):
        content = "sku,name\n1,A\n2,B\n3,C\n".encode("utf-8")

        headers, preview, total_rows, blank_columns = read_csv_preview(
            content, ",", limit=2
        )

        self.assertEqual(len(preview), 2)
        self.assertEqual(total_rows, 3)
        self.assertEqual(blank_columns, 0)

    def test_zero_preview_limit_returns_no_preview_rows(self):
        content = b"sku,name\n1,A\n2,B\n"

        headers, preview, total_rows, blank_columns = read_csv_preview(
            content, ",", limit=0
        )

        self.assertEqual(headers, ["sku", "name"])
        self.assertEqual(preview, [])
        self.assertEqual(total_rows, 2)
        self.assertEqual(blank_columns, 0)

    def test_rejects_negative_preview_limit(self):
        with self.assertRaisesRegex(ValueError, "must not be negative"):
            read_csv_preview(b"sku,name\n1,A\n", ",", limit=-1)

    def test_rejects_non_integer_preview_limit(self):
        with self.assertRaisesRegex(TypeError, "must be an integer"):
            read_csv_preview(b"sku,name\n1,A\n", ",", limit="1")

    def test_rejects_boolean_preview_limit(self):
        with self.assertRaisesRegex(TypeError, "must be an integer"):
            read_csv_preview(b"sku,name\n1,A\n", ",", limit=True)

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

    def test_rejects_rows_with_more_columns_than_header(self):
        content = b"sku,name\n1,Keyboard\n2,Mouse,Unexpected\n"

        with self.assertRaisesRegex(ValueError, "más columnas.*fila 3"):
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

    def test_rejects_extra_columns_after_preview_range(self):
        content = b"sku,name\n1,First\n2,Second,Unexpected\n"

        with self.assertRaisesRegex(ValueError, "más columnas.*fila 3"):
            read_csv_rows(content, ",")

    def test_does_not_modify_source_bytes(self):
        content = b"sku,name\n1,First\n"
        original = content[:]

        read_csv_rows(content, ",")

        self.assertEqual(content, original)


class TestGetCachedCsvData(unittest.TestCase):
    def test_reuses_parsed_data_for_same_fingerprint_and_delimiter(self):
        cache = {}
        content = b"sku,name\n1,Keyboard\n"

        with patch.object(catalog_input, "read_csv_data", wraps=catalog_input.read_csv_data) as read:
            first = get_cached_csv_data(cache, "file-a", content, ",")
            second = get_cached_csv_data(cache, "file-a", content, ",")

        self.assertIs(first, second)
        self.assertEqual(read.call_count, 1)

    def test_reparses_when_file_fingerprint_changes(self):
        cache = {}
        first_content = b"sku,name\n1,Keyboard\n"
        second_content = b"sku,name\n2,Mouse\n"

        first = get_cached_csv_data(cache, "file-a", first_content, ",")
        second = get_cached_csv_data(cache, "file-b", second_content, ",")

        self.assertEqual(first[1][0]["sku"], "1")
        self.assertEqual(second[1][0]["sku"], "2")
        self.assertEqual(cache["key"], ("file-b", ","))

    def test_reparses_when_delimiter_changes(self):
        cache = {}
        comma_content = b"sku,name\n1,Keyboard\n"
        semicolon_content = b"sku;name\n2;Mouse\n"

        get_cached_csv_data(cache, "same-file", comma_content, ",")
        result = get_cached_csv_data(cache, "same-file", semicolon_content, ";")

        self.assertEqual(result[0], ["sku", "name"])
        self.assertEqual(result[1][0]["name"], "Mouse")
        self.assertEqual(cache["key"], ("same-file", ";"))

    def test_does_not_keep_stale_data_when_new_input_is_invalid(self):
        cache = {}
        valid_content = b"sku,name\n1,Keyboard\n"
        get_cached_csv_data(cache, "file-a", valid_content, ",")

        with self.assertRaises(ValueError):
            get_cached_csv_data(cache, "file-b", b"", ",")

        self.assertEqual(cache, {})


if __name__ == "__main__":
    unittest.main()