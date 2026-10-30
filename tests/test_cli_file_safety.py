import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "src" / "image_url_auditor.py"


class TestCliFileSafety(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def write_csv(self, name="input.csv", content=None):
        path = self.root / name
        if content is None:
            content = (
                "SKU;PRODUCT_NAME;IMAGE_URL\n"
                "A1;Demo;https://example.com/image.jpg\n"
            )
        path.write_text(content, encoding="utf-8-sig")
        return path

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_refuses_to_overwrite_existing_output(self):
        source = self.write_csv()
        output = self.root / "report.csv"
        output.write_text("KEEP THIS FILE", encoding="utf-8")

        result = self.run_cli(
            "--input", source,
            "--output", output,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_text(encoding="utf-8"), "KEEP THIS FILE")

    def test_refuses_same_input_and_output_path(self):
        source = self.write_csv()
        original = source.read_bytes()

        result = self.run_cli(
            "--input", source,
            "--output", source,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(source.read_bytes(), original)

    def test_refuses_duplicate_headers(self):
        source = self.write_csv(
            content=(
                "SKU;PRODUCT_NAME;IMAGE_URL;SKU\n"
                "A1;Demo;https://example.com/image.jpg;A2\n"
            )
        )
        output = self.root / "report.csv"

        result = self.run_cli(
            "--input", source,
            "--output", output,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_refuses_rows_with_extra_fields(self):
        source = self.write_csv(
            content=(
                "SKU;PRODUCT_NAME;IMAGE_URL\n"
                "A1;Demo;https://example.com/image.jpg;UNEXPECTED\n"
            )
        )
        output = self.root / "report.csv"

        result = self.run_cli(
            "--input", source,
            "--output", output,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_refuses_rows_with_missing_fields(self):
        source = self.write_csv(
            content=(
                "SKU;PRODUCT_NAME;IMAGE_URL\n"
                "A1;Demo\n"
            )
        )
        output = self.root / "report.csv"

        result = self.run_cli(
            "--input", source,
            "--output", output,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_rejects_non_finite_and_non_positive_timeouts(self):
        source = self.write_csv()
        invalid_timeouts = ("nan", "inf", "-inf", "0", "-1")

        for timeout in invalid_timeouts:
            with self.subTest(timeout=timeout):
                output = self.root / f"report-{timeout}.csv"
                result = self.run_cli(
                    "--input", source,
                    "--output", output,
                    f"--timeout={timeout}",
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn("finite number greater than zero", result.stderr)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
