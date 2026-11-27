from io import BytesIO

import pytest
from nicegui import ui
from starlette.datastructures import UploadFile

from src.ui.nicegui_app import build_ui


@pytest.mark.asyncio
async def test_validation_step_is_guarded_until_provider_is_confirmed(user):
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


@pytest.mark.asyncio
async def test_product_selection_checkbox_updates_real_selection_summary(user):
    @ui.page("/")
    def page():
        build_ui()

    await user.open("/")

    csv_content = (
        "SKU;Nombre;Categoría;Precio;Stock\n"
        "TEST-001;Producto de prueba;Accesorios;1250;10\n"
    ).encode("utf-8")
    upload = next(iter(user.find(ui.upload).elements))
    upload.handle_uploads([
        UploadFile(filename="catalogo.csv", file=BytesIO(csv_content))
    ])

    await user.should_see("Confirmar mapeo del proveedor")
    user.find("Confirmar mapeo del proveedor").click()
    await user.should_see("Configuración del proveedor confirmada")

    user.find("Continuar sin exportación WooCommerce").click()
    user.find("Validar catálogo").click()
    await user.should_see("Preparación de altas completada")

    user.find("Continuar a selección de productos").click()
    await user.should_see("Producto de prueba")
    await user.should_see("0 seleccionados")

    user.find("Producto de prueba").click()

    await user.should_see("1 seleccionados")
