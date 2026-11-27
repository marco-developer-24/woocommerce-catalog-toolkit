import unittest

from nicegui import ui
from nicegui.testing import user_simulation

from src.ui.nicegui_app import build_ui


class TestNiceGuiSelectionWorkflow(unittest.IsolatedAsyncioTestCase):
    async def test_selection_step_is_guarded_until_provider_is_confirmed(self):
        async with user_simulation(build_ui) as user:
            await user.open("/")
            await user.should_see("Preparación de catálogo")

            user.find("Validación").click()

            await user.should_see(
                "Primero cargá y confirmá el archivo del proveedor."
            )
            await user.should_see("Etapa actual: Archivos")


if __name__ == "__main__":
    unittest.main()
