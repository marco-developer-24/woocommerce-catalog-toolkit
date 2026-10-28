import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "src" / "image_url_auditor.py"


class TestCliOutputFailures(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def write_csv(self, content):
        path = self.root / "input.csv"
        path.write_text(content, encoding="utf-8-sig")
        return path

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_invalid_csv_does_not_create_report(self):
        source = self.write_csv(
            "SKU;PRODUCT_NAME;IMAGE_URL\n"
            "A1;Demo\n"
        )
        output = self.root / "report.csv"

        result = self.run_cli(
            "--input", source,
            "--output", output,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        self.assertIn("fewer fields", result.stderr)

    def test_output_parent_creation_failure_returns_error(self):
        source = self.write_csv(
            "SKU;PRODUCT_NAME;IMAGE_URL\n"
            "A1;Demo;\n"
        )
        parent_file = self.root / "not_a_directory"
        parent_file.write_text("keep", encoding="utf-8")
        output = parent_file / "report.csv"

        result = self.run_cli(
            "--input", source,
            "--output", output,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        self.assertEqual(parent_file.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main(verbosity=2)
