import csv
import io
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
        "TEST-002;Producto hogar;Hogar;2500;8\n"
    ).encode("utf-8")
    uploads = user.find(ui.upload).elements
    upload = next(
        element
        for element in uploads
        if element.label == "Seleccionar CSV del proveedor"
    )
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

    product_checkbox = next(iter(user.find("Producto de prueba").elements))
    home_checkbox = next(iter(user.find("Producto hogar").elements))
    product_row = product_checkbox.parent_slot.parent.parent_slot.parent
    home_row = home_checkbox.parent_slot.parent.parent_slot.parent

    assert product_row.visible is True
    assert home_row.visible is True

    search = user.find("Buscar productos o categorías")
    search.type("Hogar")

    await user.should_see("Producto hogar")
    assert home_row.visible is True
    assert product_row.visible is False

    user.find("Producto hogar").click()
    await user.should_see("Seleccionados")
    await user.should_see("2")


@pytest.mark.asyncio
async def test_changing_suggested_destination_clears_confirmation(user):
    @ui.page("/")
    def page():
        build_ui()

    await user.open("/")

    # Keep a single provider category so the suggestion checkbox and
    # destination selector are unambiguous in this interaction test.
    provider_csv = (
        "SKU;Nombre;Categoría;Precio;Stock\n"
        "TEST-001;Producto de prueba;Accesorios;1250;10\n"
        "TEST-002;Producto hogar;Accesorios;2500;8\n"
    ).encode("utf-8")
    uploads = user.find(ui.upload).elements
    provider_upload = next(
        element
        for element in uploads
        if element.label == "Seleccionar CSV del proveedor"
    )
    provider_upload.handle_uploads([
        UploadFile(filename="proveedor.csv", file=BytesIO(provider_csv))
    ])

    await user.should_see("Confirmar mapeo del proveedor")
    user.find("Confirmar mapeo del proveedor").click()
    await user.should_see("Configuración del proveedor confirmada")
    await user.should_see("2 productos listos para comparar")

    store_upload = next(
        element
        for element in user.find(ui.upload).elements
        if element.label == "Seleccionar exportación CSV de WooCommerce"
    )
    store_csv = (
        "SKU,Name,Categories\n"
        "STORE-001,Producto existente,Accesorios\n"
        "STORE-002,Otro producto,Hogar\n"
    ).encode("utf-8")
    store_upload.handle_uploads([
        UploadFile(filename="woocommerce.csv", file=BytesIO(store_csv))
    ])

    await user.should_see("Comparar catálogos")
    user.find("Comparar catálogos").click()
    await user.should_see("Comparación por SKU completada")

    user.find("Validar catálogo").click()
    await user.should_see("Preparación de altas completada")
    user.find("Continuar a selección de productos").click()
    await user.should_see("Producto de prueba")

    user.find("Ver productos y configurar destino").click()
    await user.should_see("Sugerencia: Accesorios")

    destination_confirmation = next(
        iter(user.find("Confirmo el destino sugerido").elements)
    )
    user.find("Confirmo el destino sugerido").click()
    assert destination_confirmation.value is True

    destination_selector = user.find(
        kind=ui.select,
        content="Categoría de destino en WooCommerce",
    )
    destination_element = next(iter(destination_selector.elements))
    destination_selector.click()
    hogar_option = user.find("Hogar")
    hogar_option.elements = {destination_element}
    hogar_option.click()

    assert destination_element.value == "Hogar"
    assert destination_confirmation.value is False


@pytest.mark.asyncio
async def test_selected_product_can_be_downloaded_as_woocommerce_csv(
    user, monkeypatch
):
    downloads = []
    monkeypatch.setattr(
        ui,
        "download",
        lambda data, filename=None: downloads.append((data, filename)),
    )

    @ui.page("/")
    def page():
        build_ui()

    await user.open("/")

    provider_csv = (
        "SKU;Nombre;Categoría;Precio;Stock\n"
        "NEW-001;Producto seleccionado;Accesorios;1250;10\n"
        "NEW-002;Producto no seleccionado;Accesorios;2500;8\n"
        "OLD-001;Producto existente;Accesorios;3000;5\n"
        "LOW-001;Producto sin stock;Accesorios;900;0\n"
    ).encode("utf-8")
    provider_upload = next(
        element
        for element in user.find(ui.upload).elements
        if element.label == "Seleccionar CSV del proveedor"
    )
    provider_upload.handle_uploads([
        UploadFile(filename="proveedor.csv", file=BytesIO(provider_csv))
    ])

    await user.should_see("Confirmar mapeo del proveedor")
    user.find("Confirmar mapeo del proveedor").click()
    await user.should_see("Configuración del proveedor confirmada")

    store_upload = next(
        element
        for element in user.find(ui.upload).elements
        if element.label == "Seleccionar exportación CSV de WooCommerce"
    )
    store_csv = (
        "SKU,Name,Categories\n"
        "OLD-001,Producto existente,Accesorios\n"
    ).encode("utf-8")
    store_upload.handle_uploads([
        UploadFile(filename="woocommerce.csv", file=BytesIO(store_csv))
    ])

    await user.should_see("Comparar catálogos")
    user.find("Comparar catálogos").click()
    await user.should_see("Comparación por SKU completada")

    user.find("Validar catálogo").click()
    await user.should_see("Preparación de altas completada")
    user.find("Continuar a selección de productos").click()
    await user.should_see("Producto seleccionado")

    user.find("Ver productos y configurar destino").click()
    await user.should_see("Sugerencia: Accesorios")
    user.find("Confirmo el destino sugerido").click()

    user.find("Producto seleccionado").click()
    await user.should_see("1 seleccionados")
    await user.should_see("1 Listos para exportar")

    user.find("Continuar a exportación").click()
    await user.should_see("Descargar CSV de altas")
    user.find("Descargar CSV de altas").click()

    assert len(downloads) == 1
    csv_bytes, filename = downloads[0]
    assert filename == "woocommerce-altas.csv"

    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    assert [row["SKU"] for row in rows] == ["NEW-001"]
    assert rows[0]["Name"] == "Producto seleccionado"
    assert rows[0]["Regular price"] == "1250"
    assert rows[0]["Published"] == "-1"
    assert rows[0]["Type"] == "simple"
    assert rows[0]["Categories"] == "Accesorios"
