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
from src.application.catalog_preparation import prepare_catalog
from src.application.catalog_exports import make_dict_rows_csv
from src.operations.add_products import prepare_add_products
from src.operations.select_products import normalize_category
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
    }
    provider_selectors = {}
    store_selectors = {}

    ui.add_head_html("""<style>
        .catalog-upload .q-uploader__list { display: none !important; }
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
                ).props('accept=".csv"').classes("w-full catalog-upload")

            def clear_store(*, reset_upload=True):
                if reset_upload:
                    store_upload.reset()
                state["store_inspection"] = None
                state["store"] = None
                state["store_mode"] = "not_decided" if state["provider"] else "empty"
                state["preparation"] = None
                store_selectors.clear()
                preparation_results.clear()
                prepare_button.disable()
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
                store_confirmation.clear()

            def clear_provider(*, reset_upload=True):
                if reset_upload:
                    provider_upload.reset()
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
            store_confirmation = ui.column().classes("w-full gap-3")
            store_upload = ui.upload(
                label="Seleccionar exportación CSV de WooCommerce",
                auto_upload=True,
                max_file_size=MAX_UPLOAD_BYTES,
                max_files=1,
            ).props('accept=".csv"').classes("w-full catalog-upload")
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
                    store_confirmation.clear()
                    ui.notify(str(exc), type="negative")
                    return

                state["store"] = confirmed
                state["store_mode"] = "reference"
                prepare_button.enable()
                continue_without_store_button.disable()
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
                state["store_mode"] = "reading"
                state["preparation"] = None
                prepare_button.disable()
                continue_without_store_button.disable()
                preparation_results.clear()
                preparation_status.set_text(
                    "Confirmá el mapeo de WooCommerce para usar esta exportación como referencia."
                )
                store_mapping_area.clear()
                store_confirmation.clear()
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
                    "Cada fila del proveedor aparece clasificada. En esta etapa "
                    "todavía no se modifica ni se exporta ningún producto."
                ).classes("text-sm text-slate-600")
                with ui.grid(columns=2).classes("w-full gap-3"):
                    for status in (READY, REVIEW, BLOCKED, EXCLUDED):
                        with ui.card().classes("p-3 gap-1"):
                            ui.label(status_labels[status]).classes(
                                "text-xs text-slate-500"
                            )
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
                        "Preparación sin exportación WooCommerce: no se verificó "
                        "si estos SKU ya existen en la tienda. Los candidatos nuevos "
                        "son relativos a una referencia vacía."
                    ).classes("text-sm text-amber-800")
                columns = [
                    {"name": "row_number", "label": "Fila", "field": "row_number", "align": "left"},
                    {"name": "sku", "label": "SKU", "field": "sku", "align": "left"},
                    {"name": "name", "label": "Producto", "field": "name", "align": "left"},
                    {"name": "price", "label": "Precio", "field": "price", "align": "left"},
                    {"name": "stock", "label": "Stock", "field": "stock", "align": "left"},
                    {"name": "status", "label": "Clasificación", "field": "status", "align": "left"},
                    {"name": "reason", "label": "Motivo", "field": "reason", "align": "left"},
                ]
                ui.table(
                    columns=columns,
                    rows=rows,
                    row_key="row_number",
                    pagination=20,
                ).classes("w-full")
            preparation_status.set_text("Preparación de altas completada.")
            preparation_status.classes(replace="text-sm text-green-700 font-semibold")
            ui.notify("Clasificación de productos completada", type="positive")
            render_category_selection()

        def render_category_selection():
            category_selection_area.clear()
            category_controls.clear()
            provider = state["provider"]
            if provider is None:
                return

            mapping = provider["mapping"]
            category_column = mapping.get("category")
            if not category_column:
                return

            categories_by_key = {}
            for row in provider["rows"]:
                value = str(row.get(category_column, "") or "").strip()
                key = normalize_category(value)
                if key:
                    categories_by_key.setdefault(key, value)

            categories = sorted(categories_by_key.items(), key=lambda item: item[1].casefold())
            store = state["store"]
            destinations = store["observed_categories"] if store else []

            with category_selection_area:
                ui.separator()
                ui.label("5. Selección por categoría").classes(
                    "text-lg font-semibold text-slate-900"
                )
                ui.label(
                    "Activá las categorías que querés preparar y definí un cupo. "
                    "Dentro de cada categoría se prioriza el menor precio."
                ).classes("text-sm text-slate-600")
                if not destinations:
                    ui.label(
                        "No hay categorías de destino verificadas. Podés configurar "
                        "la selección, pero no se habilitará la exportación sin una "
                        "exportación WooCommerce que permita asignar categorías existentes."
                    ).classes("text-sm text-amber-800")

                for key, category in categories:
                    with ui.card().classes("w-full p-3 gap-2"):
                        with ui.row().classes("w-full items-center gap-3"):
                            enabled = ui.checkbox(category, value=False)
                            limit = ui.number(
                                label="Cupo",
                                value=0,
                                min=0,
                                precision=0,
                            ).classes("w-28")
                        destination = ui.select(
                            options=destinations,
                            label="Categoría de destino en WooCommerce",
                            clearable=True,
                        ).classes("w-full")
                        category_controls[key] = {
                            "source": category,
                            "enabled": enabled,
                            "limit": limit,
                            "destination": destination,
                        }

                ui.button(
                    "Aplicar selección",
                    on_click=apply_category_selection,
                    icon="playlist_add_check",
                ).props("color=primary")

        def apply_category_selection():
            provider = state["provider"]
            if provider is None:
                return

            category_limits = {}
            category_mappings = {}
            for key, controls in category_controls.items():
                if not controls["enabled"].value:
                    continue
                raw_limit = controls["limit"].value
                if raw_limit is None or int(raw_limit) < 0:
                    ui.notify(
                        f"Definí un cupo válido para {controls['source']}.",
                        type="warning",
                    )
                    return
                category_limits[controls["source"]] = int(raw_limit)
                destination = controls["destination"].value
                if destination:
                    category_mappings[key] = destination

            if not category_limits:
                ui.notify("Activá al menos una categoría para continuar.", type="warning")
                return

            store = state["store"]
            catalog_rows = store["rows"] if store else []
            catalog_sku_column = store["mapping"]["sku"] if store else "SKU"
            mapping = provider["mapping"]

            try:
                result = prepare_catalog(
                    provider["rows"],
                    catalog_rows,
                    selection_config={
                        "category_column": mapping["category"],
                        "price_column": mapping["price"],
                        "category_limits": category_limits,
                        "stock_column": mapping.get("stock"),
                        "category_mappings": category_mappings,
                        "require_category_mapping": True,
                    },
                    supplier_columns={
                        "sku": mapping["sku"],
                        "name": mapping["name"],
                        "price": mapping["price"],
                        "catalog_sku": catalog_sku_column,
                    },
                )
            except (KeyError, TypeError, ValueError) as exc:
                state["selection_result"] = None
                ui.notify(f"No se pudo aplicar la selección: {exc}", type="negative")
                return

            state["selection_result"] = result
            category_selection_area.clear()
            with category_selection_area:
                ui.separator()
                ui.label("Resultado de la selección").classes(
                    "text-lg font-semibold text-slate-900"
                )
                summary = result["summary"]
                with ui.grid(columns=2).classes("w-full gap-3"):
                    for label, value in (
                        ("Elegibles antes de seleccionar", summary["new_ready"]),
                        ("Preparados para exportar", summary["exported"]),
                        ("En revisión", summary["review"]),
                        ("Bloqueados", summary["blocked"]),
                        ("Ya existentes", summary["excluded_existing"]),
                        ("Fuera del cupo o sin categoría", summary["ready_not_selected"]),
                    ):
                        with ui.card().classes("p-3 gap-1"):
                            ui.label(label).classes("text-xs text-slate-500")
                            ui.label(f"{value:,}").classes(
                                "text-2xl font-semibold text-slate-900"
                            )

                selection_rows = []
                for item in result["selection"]["items"]:
                    selection_rows.append({
                        "row_number": item["row_number"],
                        "sku": str(item["row"].get(mapping["sku"], "") or ""),
                        "name": str(item["row"].get(mapping["name"], "") or ""),
                        "category": str(item["category"] or ""),
                        "price": str(item["price"] or ""),
                        "status": item["status"],
                        "reason": item["reason"] or "",
                    })
                ui.table(
                    columns=[
                        {"name": "row_number", "label": "Fila", "field": "row_number"},
                        {"name": "sku", "label": "SKU", "field": "sku"},
                        {"name": "name", "label": "Producto", "field": "name"},
                        {"name": "category", "label": "Categoría", "field": "category"},
                        {"name": "price", "label": "Precio", "field": "price"},
                        {"name": "status", "label": "Selección", "field": "status"},
                        {"name": "reason", "label": "Motivo", "field": "reason"},
                    ],
                    rows=selection_rows,
                    row_key="row_number",
                    pagination=20,
                ).classes("w-full")

                if result["export_rows"] and store is not None:
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
                        "El archivo contiene únicamente productos seleccionados, "
                        "con SKU único, precio validado y estado borrador."
                    ).classes("text-sm text-green-700")
                else:
                    ui.label(
                        "No hay productos exportables. Revisá los cupos y las "
                        "categorías de destino. La exportación requiere una referencia "
                        "WooCommerce con categorías observadas."
                    ).classes("text-sm text-amber-800")

            ui.notify("Selección por categoría aplicada", type="positive")

        with ui.card().classes("w-full p-6 gap-4"):
            ui.label("4. Preparación de altas").classes(
                "text-lg font-semibold text-slate-900"
            )
            ui.label(
                "Clasificá todos los productos del proveedor antes de configurar "
                "selecciones o generar archivos."
            ).classes("text-sm text-slate-500")
            preparation_status = ui.label(
                "Primero cargá y confirmá el mapeo del proveedor."
            ).classes("text-sm text-slate-600")
            prepare_button = ui.button(
                "Preparar altas",
                on_click=prepare_addition,
                icon="inventory",
            ).props("color=primary")
            prepare_button.disable()
            preparation_results = ui.column().classes("w-full gap-3")
            category_selection_area = ui.column().classes("w-full gap-3")
            category_controls = {}

        with ui.row().classes("w-full justify-between items-center"):
            ui.label("MVP · Procesamiento local · Sin escritura en WooCommerce").classes(
                "text-xs text-slate-500"
            )
            ui.label("Etapa 3: comparación por SKU").classes(
                "text-xs font-medium text-slate-600"
            )


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