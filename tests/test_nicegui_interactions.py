import pytest
from nicegui import ui
from nicegui.testing import User

from src.ui.nicegui_app import build_ui


@pytest.mark.asyncio
async def test_validation_step_is_guarded_until_provider_is_confirmed(user: User):
    @ui.page("/")
    def page():
        build_ui()

    await user.open("/")
    await user.should_see("Preparación de catálogo")

    user.find("Validación").click()

    await user.should_see(
        "Primero cargá y confirmá el archivo del proveedor."
    )
    await user.should_see("Etapa actual: Archivos")
