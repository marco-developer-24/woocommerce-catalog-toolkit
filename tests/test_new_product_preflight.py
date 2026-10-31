import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "src" / "new_product_preflight.py"


def write_csv(path, headers, rows, delimiter=";"):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


class NewProductPreflightTests(unittest.TestCase):
    def run_preflight(self, supplier, catalog, output, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--supplier", str(supplier),
             "--catalog", str(catalog), "--output-dir", str(output), *extra],
            text=True, capture_output=True, check=False,
        )

    def test_classifies_new_existing_duplicate_and_missing_skus(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            supplier, catalog, output = root / "supplier.csv", root / "catalog.csv", root / "output"
            write_csv(supplier, ["SKU", "Name"], [
                {"SKU": "NEW-1", "Name": "New item"},
                {"SKU": "OLD-1", "Name": "Existing item"},
                {"SKU": "DUP-1", "Name": "Duplicate A"},
                {"SKU": " DUP-1 ", "Name": "Duplicate B"},
                {"SKU": "", "Name": "Missing SKU"},
            ])
            write_csv(catalog, ["SKU", "Name"], [{"SKU": "OLD-1", "Name": "Catalog item"}])

            result = self.run_preflight(supplier, catalog, output)
            self.assertEqual(result.returncode, 0, result.stderr)

            with (output / "new_products.csv").open(encoding="utf-8-sig", newline="") as handle:
                new_rows = list(csv.DictReader(handle, delimiter=";"))
            self.assertEqual([row["SKU"] for row in new_rows], ["NEW-1"])

            with (output / "review_products.csv").open(encoding="utf-8-sig", newline="") as handle:
                review_rows = list(csv.DictReader(handle, delimiter=";"))
            statuses = [row["_PREFLIGHT_STATUS"] for row in review_rows]
            self.assertEqual(statuses.count("SKU_ALREADY_EXISTS"), 1)
            self.assertEqual(statuses.count("DUPLICATE_SKU_IN_SOURCE"), 2)
            self.assertEqual(statuses.count("MISSING_SKU"), 1)

    def test_supports_different_sku_headers_and_delimiters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            supplier, catalog, output = root / "supplier.csv", root / "catalog.csv", root / "output"
            write_csv(supplier, ["Código", "Nombre"], [
                {"Código": "NEW-1", "Nombre": "New item"},
                {"Código": "OLD-1", "Nombre": "Existing item"},
            ], delimiter=",")
            write_csv(catalog, ["SKU", "Name"], [
                {"SKU": "OLD-1", "Name": "Catalog item"},
            ], delimiter=";")

            result = self.run_preflight(
                supplier, catalog, output,
                "--supplier-sku-column", "Código",
                "--catalog-sku-column", "SKU",
                "--supplier-delimiter", ",",
                "--catalog-delimiter", ";",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with (output / "new_products.csv").open(encoding="utf-8-sig", newline="") as handle:
                new_rows = list(csv.DictReader(handle, delimiter=","))
            self.assertEqual([row["Código"] for row in new_rows], ["NEW-1"])

    def test_refuses_nonempty_output_directory_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            supplier, catalog, output = root / "supplier.csv", root / "catalog.csv", root / "output"
            output.mkdir()
            (output / "keep.txt").write_text("do not overwrite", encoding="utf-8")
            write_csv(supplier, ["SKU"], [{"SKU": "NEW-1"}])
            write_csv(catalog, ["SKU"], [])

            result = self.run_preflight(supplier, catalog, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((output / "keep.txt").read_text(encoding="utf-8"), "do not overwrite")

    def test_rejects_missing_sku_column(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            supplier, catalog = root / "supplier.csv", root / "catalog.csv"
            write_csv(supplier, ["Product"], [{"Product": "No SKU"}])
            write_csv(catalog, ["SKU"], [{"SKU": "A-1"}])

            result = self.run_preflight(supplier, catalog, root / "output")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing SKU column", result.stderr)


if __name__ == "__main__":
    unittest.main()
