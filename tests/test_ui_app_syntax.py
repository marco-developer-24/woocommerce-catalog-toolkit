import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestLocalUiSyntax(unittest.TestCase):
    def test_nicegui_entry_point_has_valid_python_syntax(self):
        app_path = ROOT / "app.py"
        source = app_path.read_text(encoding="utf-8")
        compile(source, str(app_path), "exec")

    def test_nicegui_application_has_valid_python_syntax(self):
        app_path = ROOT / "src" / "ui" / "nicegui_app.py"
        source = app_path.read_text(encoding="utf-8")
        compile(source, str(app_path), "exec")

    def test_entry_point_loads_nicegui_application(self):
        app_path = ROOT / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn("from src.ui.nicegui_app import run_app", source)
        self.assertIn("run_app()", source)
        self.assertNotIn("streamlit", source.lower())

    def test_legacy_interface_is_preserved_separately(self):
        legacy_path = ROOT / "app_legacy.py"
        source = legacy_path.read_text(encoding="utf-8")
        compile(source, str(legacy_path), "exec")
        self.assertIn(
            "from src.application.catalog_preparation import prepare_catalog",
            source,
        )

    def test_old_streamlit_wizard_remains_available_as_legacy_code(self):
        wizard_path = ROOT / "src" / "ui" / "wizard.py"
        source = wizard_path.read_text(encoding="utf-8")
        compile(source, str(wizard_path), "exec")
        self.assertIn("import streamlit as st", source)


if __name__ == "__main__":
    unittest.main()
