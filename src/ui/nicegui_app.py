"""NiceGUI interface for preparing WooCommerce catalog imports."""

from nicegui import ui

from src.application.provider_setup import (
    confirm_provider_setup,
    inspect_provider_file,
)


MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PREVIEW_LIMIT = 5
MAPPING_FIELDS = (
    ("sku", "SKU / Código", True),
    ("name", "Nombre del producto", True),
    ("category", "Categoría", True),
    ("price", "Precio (con IVA)", True),
    ("stock", "Stock (opcional)", False),
)


def build_ui():
    """Build the supplier inspection and column-mapping workflow."""
    state = {"inspection": None, "confirmed": None}
    selectors = {}

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
                "Prepará el catálogo del proveedor para una futura importación. "
                "En esta etapa no se modifica WooCommerce."
            ).classes("text-slate-600")

        with ui.card().classes("w-full p-6 gap-4"):
            ui.label("1. Archivo del proveedor").classes(
                "text-lg font-semibold text-slate-900"
            )
            ui.label(
                "Formato CSV UTF-8 · Máximo 50 MB · Procesamiento local"
            ).classes("text-sm text-slate-500")

            status = ui.label("Esperando un archivo CSV…").classes(
                "text-sm text-slate-600"
            )
            details = ui.column().classes("w-full gap-3")
            preview_area = ui.column().classes("w-full gap-2")
            mapping_area = ui.column().classes("w-full gap-3")
            confirmation_area = ui.column().classes("w-full gap-2")

            def clear_inspection():
                state["inspection"] = None
                state["confirmed"] = None
                selectors.clear()
                details.clear()
                preview_area.clear()
                mapping_area.clear()
                confirmation_area.clear()
                status.set_text("Esperando un archivo CSV…")
                status.classes(replace="text-sm text-slate-600")

            def confirm_mapping():
                inspection = state["inspection"]
                if inspection is None:
                    return

                mapping = {
                    field: selector.value
                    for field, selector in selectors.items()
                }
                try:
                    confirmed = confirm_provider_setup(inspection, mapping)
                except (TypeError, ValueError) as exc:
                    state["confirmed"] = None
                    confirmation_area.clear()
                    ui.notify(str(exc), type="negative")
                    return

                state["confirmed"] = confirmed
                confirmation_area.clear()
                with confirmation_area:
                    with ui.card().classes("w-full bg-green-50 border border-green-200"):
                        ui.label("Configuración del proveedor confirmada").classes(
                            "font-semibold text-green-800"
                        )
                        ui.label(
                            f'{len(confirmed["rows"]):,} productos listos para la siguiente etapa.'
                        ).classes("text-sm text-green-900")
                        if confirmed["stock_policy"] == "review_all":
                            ui.label(
                                "No se asignó una columna de stock: todos los productos "
                                "quedarán pendientes de revisión manual."
                            ).classes("text-sm text-amber-800")
                        else:
                            ui.label(
                                "Se detectó una columna de stock. Sus valores deberán "
                                "validarse antes de habilitar productos para exportación."
                            ).classes("text-sm text-green-900")
                ui.notify("Mapeo confirmado correctamente", type="positive")

            def render_mapping(inspection):
                selectors.clear()
                mapping_area.clear()
                confirmation_area.clear()
                with mapping_area:
                    ui.separator()
                    ui.label("2. Mapeo de columnas").classes(
                        "text-lg font-semibold text-slate-900"
                    )
                    ui.label(
                        f'Perfil detectado: {inspection["profile"]}. '
                        "Revisá las sugerencias antes de confirmar."
                    ).classes("text-sm text-slate-600")

                    for field, label, required in MAPPING_FIELDS:
                        suggestion = inspection["suggestions"].get(field)
                        field_label = label if required else label
                        selectors[field] = ui.select(
                            options=inspection["headers"],
                            value=suggestion,
                            label=field_label,
                            clearable=True,
                        ).classes("w-full")

                    ui.button(
                        "Confirmar mapeo",
                        on_click=confirm_mapping,
                        icon="check",
                    ).props("color=primary")

            def handle_upload(event):
                clear_inspection()
                try:
                    file_bytes = event.content.read()
                    inspection = inspect_provider_file(file_bytes, event.name)
                except (UnicodeDecodeError, ValueError, TypeError) as exc:
                    status.set_text(f"No se pudo interpretar el archivo: {exc}")
                    status.classes(replace="text-sm text-red-700")
                    ui.notify("No se pudo leer el CSV", type="negative")
                    return

                state["inspection"] = inspection
                status.set_text("Archivo leído correctamente")
                status.classes(replace="text-sm text-green-700 font-semibold")

                with details:
                    with ui.row().classes("w-full flex-wrap gap-6"):
                        for label, value in (
                            ("ARCHIVO", inspection["filename"]),
                            ("FILAS", f'{len(inspection["rows"]):,}'),
                            ("COLUMNAS", str(len(inspection["headers"]))),
                            (
                                "SEPARADOR DETECTADO",
                                "Tabulación"
                                if inspection["detected_delimiter"] == "\t"
                                else inspection["detected_delimiter"],
                            ),
                            ("PERFIL", inspection["profile"]),
                        ):
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

                with preview_area:
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
                            "El CSV contiene encabezados, pero no tiene filas de productos."
                        ).classes("text-sm text-amber-700")

                render_mapping(inspection)
                ui.notify("CSV inspeccionado correctamente", type="positive")

            ui.upload(
                label="Seleccionar archivo CSV",
                auto_upload=True,
                on_upload=handle_upload,
                max_file_size=MAX_UPLOAD_BYTES,
                max_files=1,
            ).props('accept=".csv"').classes("w-full")

            ui.button(
                "Quitar archivo",
                on_click=clear_inspection,
                icon="delete_outline",
            ).props("flat color=grey")

        with ui.row().classes("w-full justify-between items-center"):
            ui.label("MVP · Sin conexión ni escritura en WooCommerce").classes(
                "text-xs text-slate-500"
            )
            ui.label("Etapa 2: configuración del proveedor").classes(
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
