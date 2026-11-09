import unittest
from pathlib import Path


class TestLocalUiSyntax(unittest.TestCase):
    def test_streamlit_app_has_valid_python_syntax(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        source = app_path.read_text(encoding="utf-8")
        compile(source, str(app_path), "exec")

    def test_streamlit_app_exposes_catalog_preparation_workflow(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        source = app_path.read_text(encoding="utf-8")

        self.assertIn("from src.application.catalog_preparation import prepare_catalog", source)
        self.assertIn("from src.application.catalog_input import read_csv_rows", source)
        self.assertIn("preparation_catalog_file", source)
        self.assertIn("Categorías habilitadas para este lote", source)
        self.assertIn("catalog_preparation_selected.csv", source)
        self.assertIn("catalog_preparation_review.csv", source)
        self.assertIn('prep_result.get("signature") == current_preparation_signature', source)


if __name__ == "__main__":
    unittest.main()
