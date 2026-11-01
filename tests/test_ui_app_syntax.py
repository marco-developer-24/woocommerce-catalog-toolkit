import unittest
from pathlib import Path


class TestLocalUiSyntax(unittest.TestCase):
    def test_streamlit_app_has_valid_python_syntax(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        source = app_path.read_text(encoding="utf-8")
        compile(source, str(app_path), "exec")


if __name__ == "__main__":
    unittest.main()
