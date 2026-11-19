"""NiceGUI interface for preparing WooCommerce catalog imports."""

from nicegui import ui

from src.application.provider_setup import (
    confirm_provider_setup,
    inspect_provider_file,
)
from src.application.store_setup import (
    confirm_store_setup,
    inspect_store_file,
)


MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PREVIEW_LIMIT = 5
PROVIDER_MAPPING_FIELDS = (
    ("sku", "SKU / Código"),
    ("name", "Nombre del producto"),
    ("category", "Categoría"),
    ("price", "Precio (con IVA)"),
    ("stock", "Stock (opcional)"),
)


def build_ui():
    """Build supplier setup and WooCommerce catalog comparison screens."""
    state = {
        "provider_inspection": None,
        "provider": None,
        "store_inspection": None,
        "store": None,
    }
    provider_selectors = {}
    store_selectors = {}

    ui.colors(
        primary="#2563eb",
        secondary="#64748b",
        accent="#0f172a",
        positive="#15803d",
        negative="#b91c1c",
        warning="#b45309",
    )

    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-6"):
        with ui.column().classes("w-full gap-1"):
            ui.label("CATALOG TOOLKIT").classes(
                "text-xs font-bold tracking-widest text-blue-700"
            )
            ui.label("Preparación de catálogo").classes(
                "text-3xl font-bold text-slate-900"
            )
            ui.label(
                "Prepará altas de productos desde el proveedor y comparalas "
                "con una exportación de WooCommerce. No se modifica la tienda."
            ).classes("text-slate-600")

        with ui.card().classes("w-full p-6 gap-4"):
            ui.label("1. Archivo del proveedor").classes(
                "text-lg font-semibold text-slate-900"
            )
            ui.label(
                "CSV UTF-8 · Máximo 50 MB · Procesamiento local"
            ).classes("text-sm text-slate-500")
            provider_status = ui.label("Esperando un archivo CSV…").classes(
                "text-sm text-slate-600"
            )
            provider_details = ui.column().classes("w-full gap-3")
            provider_preview = ui.column().classes("w-full gap-2")
            provider_mapping_area = ui.column().classes("w-full gap-3")
            provider_confirmation = ui.column().classes("w-full gap-2")

            with ui.column().classes("w-full gap-2"):
                provider_upload = ui.upload(
                    label="Seleccionar CSV del proveedor",
                    auto_upload=True,
                    max_file_size=MAX_UPLOAD_BYTES,
                    max_files=1,
                ).props('accept=".csv"').classes("w-full")

            def clear_store():
                state["store_inspection"] = None
                state["store"] = None
                store_selectors.clear()
                store_status.set_text("Esperando una exportación de WooCommerce…")
                store_status.classes(replace="text-sm text-slate-600")
                store_details.clear()
                store_mapping_area.clear()
                store_confirmation.clear()

            def clear_provider():
                state["provider_inspection"] = None
                state["provider"] = None
                provider_selectors.clear()
                provider_details.clear()
                provider_preview.clear()
                provider_mapping_area.clear()
                provider_confirmation.clear()
                provider_status.set_text("Esperando un archivo CSV…")
                provider_status.classes(replace="text-sm text-slate-600")
                clear_store()

            def confirm_provider_mapping():
                inspection = state["provider_inspection"]
                if inspection is None:
                    return
                mapping = {
                    field: selector.value
                    for field, selector in provider_selectors.items()
                }
                try:
                    confirmed = confirm_provider_setup(inspection, mapping)
                except (TypeError, ValueError) as exc:
                    state["provider"] = None
                    provider_confirmation.clear()
                    ui.notify(str(exc), type="negative")
                    return

                state["provider"] = confirmed
                clear_store()
                provider_confirmation.clear()
                with provider_confirmation:
                    with ui.card().classes(
                        "w-full bg-green-50 border border-green-200"
                    ):
                        ui.label("Configuración del proveedor confirmada").classes(
                            "font-semibold text-green-800"
                        )
                        ui.label(
                            f'{len(confirmed["rows"]):,} productos listos para comparar.'
                        ).classes("text-sm text-green-900")
                        if confirmed["stock_policy"] == "review_all":
                            ui.label(
                                "Sin columna de stock: todos los productos "
                                "quedarán pendientes de revisión manual."
                            ).classes("text-sm text-amber-800")
                        else:
                            ui.label(
                                "Columna de stock detectada. Sus valores deberán "
                                "validarse antes de habilitar productos para exportación."
                            ).classes("text-sm text-green-900")
                ui.notify("Mapeo del proveedor confirmado", type="positive")

            def render_provider_mapping(inspection):
                provider_selectors.clear()
                provider_mapping_area.clear()
                provider_confirmation.clear()
                with provider_mapping_area:
                    ui.separator()
                    ui.label("2. Mapeo de columnas del proveedor").classes(
                        "text-lg font-semibold text-slate-900"
                    )
                    ui.label(
                        f'Perfil detectado: {inspection["profile"]}. '
                        "Revisá las sugerencias antes de confirmar."
                    ).classes("text-sm text-slate-600")
                    for field, label in PROVIDER_MAPPING_FIELDS:
                        provider_selectors[field] = ui.select(
                            options=inspection["headers"],
                            value=inspection["suggestions"].get(field),
                            label=label,
                            clearable=True,
                        ).classes("w-full")
                    ui.button(
                        "Confirmar mapeo del proveedor",
                        on_click=confirm_provider_mapping,
                        icon="check",
                    ).props("color=primary")

            async def handle_provider_upload(event):
                clear_provider()
                try:
                    file_bytes = event.content.read()
                    inspection = inspect_provider_file(file_bytes, event.name)
                except (UnicodeDecodeError, ValueError, TypeError) as exc:
                    provider_status.set_text(
                        f"No se pudo interpretar el archivo: {exc}"
                    )
                    provider_status.classes(replace="text-sm text-red-700")
                    ui.notify("No se pudo leer el CSV del proveedor", type="negative")
                    return

                state["provider_inspection"] = inspection
                provider_status.set_text("Archivo leído correctamente")
                provider_status.classes(
                    replace="text-sm text-green-700 font-semibold"
                )
                with provider_details:
                    with ui.row().classes("w-full flex-wrap gap-6"):
                        values = (
                            ("ARCHIVO", inspection["filename"]),
                            ("FILAS", f'{len(inspection["rows"]):,}'),
                            ("COLUMNAS", str(len(inspection["headers"]))),
                            (
                                "SEPARADOR",
                                "Tabulación"
                                if inspection["detected_delimiter"] == "\t"
                                else inspection["detected_delimiter"],
                            ),
                            ("PERFIL", inspection["profile"]),
                        )
                        for label, value in values:
                            with ui.column().classes("gap-0"):
                                ui.label(label).classes(
                                    "text-xs font-semibold text-slate-500"
                                )
                                ui.label(value).classes(
                                    "font-medium text-slate-900"
                                )
                    if inspection["ignored_empty_columns"]:
                        ui.label(
                            f'Se ignoraron {inspection["ignored_empty_columns"]} '
                            "columna(s) sin encabezado y completamente vacía(s)."
                        ).classes("text-sm text-amber-700")

                with provider_preview:
                    ui.label("Vista previa · Primeras 5 filas").classes(
                        "text-base font-semibold text-slate-900"
                    )
                    headers = inspection["headers"][:6]
                    rows = [
                        {header: row.get(header, "") for header in headers}
                        for row in inspection["rows"][:PREVIEW_LIMIT]
                    ]
                    if rows:
                        columns = [
                            {
                                "name": header,
                                "label": header,
                                "field": header,
                                "align": "left",
                            }
                            for header in headers
                        ]
                        ui.table(
                            columns=columns,
                            rows=rows,
                            row_key=headers[0],
                        ).classes("w-full")
                    else:
                        ui.label(
                            "El CSV contiene encabezados, pero no tiene productos."
                        ).classes("text-sm text-amber-700")
                render_provider_mapping(inspection)
                ui.notify("CSV del proveedor inspeccionado", type="positive")

            provider_upload.on_upload(handle_provider_upload)
            ui.button(
                "Quitar archivo del proveedor",
                on_click=clear_provider,
                icon="delete_outline",
            ).props("flat color=grey")

        with ui.card().classes("w-full p-6 gap-4"):
            ui.label("3. Exportación de WooCommerce").classes(
                "text-lg font-semibold text-slate-900"
            )
            ui.label(
                "Subí un CSV exportado desde Productos → Exportar en WooCommerce. "
                "Se usará como una fotografía de referencia, no como inventario completo."
            ).classes("text-sm text-slate-500")
            store_status = ui.label(
                "Esperando una exportación de WooCommerce…"
            ).classes("text-sm text-slate-600")
            store_details = ui.column().classes("w-full gap-3")
            store_mapping_area = ui.column().classes("w-full gap-3")
            store_confirmation = ui.column().classes("w-full gap-3")
            store_upload = ui.upload(
                label="Seleccionar exportación CSV de WooCommerce",
                auto_upload=True,
                max_file_size=MAX_UPLOAD_BYTES,
                max_files=1,
            ).props('accept=".csv"').classes("w-full")

            def confirm_store_mapping():
                if state["provider"] is None:
                    ui.notify(
                        "Primero cargá y confirmá el archivo del proveedor.",
                        type="warning",
                    )
                    return
                inspection = state["store_inspection"]
                if inspection is None:
                    return
                mapping = {
                    field: selector.value
                    for field, selector in store_selectors.items()
                }
                try:
                    confirmed = confirm_store_setup(
                        state["provider"], inspection, mapping
                    )
                except (TypeError, ValueError) as exc:
                    state["store"] = None
                    store_confirmation.clear()
                    ui.notify(str(exc), type="negative")
                    return

                state["store"] = confirmed
                store_confirmation.clear()
                summary = confirmed["summary"]
                with store_confirmation:
                    ui.separator()
                    ui.label("4. Resultado de la comparación").classes(
                        "text-lg font-semibold text-slate-900"
                    )
                    ui.label(
                        "Comparación por SKU entre el proveedor y esta exportación."
                    ).classes("text-sm text-slate-600")
                    with ui.grid(columns=2).classes("w-full gap-3"):
                        metrics = (
                            ("Candidatos nuevos", summary["new_candidates"]),
                            ("Ya existentes", summary["existing"]),
                            ("SKU duplicados en proveedor", summary["duplicate_supplier_sku"]),
                            ("SKU duplicados en exportación", summary["duplicate_store_sku"]),
                            ("SKU faltantes", summary["missing_supplier_sku"]),
                            ("Categorías observadas", summary["observed_categories"]),
                        )
                        for label, value in metrics:
                            with ui.card().classes("p-3 gap-1"):
                                ui.label(label).classes(
                                    "text-xs text-slate-500"
                                )
                                ui.label(f"{value:,}").classes(
                                    "text-2xl font-semibold text-slate-900"
                                )
                    ui.label(
                        f'Proveedor: {summary["supplier_rows"]:,} filas · '
                        f'WooCommerce: {summary["store_rows"]:,} filas'
                    ).classes("text-sm text-slate-600")
                    if confirmed["observed_categories"]:
                        ui.label("Categorías encontradas en la exportación").classes(
                            "font-semibold text-slate-800"
                        )
                        ui.label(
                            "Estas son categorías observadas en el archivo, "
                            "no necesariamente todas las categorías existentes en la tienda."
                        ).classes("text-xs text-slate-500")
                        ui.label(
                            "\n".join(confirmed["observed_categories"])
                        ).classes("text-sm text-slate-700 whitespace-pre-line")
                    else:
                        ui.label(
                            "No se detectaron categorías. Revisá si el archivo "
                            "incluye la columna Categories."
                        ).classes("text-sm text-amber-800")
                ui.notify("Comparación por SKU completada", type="positive")

            def render_store_mapping(inspection):
                store_selectors.clear()
                store_mapping_area.clear()
                store_confirmation.clear()
                with store_mapping_area:
                    ui.separator()
                    ui.label("Mapeo de columnas de WooCommerce").classes(
                        "text-lg font-semibold text-slate-900"
                    )
                    ui.label(
                        "Indicá qué columna contiene el SKU y, si está disponible, "
                        "la ruta de categorías."
                    ).classes("text-sm text-slate-600")
                    store_selectors["sku"] = ui.select(
                        options=inspection["headers"],
                        value=inspection["suggestions"].get("sku"),
                        label="SKU (obligatorio)",
                        clearable=True,
                    ).classes("w-full")
                    store_selectors["categories"] = ui.select(
                        options=inspection["headers"],
                        value=inspection["suggestions"].get("categories"),
                        label="Categories (opcional)",
                        clearable=True,
                    ).classes("w-full")
                    ui.button(
                        "Comparar catálogos",
                        on_click=confirm_store_mapping,
                        icon="compare_arrows",
                    ).props("color=primary")

            async def handle_store_upload(event):
                state["store_inspection"] = None
                state["store"] = None
                store_mapping_area.clear()
                store_confirmation.clear()
                if state["provider"] is None:
                    store_status.set_text(
                        "Primero confirmá el mapeo del proveedor."
                    )
                    store_status.classes(replace="text-sm text-amber-800")
                    ui.notify(
                        "Falta confirmar el archivo del proveedor.",
                        type="warning",
                    )
                    return
                try:
                    file_bytes = event.content.read()
                    inspection = inspect_store_file(file_bytes, event.name)
                except (UnicodeDecodeError, ValueError, TypeError) as exc:
                    store_status.set_text(
                        f"No se pudo interpretar la exportación: {exc}"
                    )
                    store_status.classes(replace="text-sm text-red-700")
                    ui.notify("No se pudo leer la exportación", type="negative")
                    return

                state["store_inspection"] = inspection
                store_status.set_text("Exportación leída correctamente")
                store_status.classes(
                    replace="text-sm text-green-700 font-semibold"
                )
                with store_details:
                    store_details.clear()
                    with ui.row().classes("w-full flex-wrap gap-6"):
                        values = (
                            ("ARCHIVO", inspection["filename"]),
                            ("FILAS", f'{inspection["row_count"]:,}'),
                            ("COLUMNAS", str(len(inspection["headers"]))),
                            ("SEPARADOR", inspection["detected_delimiter"]),
                        )
                        for label, value in values:
                            with ui.column().classes("gap-0"):
                                ui.label(label).classes(
                                    "text-xs font-semibold text-slate-500"
                                )
                                ui.label(value).classes(
                                    "font-medium text-slate-900"
                                )
                    if inspection["ignored_empty_columns"]:
                        ui.label(
                            f'Se ignoraron {inspection["ignored_empty_columns"]} '
                            "columna(s) vacía(s) sin encabezado."
                        ).classes("text-sm text-amber-700")
                render_store_mapping(inspection)
                ui.notify("Exportación de WooCommerce inspeccionada", type="positive")

            store_upload.on_upload(handle_store_upload)
            ui.button(
                "Quitar exportación de WooCommerce",
                on_click=clear_store,
                icon="delete_outline",
            ).props("flat color=grey")

        with ui.row().classes("w-full justify-between items-center"):
            ui.label("MVP · Procesamiento local · Sin escritura en WooCommerce").classes(
                "text-xs text-slate-500"
            )
            ui.label("Etapa 3: comparación por SKU").classes(
                "text-xs font-medium text-slate-600"
            )


def run_app():
    """Start the local NiceGUI application in a desktop webview."""
    build_ui()
    ui.run(
        title="WooCommerce Catalog Toolkit",
        native=True,
        window_size=(1280, 860),
        reload=False,
        show=False,
    )


if __name__ == "__main__":
    run_app()
