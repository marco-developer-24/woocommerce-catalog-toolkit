import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestLocalUiSyntax(unittest.TestCase):
    def test_streamlit_entry_point_has_valid_python_syntax(self):
        app_path = ROOT / "app.py"
        source = app_path.read_text(encoding="utf-8")
        compile(source, str(app_path), "exec")

    def test_guided_wizard_has_valid_python_syntax(self):
        wizard_path = ROOT / "src" / "ui" / "wizard.py"
        source = wizard_path.read_text(encoding="utf-8")
        compile(source, str(wizard_path), "exec")

    def test_legacy_interface_is_preserved_separately(self):
        legacy_path = ROOT / "app_legacy.py"
        source = legacy_path.read_text(encoding="utf-8")
        compile(source, str(legacy_path), "exec")
        self.assertIn("from src.application.catalog_preparation import prepare_catalog", source)

    def test_streamlit_entry_point_loads_guided_workflow(self):
        app_path = ROOT / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn("from src.ui.wizard import render_wizard", source)
        self.assertIn("render_wizard()", source)

    def test_wizard_exposes_five_ordered_stages(self):
        wizard_path = ROOT / "src" / "ui" / "wizard.py"
        source = wizard_path.read_text(encoding="utf-8")
        for stage in ("Proveedor", "Tienda", "Categorías", "Selección", "Exportación"):
            self.assertIn(stage, source)


if __name__ == "__main__":
    unittest.main()
