"""NiceGUI interface for preparing WooCommerce catalog imports."""

from nicegui import ui
from decimal import Decimal, InvalidOperation

from src.application.provider_setup import (
    confirm_provider_setup,
    inspect_provider_file,
)
from src.application.store_setup import (
    confirm_store_setup,
    inspect_store_file,
)
from src.application.catalog_preparation import prepare_catalog
from src.application.catalog_exports import make_dict_rows_csv
from src.application.woocommerce_categories import (
    suggest_destination_categories,
)
from src.operations.add_products import prepare_add_products
from src.operations.select_products import normalize_category
from src.application.product_selection import set_product_selection
from src.operations.common import BLOCKED, EXCLUDED, READY, REVIEW


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
        "store_mode": "not_decided",
        "preparation": None,
        "selection_result": None,
        "selection_category_mappings": {},
        "selection_state": {},
        "selection_confirmations": {},
    }
    provider_selectors = {}
    store_selectors = {}
    step_panels = {}
    step_buttons = {}
    step_labels = {
        "files": "Archivos",
        "validation": "Validación",
        "selection": "Selección",
        "export": "Exportación",
    }

    def go_to_step(step):
        if step not in step_labels:
            return
        if step != "files" and state["provider"] is None:
            ui.notify("Primero cargá y confirmá el archivo del proveedor.", type="warning")
            return
        if step in ("selection", "export") and state["preparation"] is None:
            ui.notify("Primero ejecutá la validación del catálogo.", type="warning")
            return
        if step == "export" and state["selection_result"] is None:
            ui.notify("Primero revisá la selección de productos.", type="warning")
            return
        for key, panel in step_panels.items():
            panel.set_visibility(key == step)
        for key, button in step_buttons.items():
            button.props("color=primary" if key == step else "color=grey")
        step_status.set_text(f'Etapa actual: {step_labels[step]}')

    ui.add_head_html("""<style>
         .catalog-upload .q-uploader__list,
        .catalog-upload .q-uploader__progress { display: none !important; }
    </style>""")

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

        with ui.row().classes("w-full flex-wrap items-center gap-2"):
            for step_key, step_label in step_labels.items():
                step_buttons[step_key] = ui.button(
                    step_label,
                    on_click=lambda key=step_key: go_to_step(key),
                ).props("outline color=grey")
            step_status = ui.label("Etapa actual: Archivos").classes(
                "text-sm text-slate-500"
            )

        with ui.column() as files_panel:
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
                    ).props('accept=".csv" hide-upload-progress').classes("w-full catalog-upload")

                def clear_store(*, reset_upload=True):
                    if reset_upload:
                        store_upload.reset()
                    state["store_inspection"] = None
                    state["store"] = None
                    state["store_mode"] = "not_decided" if state["provider"] else "empty"
                    state["preparation"] = None
                    state["selection_result"] = None
                    state["selection_category_mappings"] = {}
                    state["selection_confirmations"] = {}
                    store_selectors.clear()
                    preparation_results.clear()
                    category_selection_area.clear()
                    comparison_summary_area.clear()
                    export_area.clear()
                    prepare_button.disable()
                    continue_to_selection_button.disable()
                    if state["provider"] is not None:
                        continue_without_store_button.enable()
                    else:
                        continue_without_store_button.disable()
                    preparation_status.set_text(
                        "Elegí si vas a comparar con WooCommerce o continuar sin esa referencia."
                    )
                    store_status.set_text(
                        "Exportación opcional. Si la tienda ya tiene productos, cargá su exportación para detectar SKU existentes."
                        if state["provider"] else "Primero cargá y confirmá el mapeo del proveedor."
                    )
                    store_status.classes(replace="text-sm text-slate-600")
                    store_details.clear()
                    store_mapping_area.clear()
                    comparison_summary_area.clear()

                def clear_provider(*, reset_upload=True):
                    if reset_upload:
                        provider_upload.reset()
                    state["provider_inspection"] = None
                    state["provider"] = None
                    state["selection_state"] = {}
                    state["selection_category_mappings"] = {}
                    state["selection_confirmations"] = {}
                    provider_selectors.clear()
                    provider_details.clear()
                    provider_preview.clear()
                    provider_mapping_area.clear()
                    provider_confirmation.clear()
                    provider_status.set_text("Esperando un archivo CSV…")
                    provider_status.classes(replace="text-sm text-slate-600")
                    clear_store()
                    store_upload.disable()
                    continue_without_store_button.disable()
                    prepare_button.disable()
                    store_status.set_text("Primero cargá y confirmá el mapeo del proveedor.")

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
                    store_upload.enable()
                    continue_without_store_button.enable()
                    prepare_button.disable()
                    store_status.set_text(
                        "Proveedor confirmado. Podés cargar WooCommerce o continuar sin ese archivo."
                    )
                    store_status.classes(replace="text-sm text-blue-700 font-semibold")
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
                    clear_provider(reset_upload=False)
                    try:
                        file_bytes = event.content.read()
                        provider_upload.reset()
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
                store_upload = ui.upload(
                    label="Seleccionar exportación CSV de WooCommerce",
                    auto_upload=True,
                    max_file_size=MAX_UPLOAD_BYTES,
                    max_files=1,
                ).props('accept=".csv" hide-upload-progress').classes("w-full catalog-upload")
                store_upload.disable()
                continue_without_store_button = ui.button(
                    "Continuar sin exportación WooCommerce",
                    on_click=lambda: continue_without_store(),
                    icon="skip_next",
                ).props("outline color=secondary")
                continue_without_store_button.disable()
                store_status.set_text("Primero cargá y confirmá el mapeo del proveedor.")

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
                        comparison_summary_area.clear()
                        ui.notify(str(exc), type="negative")
                        return

                    state["store"] = confirmed
                    state["store_mode"] = "reference"
                    prepare_button.enable()
                    continue_without_store_button.disable()
                    comparison_summary_area.clear()
                    summary = confirmed["summary"]
                    with comparison_summary_area:
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
                    go_to_step("validation")

                def render_store_mapping(inspection):
                    store_selectors.clear()
                    store_mapping_area.clear()
                    comparison_summary_area.clear()
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
                    state["store_mode"] = "reading"
                    state["preparation"] = None
                    state["selection_result"] = None
                    state["selection_category_mappings"] = {}
                    state["selection_confirmations"] = {}
                    prepare_button.disable()
                    continue_to_selection_button.disable()
                    continue_without_store_button.disable()
                    preparation_results.clear()
                    category_selection_area.clear()
                    comparison_summary_area.clear()
                    export_area.clear()
                    preparation_status.set_text(
                        "Confirmá el mapeo de WooCommerce para usar esta exportación como referencia."
                    )
                    store_mapping_area.clear()
                    comparison_summary_area.clear()
                    store_details.clear()
                    try:
                        file_bytes = event.content.read()
                        store_upload.reset()
                        inspection = inspect_store_file(file_bytes, event.name)
                    except (UnicodeDecodeError, ValueError, TypeError) as exc:
                        state["store_mode"] = "invalid"
                        store_status.set_text(
                            f"No se pudo interpretar la exportación: {exc}. "
                            "La comparación está bloqueada. Reemplazá el archivo o quitálo "
                            "y elegí continuar sin referencia."
                        )
                        store_status.classes(replace="text-sm text-red-700")
                        with store_details:
                            ui.label(f"Archivo rechazado: {event.name}").classes(
                                "text-sm font-medium text-slate-800"
                            )
                        ui.notify("No se pudo leer la exportación; preparación bloqueada", type="negative")
                        return

                    state["store_inspection"] = inspection
                    state["store_mode"] = "inspected"
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

                def continue_without_store():
                    clear_store()
                    state["store_mode"] = "without_reference"
                    prepare_button.enable()
                    continue_without_store_button.disable()
                    store_status.set_text(
                        "Continuarás sin comparar SKU existentes. La preparación no podrá confirmar si los productos ya están en la tienda."
                    )
                    store_status.classes(replace="text-sm text-amber-800 font-semibold")
                    preparation_status.set_text(
                        "Referencia WooCommerce omitida explícitamente. Ya podés preparar las altas."
                    )
                    ui.notify("Se continuará sin referencia WooCommerce", type="warning")
                    go_to_step("validation")

        def prepare_addition():
            category_selection_area.clear()
            state["selection_result"] = None
            provider = state["provider"]
            if provider is None:
                ui.notify("Primero confirmá el mapeo del proveedor.", type="warning")
                return

            if state["store_mode"] not in ("reference", "without_reference"):
                ui.notify(
                    "Resolvé primero el estado de la exportación WooCommerce o elegí continuar sin ella.",
                    type="warning",
                )
                return

            if state["store_inspection"] is not None and state["store"] is None:
                ui.notify(
                    "La exportación de WooCommerce está cargada, pero falta confirmar su mapeo.",
                    type="warning",
                )
                return

            store = state["store"]
            catalog_rows = store["rows"] if store else []
            catalog_sku_column = store["mapping"]["sku"] if store else "SKU"
            mapping = provider["mapping"]
            try:
                result = prepare_add_products(
                    provider["rows"],
                    catalog_rows,
                    supplier_sku_column=mapping["sku"],
                    catalog_sku_column=catalog_sku_column,
                    name_column=mapping["name"],
                    price_column=mapping["price"],
                    stock_column=mapping.get("stock"),
                    require_positive_stock=True,
                )
            except (KeyError, TypeError, ValueError) as exc:
                state["preparation"] = None
                preparation_results.clear()
                preparation_status.set_text(f"No se pudo preparar el catálogo: {exc}")
                preparation_status.classes(replace="text-sm text-red-700")
                ui.notify("Falló la preparación de altas", type="negative")
                return

            state["preparation"] = result
            preparation_results.clear()
            counts = {
                READY: len(result[READY]),
                REVIEW: len(result[REVIEW]),
                BLOCKED: len(result[BLOCKED]),
                EXCLUDED: len(result[EXCLUDED]),
            }
            status_labels = {
                READY: "Elegible",
                REVIEW: "En revisión",
                BLOCKED: "Bloqueado",
                EXCLUDED: "Ya existe en WooCommerce",
            }
            status_styles = {
                READY: "text-green-700",
                REVIEW: "text-amber-700",
                BLOCKED: "text-red-700",
                EXCLUDED: "text-slate-600",
            }
            all_items = sorted(
                (
                    item
                    for status in (READY, REVIEW, BLOCKED, EXCLUDED)
                    for item in result[status]
                ),
                key=lambda item: item["row_number"],
            )
            rows = []
            for item in all_items:
                source = item["row"]
                rows.append({
                    "row_number": item["row_number"],
                    "sku": str(item["sku"] or ""),
                    "name": str(source.get(mapping["name"], "") or ""),
                    "price": str(source.get(mapping["price"], "") or ""),
                    "stock": str(source.get(mapping.get("stock"), "") or "")
                    if mapping.get("stock") else "No informado",
                    "status": status_labels[item["status"]],
                    "reason": item["reason"],
                })
            with preparation_results:
                ui.separator()
                ui.label("Resultado de la preparación").classes(
                    "text-lg font-semibold text-slate-900"
                )
                ui.label(
                    "Cada fila del proveedor queda clasificada técnicamente. "
                    "La selección comercial se realiza por separado."
                ).classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-3"):
                    for status in (READY, REVIEW, BLOCKED, EXCLUDED):
                        with ui.card().classes("p-3 gap-1"):
                            ui.label(status_labels[status]).classes("text-xs text-slate-500")
                            ui.label(f"{counts[status]:,}").classes(
                                f"text-2xl font-semibold {status_styles[status]}"
                            )
                ui.label(
                    f"Total: {len(all_items):,} filas · "
                    f"Proveedor: {len(provider['rows']):,} productos · "
                    f"WooCommerce: {len(catalog_rows):,} productos de referencia"
                ).classes("text-sm font-medium text-slate-700")
                if store is None:
                    ui.label(
                        "Sin exportación WooCommerce no se verificaron SKU existentes "
                        "ni categorías de destino."
                    ).classes("text-sm text-amber-800")
                with ui.expansion(
                    "Inspeccionar productos y motivos de validación",
                    icon="table_view",
                ):
                    ui.table(
                        columns=[
                            {"name": "row_number", "label": "Fila", "field": "row_number", "align": "left"},
                            {"name": "sku", "label": "SKU", "field": "sku", "align": "left"},
                            {"name": "name", "label": "Producto", "field": "name", "align": "left"},
                            {"name": "price", "label": "Precio", "field": "price", "align": "left"},
                            {"name": "stock", "label": "Stock", "field": "stock", "align": "left"},
                            {"name": "status", "label": "Clasificación", "field": "status", "align": "left"},
                            {"name": "reason", "label": "Motivo", "field": "reason", "align": "left"},
                        ],
                        rows=rows,
                        row_key="row_number",
                        pagination=20,
                    ).classes("w-full")
            preparation_status.set_text("Preparación de altas completada.")
            preparation_status.classes(replace="text-sm text-green-700 font-semibold")
            ui.notify("Validación del catálogo completada", type="positive")
            continue_to_selection_button.enable()
            go_to_step("validation")

        def render_category_selection():
            """Render category destinations and individual product selection."""
            category_selection_area.clear()
            category_controls.clear()
            provider = state["provider"]
            if provider is None:
                return

            mapping = provider["mapping"]
            category_column = mapping["category"]
            categories_by_key = {}
            products_by_category = {}
            for row_number, row in enumerate(provider["rows"], start=2):
                category = str(row.get(category_column, "") or "").strip()
                key = normalize_category(category)
                if not key:
                    key = "__sin_categoria__"
                    category = "Sin categoría"
                categories_by_key.setdefault(key, category)
                products_by_category.setdefault(key, []).append(
                    {"row_number": row_number, "row": row}
                )

            categories = sorted(
                categories_by_key.items(),
                key=lambda pair: pair[1].casefold(),
            )
            store = state["store"]
            destinations = store["observed_categories"] if store else []
            suggestions = suggest_destination_categories(
                [category for _, category in categories],
                destinations,
            ) if destinations else {}

            def build_result():
                current_store = state["store"]
                catalog_rows = current_store["rows"] if current_store else []
                catalog_sku_column = (
                    current_store["mapping"]["sku"] if current_store else "SKU"
                )
                current_mapping = state["provider"]["mapping"]
                return prepare_catalog(
                    state["provider"]["rows"],
                    catalog_rows,
                    selection_config={
                        "category_column": current_mapping["category"],
                        "stock_column": current_mapping.get("stock"),
                        "category_mappings": state["selection_category_mappings"],
                    },
                    supplier_columns={
                        "sku": current_mapping["sku"],
                        "name": current_mapping["name"],
                        "price": current_mapping["price"],
                        "catalog_sku": catalog_sku_column,
                    },
                    selection_state=state["selection_state"],
                )

            def refresh_result():
                try:
                    result = build_result()
                except (KeyError, TypeError, ValueError) as exc:
                    ui.notify(f"No se pudo actualizar la selección: {exc}", type="negative")
                    return
                state["selection_result"] = result
                state["selection_state"] = dict(result["selection_state"])
                summary = result["summary"]
                summary_labels["selected"].set_text(f'{summary["selected"]:,}')
                summary_labels["exportable"].set_text(f'{summary["exportable"]:,}')
                summary_labels["not_selected"].set_text(f'{summary["ready_not_selected"]:,}')
                summary_labels["review"].set_text(f'{summary["review"]:,}')
                summary_labels["blocked"].set_text(f'{summary["blocked"]:,}')
                summary_labels["existing"].set_text(f'{summary["excluded_existing"]:,}')
                for category_key, count_label in category_count_labels.items():
                    selected_count = sum(
                        1 for product in products_by_category[category_key]
                        if state["selection_state"].get(product["row_number"]) == "SELECTED"
                    )
                    count_label.set_text(
                        f'{len(products_by_category[category_key]):,} productos · '
                        f'{selected_count:,} seleccionados'
                    )
                update_export_area(result)

            def update_export_area(result):
                export_area.clear()
                with export_area:
                    if result["export_rows"]:
                        export_fields = [
                            "SKU", "Name", "Regular price", "Published", "Type", "Categories"
                        ]
                        csv_content = make_dict_rows_csv(
                            result["export_rows"], export_fields
                        )
                        ui.button(
                            "Descargar CSV de altas",
                            on_click=lambda data=csv_content: ui.download(
                                data, "woocommerce-altas.csv"
                            ),
                            icon="download",
                        ).props("color=primary")
                        ui.label(
                            "Solo incluye productos seleccionados, técnicamente elegibles "
                            "y con destino WooCommerce confirmado."
                        ).classes("text-sm text-green-700")
                    else:
                        ui.label(
                            "Todavía no hay productos listos para exportar. "
                            "Seleccioná productos elegibles y confirmá el destino de sus categorías."
                        ).classes("text-sm text-amber-800")

            result = build_result()
            state["selection_result"] = result
            state["selection_state"] = dict(result["selection_state"])
            summary_labels = {}
            category_controls.clear()

            with category_selection_area:
                ui.separator()
                ui.label("Elegí qué productos incorporar").classes(
                    "text-lg font-semibold text-slate-900"
                )
                ui.label(
                    "Solo podés seleccionar productos técnicamente elegibles. "
                    "El destino WooCommerce se confirma por separado."
                ).classes("text-sm text-slate-600")
                with ui.grid(columns=3).classes("w-full gap-3"):
                    summary_cards = (
                        ("selected", "Seleccionados"),
                        ("exportable", "Listos para exportar"),
                        ("not_selected", "Elegibles sin seleccionar"),
                        ("review", "En revisión"),
                        ("blocked", "Bloqueados"),
                        ("existing", "Ya existentes"),
                    )
                    for key, label in summary_cards:
                        with ui.card().classes("p-3 gap-1"):
                            ui.label(label).classes("text-xs text-slate-500")
                            summary_labels[key] = ui.label("0").classes(
                                "text-2xl font-semibold text-slate-900"
                            )

                ui.label(
                    "Buscá por nombre o SKU. El precio se muestra en cada producto. "
                    "Abrí una categoría para revisar sus artículos y configurar el destino."
                ).classes("text-sm text-slate-600")
                category_filter = ui.input(
                    label="Buscar productos o categorías",
                    placeholder="Nombre del producto o SKU…",
                ).props("clearable").classes("w-full")

                if not destinations:
                    ui.label(
                        "No hay categorías de destino verificadas. Podés seleccionar "
                        "productos, pero no se generará un CSV hasta cargar una "
                        "exportación WooCommerce con categorías de destino."
                    ).classes("text-sm text-amber-800")

                category_panels = {}
                category_expansions = {}
                category_product_rows = {}
                category_count_labels = {}
                with ui.element("div").classes(
                    "grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 w-full"
                ):
                    for key, category in categories:
                        category_products = products_by_category[key]
                        category_items = {
                            item["row_number"]: item
                            for item in result["selection"]["items"]
                        }
                        suggestion = suggestions.get(key, {
                            "status": "unmatched",
                            "destination": None,
                            "match_type": None,
                        })
                        suggested_destination = suggestion["destination"]
                        confirmed_value = state["selection_confirmations"].get(key)
                        destination_value = state["selection_category_mappings"].get(key)
                        if destination_value not in destinations:
                            destination_value = suggested_destination

                        with ui.card().classes("w-full min-w-0 p-3 gap-2") as category_card:
                            ui.label(category).classes("font-semibold text-slate-900")
                            selected_in_category = sum(
                                1 for product in category_products
                                if state["selection_state"].get(product["row_number"]) == "SELECTED"
                            )
                            category_count_labels[key] = ui.label(
                                f"{len(category_products):,} productos · "
                                f"{selected_in_category:,} seleccionados"
                            ).classes("text-xs text-slate-500")
                            with ui.expansion(
                                "Ver productos y configurar destino",
                                icon="category",
                                value=False,
                            ).classes("w-full border border-slate-200 rounded-lg") as panel:
                                destination = ui.select(
                                    options=destinations,
                                    value=destination_value,
                                    label="Categoría de destino en WooCommerce",
                                    clearable=True,
                                ).classes("w-full")
    
                                accepted_destination = {"value": confirmed_value}
                                accepted_control = {"value": None}
                                if suggestion["status"] == "suggested":
                                    match_label = (
                                        "Coincidencia exacta de ruta"
                                        if suggestion["match_type"] == "exact_path"
                                        else "Coincidencia única por nombre"
                                    )
                                    ui.label(
                                        f"Sugerencia: {suggested_destination} · {match_label}"
                                    ).classes("text-sm text-blue-700")
                                    accepted = ui.checkbox(
                                        "Confirmo el destino sugerido",
                                        value=confirmed_value == suggested_destination,
                                    )
                                    accepted_control["value"] = accepted
                                    def on_accept_suggestion(
                                        event, category_key=key,
                                        accepted_state=accepted_destination,
                                        destination_selector=destination,
                                    ):
                                        value = (
                                            destination_selector.value
                                            if event.value else None
                                        )
                                        accepted_state["value"] = value
                                        if value:
                                            state["selection_confirmations"][category_key] = value
                                            state["selection_category_mappings"][category_key] = value
                                        else:
                                            state["selection_confirmations"].pop(category_key, None)
                                            state["selection_category_mappings"].pop(category_key, None)
                                        refresh_result()
    
                                    accepted.on_value_change(on_accept_suggestion)
                                elif suggestion["status"] == "ambiguous":
                                    ui.label(
                                        "Hay varias coincidencias posibles. Elegí el destino "
                                        "correcto manualmente."
                                    ).classes("text-sm text-amber-800")
                                else:
                                    ui.label(
                                        "No hay una sugerencia confiable. Elegí el destino "
                                        "manualmente."
                                    ).classes("text-sm text-amber-800")
    
                                def on_destination_change(
                                    event, category_key=key,
                                    suggestion_data=suggestion,
                                    accepted_state=accepted_destination,
                                    confirmation_control=accepted_control,
                                ):
                                    selected_destination = event.value
                                    state["selection_confirmations"].pop(category_key, None)
                                    accepted_state["value"] = None
                                    if confirmation_control["value"] is not None:
                                        confirmation_control["value"].set_value(False)
                                    if selected_destination:
                                        if (
                                            suggestion_data["status"] != "suggested"
                                            or selected_destination != suggestion_data["destination"]
                                        ):
                                            state["selection_category_mappings"][category_key] = selected_destination
                                        else:
                                            state["selection_category_mappings"].pop(category_key, None)
                                    else:
                                        state["selection_category_mappings"].pop(category_key, None)
                                    refresh_result()
    
                                destination.on_value_change(on_destination_change)
                                category_controls[key] = {
                                    "destination": destination,
                                    "suggestion": suggestion,
                                }
    
                                ui.separator()
                                eligible_products = []
                                other_products = []
                                for product in category_products:
                                    item = category_items[product["row_number"]]
                                    if item["technical_status"] == READY:
                                        eligible_products.append((product, item))
                                    else:
                                        other_products.append((product, item))
    
                                def price_sort_value(pair):
                                    raw = str(pair[0]["row"].get(mapping["price"], "") or "")
                                    normalized = raw.strip().replace(" ", "")
                                    if "," in normalized and "." in normalized:
                                        normalized = normalized.replace(".", "").replace(",", ".")
                                    elif "," in normalized:
                                        normalized = normalized.replace(",", ".")
                                    try:
                                        return (0, Decimal(normalized))
                                    except (InvalidOperation, ValueError):
                                        return (1, Decimal("0"))
    
                                eligible_products.sort(key=price_sort_value)
                                if eligible_products:
                                    ui.label(
                                        f"Productos elegibles · {len(eligible_products):,}"
                                    ).classes("text-sm font-semibold text-slate-700")
                                    for product, item in eligible_products:
                                        row = product["row"]
                                        row_number = product["row_number"]
                                        sku = str(row.get(mapping["sku"], "") or "Sin SKU")
                                        name = str(row.get(mapping["name"], "") or "Sin nombre")
                                        price = str(row.get(mapping["price"], "") or "Sin precio")
                                        selected = state["selection_state"].get(row_number) == "SELECTED"
                                        with ui.row().classes(
                                            "w-full items-center justify-between gap-3 py-2 border-b border-slate-100"
                                        ) as product_row_ui:
                                            with ui.column().classes("min-w-0 flex-grow gap-0"):
                                                checkbox = ui.checkbox(
                                                    name,
                                                    value=selected,
                                                ).classes("font-medium")
                                                ui.label(f"SKU: {sku}").classes(
                                                    "text-xs text-slate-500 pl-7"
                                                )
                                            ui.label(format_catalog_price(price)).classes(
                                                "font-semibold text-slate-800 whitespace-nowrap"
                                            )
                                            def on_product_selection(
                                                event, source_row=row_number
                                            ):
                                                eligible_rows = {
                                                    candidate["row_number"]
                                                    for status in (READY,)
                                                    for candidate in state["selection_result"]["add_products"][status]
                                                }
                                                try:
                                                    state["selection_state"] = set_product_selection(
                                                        state["selection_state"],
                                                        source_row,
                                                        selected=bool(event.value),
                                                        eligible_row_numbers=eligible_rows,
                                                    )
                                                except (KeyError, TypeError, ValueError) as exc:
                                                    ui.notify(str(exc), type="warning")
                                                    return
                                                refresh_result()
    
                                            checkbox.on_value_change(on_product_selection)
                                            category_product_rows.setdefault(key, []).append((
                                                normalize_category(f"{name} {sku}"), product_row_ui
                                            ))
                                else:
                                    ui.label(
                                        "No hay productos técnicamente elegibles en esta categoría."
                                    ).classes("text-sm text-slate-500")
    
                                if other_products:
                                    ui.separator()
                                    ui.label(
                                        f"No seleccionables · {len(other_products):,}"
                                    ).classes("text-sm font-semibold text-slate-500")
                                    for product, item in other_products:
                                        row = product["row"]
                                        sku = str(row.get(mapping["sku"], "") or "Sin SKU")
                                        name = str(row.get(mapping["name"], "") or "Sin nombre")
                                        with ui.row().classes(
                                            "w-full items-start justify-between gap-3 py-2 border-b border-slate-100"
                                        ) as product_row_ui:
                                            with ui.column().classes("min-w-0 flex-grow gap-0"):
                                                ui.label(name).classes("text-sm text-slate-700")
                                                ui.label(f"SKU: {sku}").classes("text-xs text-slate-500")
                                                ui.label(
                                                    f'{item["technical_status"]} · {item["reason"]}'
                                                ).classes("text-xs text-slate-500")
                                            ui.label(format_catalog_price(
                                                str(row.get(mapping["price"], "") or "")
                                            )).classes("text-sm text-slate-500 whitespace-nowrap")
                                        category_product_rows.setdefault(key, []).append((
                                            normalize_category(f"{name} {sku}"), product_row_ui
                                        ))
    
                        category_panels[key] = category_card
                        category_expansions[key] = panel

                def filter_categories(event):
                    query = normalize_category(event.value)
                    for key, panel in category_panels.items():
                        category_matches = (
                            not query
                            or query in key
                            or query in normalize_category(categories_by_key[key])
                        )
                        matching_products = 0
                        for searchable_text, product_row in category_product_rows.get(key, []):
                            product_matches = not query or query in searchable_text
                            visible = category_matches or product_matches
                            product_row.set_visibility(visible)
                            matching_products += int(visible)
                        panel.set_visibility(category_matches or matching_products > 0)
                        if query and not category_matches and matching_products:
                            category_expansions[key].set_value(True)

                category_filter.on_value_change(filter_categories)
                update_export_area(result)

            for key, controls in category_controls.items():
                suggestion = controls["suggestion"]
                destination = controls["destination"].value
                if not destination:
                    continue
                if (
                    suggestion["status"] == "suggested"
                    and destination == suggestion["destination"]
                    and state["selection_confirmations"].get(key) != destination
                ):
                    continue
                state["selection_category_mappings"][key] = destination

            refresh_result()

        def continue_to_selection():
            if state["preparation"] is None:
                ui.notify("Primero validá el catálogo.", type="warning")
                return
            render_category_selection()
            go_to_step("selection")

        with ui.column() as validation_panel:
            with ui.card().classes("w-full p-6 gap-4"):
                ui.label("2. Validación del catálogo").classes(
                    "text-xl font-semibold text-slate-900"
                )
                ui.label(
                    "Revisamos SKU, datos obligatorios, precio y stock. "
                    "Esta etapa no selecciona ni publica productos."
                ).classes("text-sm text-slate-600")
                comparison_summary_area = ui.column().classes("w-full gap-3")
                preparation_status = ui.label(
                    "Cargá los archivos y confirmá sus columnas para comenzar."
                ).classes("text-sm text-slate-600")
                prepare_button = ui.button(
                    "Validar catálogo",
                    on_click=prepare_addition,
                    icon="fact_check",
                ).props("color=primary")
                prepare_button.disable()
                preparation_results = ui.column().classes("w-full gap-3")
                continue_to_selection_button = ui.button(
                    "Continuar a selección de productos",
                    on_click=continue_to_selection,
                    icon="arrow_forward",
                ).props("color=primary")
                continue_to_selection_button.disable()

        with ui.column() as selection_panel:
            with ui.card().classes("w-full p-6 gap-4"):
                ui.label("3. Selección de productos").classes(
                    "text-xl font-semibold text-slate-900"
                )
                ui.label(
                    "Elegí individualmente los productos que querés incorporar. "
                    "Todos comienzan sin seleccionar."
                ).classes("text-sm text-slate-600")
                category_selection_area = ui.column().classes("w-full gap-3")
                category_controls = {}
                ui.button(
                    "Continuar a exportación",
                    on_click=lambda: go_to_step("export"),
                    icon="arrow_forward",
                ).props("color=primary")

        with ui.column() as export_panel:
            with ui.card().classes("w-full p-6 gap-4"):
                ui.label("4. Revisión y exportación").classes(
                    "text-xl font-semibold text-slate-900"
                )
                ui.label(
                    "Revisá el resultado final y descargá el CSV de altas. "
                    "La tienda no se modifica."
                ).classes("text-sm text-slate-600")
                export_area = ui.column().classes("w-full gap-3")
                ui.button(
                    "Volver a selección",
                    on_click=lambda: go_to_step("selection"),
                    icon="arrow_back",
                ).props("outline color=secondary")

        step_panels.update({
            "files": files_panel,
            "validation": validation_panel,
            "selection": selection_panel,
            "export": export_panel,
        })
        go_to_step("files")

        with ui.row().classes("w-full justify-between items-center"):
            ui.label("MVP · Procesamiento local · Sin escritura en WooCommerce").classes(
                "text-xs text-slate-500"
            )
            ui.label("Preparación local · Sin escritura en WooCommerce").classes(
                "text-xs font-medium text-slate-600"
            )


def format_catalog_price(value: str) -> str:
    """Format supplier prices as Argentine pesos for the selection UI."""
    raw = str(value or "").strip().replace(" ", "")
    if not raw:
        return "Sin precio"
    normalized = raw
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return f"$ {raw}"
    localized = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {localized}"


def run_app():
    """Start the local NiceGUI application in a browser."""
    build_ui()
    ui.run(
        title="WooCommerce Catalog Toolkit",
        native=False,
        reload=False,
        show=True,
    )


if __name__ == "__main__":
    run_app()