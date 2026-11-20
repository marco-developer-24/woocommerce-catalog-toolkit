import unittest

from src.application.provider_setup import (
    confirm_provider_setup,
    inspect_provider_file,
)


class ProviderSetupServiceTests(unittest.TestCase):
    def setUp(self):
        self.csv_bytes = (
            "CODIGO;DETALLE;CATEGORIA;PRECIO PESOS CON IVA;STOCK\n"
            "A-01;Teclado;Periféricos;12500;8\n"
            "A-02;Mouse;Periféricos;7500;0\n"
        ).encode("utf-8")

    def test_inspection_reads_rows_and_suggests_nb_mapping(self):
        result = inspect_provider_file(self.csv_bytes, "NB-lista.csv")
        self.assertEqual(result["delimiter"], ";")
        self.assertEqual(result["profile"], "NB")
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["suggestions"]["price"], "PRECIO PESOS CON IVA")
        self.assertEqual(result["suggestions"]["stock"], "STOCK")

    def test_inspection_accepts_explicit_delimiter_and_profile(self):
        result = inspect_provider_file(
            self.csv_bytes, "catalog.csv", delimiter=";", profile="NB"
        )
        self.assertEqual(result["delimiter"], ";")
        self.assertEqual(result["profile"], "NB")

    def test_inspection_rejects_non_bytes_input(self):
        with self.assertRaises(TypeError):
            inspect_provider_file("not bytes", "catalog.csv")

    def test_inspection_rejects_files_over_size_limit(self):
        with self.assertRaisesRegex(ValueError, "50 MB"):
            inspect_provider_file(b"x" * (50 * 1024 * 1024 + 1), "large.csv")

    def test_inspection_rejects_unsupported_delimiter(self):
        with self.assertRaisesRegex(ValueError, "delimiter"):
            inspect_provider_file(self.csv_bytes, "catalog.csv", delimiter=":")

    def test_inspection_rejects_unknown_profile(self):
        with self.assertRaisesRegex(ValueError, "Unknown provider profile"):
            inspect_provider_file(
                self.csv_bytes, "catalog.csv", profile="Other"
            )

    def test_confirmation_returns_validated_mapping_and_stock_policy(self):
        inspection = inspect_provider_file(self.csv_bytes, "NB-lista.csv")
        confirmed = confirm_provider_setup(
            inspection,
            {
                "sku": "CODIGO",
                "name": "DETALLE",
                "category": "CATEGORIA",
                "price": "PRECIO PESOS CON IVA",
                "stock": "STOCK",
            },
        )
        self.assertEqual(confirmed["mapping"]["price"], "PRECIO PESOS CON IVA")
        self.assertEqual(confirmed["stock_policy"], "validate_column")
        self.assertEqual(
            confirmed["mapping_fingerprint"],
            (
                inspection["file_hash"],
                inspection["delimiter"],
                inspection["profile"],
                (
                    ("sku", "CODIGO"),
                    ("name", "DETALLE"),
                    ("category", "CATEGORIA"),
                    ("price", "PRECIO PESOS CON IVA"),
                    ("stock", "STOCK"),
                ),
            ),
        )

    def test_confirmation_requires_stock_review_when_column_is_absent(self):
        inspection = inspect_provider_file(self.csv_bytes, "NB-lista.csv")
        confirmed = confirm_provider_setup(
            inspection,
            {
                "sku": "CODIGO",
                "name": "DETALLE",
                "category": "CATEGORIA",
                "price": "PRECIO PESOS CON IVA",
                "stock": None,
            },
        )
        self.assertEqual(confirmed["stock_policy"], "review_all")

    def test_confirmation_rejects_invalid_mapping(self):
        inspection = inspect_provider_file(self.csv_bytes, "NB-lista.csv")
        with self.assertRaises(ValueError):
            confirm_provider_setup(
                inspection,
                {
                    "sku": "CODIGO",
                    "name": "CODIGO",
                    "category": "CATEGORIA",
                    "price": "PRECIO PESOS CON IVA",
                    "stock": None,
                },
            )


if __name__ == "__main__":
    unittest.main()
