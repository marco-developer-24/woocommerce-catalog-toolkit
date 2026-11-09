"""Local Streamlit interface for the Catalog CSV Validator."""

import csv
import hashlib
import io
import unicodedata
import zipfile

import streamlit as st

from src.application.catalog_validation import run_catalog_validation
from src.application.catalog_preparation import prepare_catalog
from src.application.catalog_preparation_report import build_preparation_review
from src.application.catalog_input import read_csv_rows
from src.catalog_csv_report import REPORT_FIELDS, build_catalog_report, filter_catalog_issues
from src.application.catalog_input import detect_delimiter, read_csv_preview

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DELIMITER_OPTIONS = {
    "Punto y coma (;)": ";",
    "Coma (,)": ",",
    "Tabulación": "\t",
    "Barra vertical (|)": "|",
}



def make_dict_rows_csv(rows, fieldnames):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return ('\ufeff' + output.getvalue()).encode('utf-8')

def make_issues_csv(issues):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=REPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(issues)
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def make_issues_text(issues):
    """Return a readable, copy-friendly representation of all validation issues."""
    if not issues:
        return "No se detectaron incidencias según las reglas actuales."

    blocks = []
    for issue in issues:
        blocks.append(
            f"Fila: {issue['row_number']}\n"
            f"Campo: {issue['field']}\n"
            f"Severidad: {issue['severity']}\n"
            f"Código: {issue['code']}\n"
            f"Valor: {issue['value']}\n"
            f"Detalle: {issue['message']}"
        )
    return "\n\n".join(blocks)


def normalize_header(value):
    """Normalize supplier headers for tolerant, accent-insensitive matching."""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return "".join(char.casefold() for char in normalized if char.isalnum())


def suggest_column(headers, aliases):
    """Suggest a header using normalized exact matches, without guessing loosely."""
    normalized_aliases = {normalize_header(alias) for alias in aliases}
    for header in headers:
        if normalize_header(header) in normalized_aliases:
            return headers.index(header)
    return 0


def make_summary(filename, file_hash, delimiter, mapping, report, ignored_empty_columns=0):
    lines = [
        "WooCommerce Catalog Toolkit — Catalog CSV Validator",
        "",
        f"Archivo analizado: {filename}",
        f"SHA-256: {file_hash}",
        f"Delimitador: {delimiter!r}",
        f"Columnas vacías sin encabezado ignoradas: {ignored_empty_columns}",
        f"Columna SKU: {mapping['sku']}",
        f"Columna nombre: {mapping['name']}",
        f"Columna precio: {mapping['price']}",
        f"Columna stock: {mapping['stock'] or 'No validada'}",
        "",
        f"Productos analizados: {report['total_products']}",
        f"Productos sin errores: {report['ready_products']}",
        f"Productos con errores: {report['products_with_errors']}",
        f"Productos con advertencias: {report['products_with_warnings']}",
        f"Errores detectados: {report['error_count']}",
        f"Advertencias detectadas: {report['warning_count']}",
        "",
        "Este informe es una revisión de calidad de datos. No importa ni modifica productos en WooCommerce.",
        "Los productos sin errores no quedan automáticamente aprobados para importar; requieren revisión humana.",
    ]
    return "\n".join(lines) + "\n"


def make_report_zip(issues_csv, summary):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("catalog_issues.csv", issues_csv)
        archive.writestr("summary.txt", summary)
    return output.getvalue()


st.set_page_config(page_title="Catalog CSV Validator", page_icon="🧰", layout="wide")

st.title("WooCommerce Catalog Toolkit")
st.subheader("Validador de catálogo CSV")
st.write(
    "Revisá la calidad de los datos de un proveedor antes de preparar una importación. "
    "El análisis es local: no se conecta a tu tienda y no modifica el archivo original."
)

with st.container(border=True):
    uploaded_file = st.file_uploader("Cargá el CSV del proveedor", type=["csv"])
    if uploaded_file is None:
        st.info("Subí un archivo CSV para comenzar. Se aceptan archivos UTF-8 y UTF-8 con BOM.")
        st.stop()

    file_bytes = uploaded_file.getvalue()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        st.error("El archivo supera el límite de 50 MB para esta primera versión.")
        st.stop()

    try:
        sample = file_bytes[:8192].decode("utf-8-sig")
    except UnicodeDecodeError:
        st.error("No se pudo leer el archivo como UTF-8. Exportalo como CSV UTF-8 e intentá nuevamente.")
        st.stop()

    detected_delimiter = detect_delimiter(sample)
    delimiter_labels = list(DELIMITER_OPTIONS)
    detected_label = next(
        (label for label, value in DELIMITER_OPTIONS.items() if value == detected_delimiter),
        delimiter_labels[0],
    )
    selected_label = st.selectbox(
        "Separador de columnas",
        delimiter_labels,
        index=delimiter_labels.index(detected_label),
        help="El separador se detecta automáticamente, pero podés corregirlo si la vista previa no se ve bien.",
    )
    delimiter = DELIMITER_OPTIONS[selected_label]

    try:
        headers, preview, total_rows, ignored_empty_columns = read_csv_preview(file_bytes, delimiter)
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        st.error(f"No se pudo interpretar el CSV: {exc}")
        st.stop()

    if ignored_empty_columns:
        st.warning(
            f"Se detectaron {ignored_empty_columns} columna(s) sin encabezado y completamente vacía(s). "
            "Se ignorarán durante el análisis; el archivo original no se modifica."
        )

    st.caption(f"Archivo: {uploaded_file.name} · {total_rows} filas de productos · {len(headers)} columnas útiles")
    st.markdown("**Vista previa**")
    st.caption(
        "Vista compacta para inspeccionar la estructura. Los valores largos se recortan "
        "solo en pantalla; el análisis utiliza siempre el contenido original."
    )

    preview_limit = st.selectbox(
        "Filas para mostrar",
        options=[5, 10, 20],
        index=1,
        key="preview_row_limit",
    )
    visible_default = []
    for candidate in ("SKU", "Código", "CODIGO", "Nombre", "Descripción", "Precio", "Price"):
        match = next((header for header in headers if header.casefold() == candidate.casefold()), None)
        if match and match not in visible_default:
            visible_default.append(match)
    for header in headers:
        if len(visible_default) >= min(6, len(headers)):
            break
        if header not in visible_default:
            visible_default.append(header)

    visible_columns = st.multiselect(
        "Columnas visibles",
        options=headers,
        default=visible_default,
        key="preview_visible_columns",
        help="Elegí qué columnas querés inspeccionar. Podés agregar o quitar columnas cuando lo necesites.",
    )
    if not visible_columns:
        st.info("Seleccioná al menos una columna para mostrar la vista previa.")
    else:
        st.caption(f"Mostrando {len(visible_columns)} de {len(headers)} columnas.")
        compact_preview = [
            {
                header: (
                    str(row.get(header, ""))
                    if len(str(row.get(header, ""))) <= 56
                    else str(row.get(header, ""))[:53] + "..."
                )
                for header in visible_columns
            }
            for row in preview[:preview_limit]
        ]
        column_config = {
            header: st.column_config.TextColumn(header, width="medium")
            for header in visible_columns
        }
        st.dataframe(
            compact_preview,
            column_order=visible_columns,
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            height=360,
        )

        if preview:
            st.markdown("**Inspeccionar un valor completo**")
            detail_col1, detail_col2 = st.columns([1, 2])
            with detail_col1:
                detail_row = st.selectbox(
                    "Fila de la vista previa",
                    options=list(range(len(preview))),
                    format_func=lambda index: f"Fila {index + 1} (CSV: {index + 2})",
                    key="preview_detail_row",
                )
            with detail_col2:
                detail_column = st.selectbox(
                    "Columna",
                    options=headers,
                    key="preview_detail_column",
                )
            full_value = str(preview[detail_row].get(detail_column, ""))
            st.code(full_value if full_value else "(vacío)", language="text")

    aliases = {
        "sku": ("SKU", "sku", "CODIGO", "CÓDIGO", "PRODUCT_CODE", "CODE"),
        "name": ("PRODUCT_NAME", "NAME", "NOMBRE", "DESCRIPCION", "DESCRIPCIÓN", "DESCRIPTION"),
        "price": ("PRICE", "PRECIO", "PRECIO_VENTA", "SALE_PRICE"),
        "stock": ("STOCK", "QUANTITY", "CANTIDAD", "EXISTENCIA"),
    }

    def default_column(kind):
        return suggest_column(headers, aliases[kind])

    st.markdown("**Asignación de columnas**")
    st.caption("Confirmá qué columna representa cada dato. El stock es opcional.")
    col1, col2 = st.columns(2)
    with col1:
        sku_column = st.selectbox("SKU", headers, index=default_column("sku"), key="sku_column")
        name_column = st.selectbox("Nombre del producto", headers, index=default_column("name"), key="name_column")
    with col2:
        price_column = st.selectbox("Precio", headers, index=default_column("price"), key="price_column")
        stock_options = ["— No validar stock —"] + headers
        stock_default = next(
            (header for candidate in aliases["stock"] for header in headers if header.casefold() == candidate.casefold()),
            None,
        )
        stock_column = st.selectbox(
            "Stock (opcional)",
            stock_options,
            index=stock_options.index(stock_default) if stock_default else 0,
            key="stock_column",
        )
    current_mapping = {
        "sku": sku_column,
        "name": name_column,
        "price": price_column,
        "stock": None if stock_column == "— No validar stock —" else stock_column,
    }
    required_columns = [current_mapping["sku"], current_mapping["name"], current_mapping["price"]]
    mapping_error = None
    if len(set(required_columns)) != len(required_columns):
        mapping_error = "SKU, nombre y precio deben estar asignados a columnas diferentes."
    elif current_mapping["stock"] in required_columns:
        mapping_error = "La columna de stock debe ser distinta de SKU, nombre y precio."

    if mapping_error:
        st.error(mapping_error)
    else:
        st.caption("Asignación válida: cada campo utiliza una columna diferente.")

    current_signature = (
        hashlib.sha256(file_bytes).hexdigest(),
        delimiter,
        current_mapping["sku"],
        current_mapping["name"],
        current_mapping["price"],
        current_mapping["stock"],
    )

    if st.button(
        "Analizar catálogo",
        type="primary",
        use_container_width=True,
        disabled=bool(mapping_error),
    ):
        try:
            validation = run_catalog_validation(
                file_bytes,
                total_products=total_rows,
                delimiter=delimiter,
                mapping=current_mapping,
            )
            issues = validation["issues"]
            report = validation["report"]
            file_hash = validation["file_hash"]
            issues_csv = make_issues_csv(issues)
            summary = make_summary(
                uploaded_file.name,
                file_hash,
                delimiter,
                current_mapping,
                report,
                ignored_empty_columns,
            )
            issues_text = make_issues_text(issues)
            diagnostic_text = (
                summary
                + "\nDetalle de incidencias\n======================\n"
                + issues_text
            )
            archive = make_report_zip(issues_csv, summary)

            st.session_state["catalog_validation"] = {
                "issues": issues,
                "report": report,
                "issues_csv": issues_csv,
                "summary": summary,
                "issues_text": issues_text,
                "diagnostic_text": diagnostic_text,
                "archive": archive,
                "signature": current_signature,
            }
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            st.error(f"No se pudo completar la validación: {exc}")
            st.session_state.pop("catalog_validation", None)

result = st.session_state.get("catalog_validation")
if result and result.get("signature") == current_signature:
    st.divider()
    st.header("Resultado del análisis")
    report = result["report"]
    metric_cols = st.columns(4)
    metric_cols[0].metric("Productos", report["total_products"])
    metric_cols[1].metric("Sin errores", report["ready_products"])
    metric_cols[2].metric("Con errores", report["products_with_errors"])
    metric_cols[3].metric("Con advertencias", report["products_with_warnings"])

    if report["total_issues"] == 0:
        st.success("No se detectaron problemas en las reglas actuales.")
    else:
        st.warning(
            f"Se detectaron {report['error_count']} errores y "
            f"{report['warning_count']} advertencias. Revisá el detalle antes de importar."
        )

    if result["issues"]:
        st.subheader("Problemas detectados")
        filter_cols = st.columns([1, 1, 2])
        with filter_cols[0]:
            severity_label = st.selectbox(
                "Severidad",
                ["Todas", "Errores", "Advertencias"],
                key="issue_severity_filter",
            )
        with filter_cols[1]:
            available_fields = sorted({issue["field"] for issue in result["issues"]})
            field_filter = st.selectbox(
                "Campo",
                ["Todos"] + available_fields,
                key="issue_field_filter",
            )
        with filter_cols[2]:
            issue_search = st.text_input(
                "Buscar en incidencias",
                placeholder="SKU, valor, código o descripción...",
                key="issue_search_filter",
            )

        severity_filter = {
            "Todas": None,
            "Errores": "error",
            "Advertencias": "warning",
        }[severity_label]
        visible_issues = filter_catalog_issues(
            result["issues"],
            severity=severity_filter,
            field=None if field_filter == "Todos" else field_filter,
            search=issue_search,
        )
        st.caption(
            f"Mostrando {len(visible_issues)} de {len(result['issues'])} incidencias. "
            "Los archivos descargables conservan el informe completo."
        )
        if visible_issues:
            st.dataframe(visible_issues, hide_index=True, use_container_width=True)
        else:
            st.info("No hay incidencias que coincidan con estos filtros.")
    else:
        st.info("El CSV no presenta incidencias según las reglas actuales.")

    st.subheader("Copiar resultados")
    st.caption("Los bloques incluyen un control de copia en su esquina superior derecha.")
    with st.expander("Copiar resumen", expanded=False):
        st.code(result["summary"], language="text")
    with st.expander("Copiar incidencias", expanded=False):
        st.code(result["issues_text"], language="text")
    with st.expander("Copiar diagnóstico completo", expanded=False):
        st.code(result["diagnostic_text"], language="text")

    st.subheader("Descargar resultados")
    download_cols = st.columns(2)
    download_cols[0].download_button(
        "Descargar incidencias CSV",
        data=result["issues_csv"],
        file_name="catalog_issues.csv",
        mime="text/csv",
        use_container_width=True,
    )
    download_cols[1].download_button(
        "Descargar informe completo ZIP",
        data=result["archive"],
        file_name="catalog_validation_report.zip",
        mime="application/zip",
        use_container_width=True,
    )
    with st.expander("Ver resumen del análisis"):
        st.code(result["summary"], language="text")

elif result:
    st.info("Cambiaste el archivo o la configuración. Ejecutá nuevamente el análisis para generar resultados actualizados.")

st.divider()
st.header("Preparación de catálogo")
st.write("Seleccioná productos nuevos para un lote por categoría. Se comparan los SKU contra una exportación de WooCommerce. Esta etapa no importa ni publica productos.")
st.caption("Regla actual: dentro de cada categoría se priorizan los productos elegibles de menor precio. Revisá el resultado antes de continuar.")

with st.container(border=True):
    catalog_file = st.file_uploader("Exportación actual de productos WooCommerce", type=["csv"], key="preparation_catalog_file")
    if catalog_file is not None:
        catalog_bytes = catalog_file.getvalue()
        if len(catalog_bytes) > MAX_UPLOAD_BYTES:
            st.error("La exportación supera el límite de 50 MB.")
        else:
            try:
                catalog_sample = catalog_bytes[:8192].decode("utf-8-sig")
                detected_catalog_delimiter = detect_delimiter(catalog_sample)
                catalog_delimiter_label = next((label for label, value in DELIMITER_OPTIONS.items() if value == detected_catalog_delimiter), delimiter_labels[0])
                catalog_label = st.selectbox("Separador del catálogo WooCommerce", delimiter_labels, index=delimiter_labels.index(catalog_delimiter_label), key="preparation_catalog_delimiter")
                catalog_delimiter = DELIMITER_OPTIONS[catalog_label]
                catalog_headers, catalog_rows = read_csv_rows(catalog_bytes, catalog_delimiter)
                _, supplier_rows = read_csv_rows(file_bytes, delimiter)

                st.markdown("**Mapeo para preparar productos nuevos**")
                left, right = st.columns(2)
                with left:
                    prep_sku = st.selectbox("SKU del proveedor", headers, index=headers.index(current_mapping["sku"]), key="prep_sku")
                    prep_name = st.selectbox("Nombre del producto", headers, index=headers.index(current_mapping["name"]), key="prep_name")
                    prep_category = st.selectbox("Categoría del proveedor", headers, index=suggest_column(headers, ("CATEGORIA", "CATEGORY", "PRODUCT_CATEGORY")), key="prep_category")
                with right:
                    prep_price = st.selectbox("Precio para selección", headers, index=headers.index(current_mapping["price"]), key="prep_price")
                    prep_catalog_sku = st.selectbox("SKU en WooCommerce", catalog_headers, index=suggest_column(catalog_headers, ("SKU", "Product SKU")), key="prep_catalog_sku")
                    stock_options = ["— Sin filtro de stock —"] + headers
                    prep_stock = st.selectbox("Stock del proveedor (opcional)", stock_options, key="prep_stock")

                categories = sorted({str(row.get(prep_category, "")).strip() for row in supplier_rows if str(row.get(prep_category, "")).strip()}, key=str.casefold)
                selected_categories = st.multiselect("Categorías habilitadas para este lote", categories, default=[], key="prep_enabled_categories", help="Elegí explícitamente qué categorías incluir.")
                category_limits = {}
                if selected_categories:
                    st.markdown("**Límite de productos por categoría**")
                    limit_columns = st.columns(min(3, len(selected_categories)))
                    for index, category in enumerate(selected_categories):
                        with limit_columns[index % len(limit_columns)]:
                            category_limits[category] = st.number_input(category, min_value=0, value=5, step=1, key=f"prep_limit_{index}_{normalize_header(category)}")

                apply_stock_filter = False
                minimum_stock = None
                if prep_stock != "— Sin filtro de stock —":
                    apply_stock_filter = st.checkbox("Aplicar stock mínimo", value=False, key="prep_apply_stock_minimum")
                    if apply_stock_filter:
                        minimum_stock = st.number_input("Stock mínimo", min_value=0, value=1, step=1, key="prep_minimum_stock")

                required_mapping = [prep_sku, prep_name, prep_price, prep_category]
                mapping_error = len(set(required_mapping)) != len(required_mapping) or prep_stock in required_mapping
                if mapping_error:
                    st.error("SKU, nombre, precio y categoría deben usar columnas diferentes. La columna de stock también debe ser distinta.")

                if st.button("Preparar selección de productos", type="primary", use_container_width=True, disabled=not selected_categories or mapping_error, key="run_catalog_preparation"):
                    try:
                        selection_config = {"category_column": prep_category, "price_column": prep_price, "category_limits": category_limits}
                        if prep_stock != "— Sin filtro de stock —":
                            selection_config["stock_column"] = prep_stock
                        if apply_stock_filter:
                            selection_config["minimum_stock"] = minimum_stock
                        preparation = prepare_catalog(supplier_rows, catalog_rows, selection_config=selection_config, supplier_columns={"sku": prep_sku, "name": prep_name, "price": prep_price, "catalog_sku": prep_catalog_sku})
                        review_rows = build_preparation_review(preparation, prep_category, prep_price)
                        review_fields = ["CSV row", "SKU", "Category", "Price", "Status", "Reason code", "Reason", "Category position"]
                        selected_fields = ["SKU", "Name", "Regular price", "Published", "Type"]
                        prep_signature = (
                            hashlib.sha256(file_bytes).hexdigest(),
                            hashlib.sha256(catalog_bytes).hexdigest(),
                            delimiter,
                            catalog_delimiter,
                            prep_sku,
                            prep_name,
                            prep_price,
                            prep_category,
                            prep_catalog_sku,
                            prep_stock,
                            tuple(sorted(category_limits.items())),
                            minimum_stock if apply_stock_filter else None,
                        )
                        st.session_state["catalog_preparation"] = {"result": preparation, "review_rows": review_rows, "review_csv": make_dict_rows_csv(review_rows, review_fields), "selected_csv": make_dict_rows_csv(preparation["export_rows"], selected_fields), "signature": prep_signature}
                    except (OSError, UnicodeError, csv.Error, ValueError, TypeError) as exc:
                        st.error(f"No se pudo preparar el catálogo: {exc}")
                        st.session_state.pop("catalog_preparation", None)
            except (UnicodeDecodeError, csv.Error, ValueError) as exc:
                st.error(f"No se pudo leer la exportación de WooCommerce: {exc}")

prep_result = st.session_state.get("catalog_preparation")
if prep_result:
    st.subheader("Resultado de preparación")
    preparation = prep_result["result"]
    summary = preparation["summary"]
    metrics = st.columns(4)
    metrics[0].metric("Filas proveedor", summary["supplier_rows"])
    metrics[1].metric("Nuevos aptos", summary["new_ready"])
    metrics[2].metric("Seleccionados", summary["exported"])
    metrics[3].metric("Existentes excluidos", summary["excluded_existing"])
    detail_metrics = st.columns(3)
    detail_metrics[0].metric("Bloqueados", summary["blocked"])
    detail_metrics[1].metric("En revisión", summary["review"])
    detail_metrics[2].metric("Aptos fuera del límite", summary["ready_not_selected"])
    if preparation["export_rows"]:
        st.success(f"Se prepararon {summary['exported']} producto(s). La salida mantiene Published=0 y Type=simple.")
    else:
        st.warning("No hay productos seleccionados con la configuración actual.")
    st.markdown("**Detalle de selección**")
    if prep_result["review_rows"]:
        st.dataframe(prep_result["review_rows"], hide_index=True, use_container_width=True)
    else:
        st.info("No hay filas aptas para selección con las categorías configuradas.")
    downloads = st.columns(2)
    downloads[0].download_button("Descargar productos seleccionados CSV", data=prep_result["selected_csv"], file_name="catalog_preparation_selected.csv", mime="text/csv", use_container_width=True, disabled=not preparation["export_rows"])
    downloads[1].download_button("Descargar revisión CSV", data=prep_result["review_csv"], file_name="catalog_preparation_review.csv", mime="text/csv", use_container_width=True)
    st.caption("La exportación contiene SKU, nombre, precio, Published y Type. No es todavía un archivo universal de importación WooCommerce.")

st.divider()
st.caption("Versión inicial de la interfaz · Análisis local · Sin conexión a WooCommerce · Sin escritura sobre el archivo fuente") · Análisis local · Sin conexión a WooCommerce · Sin escritura sobre el archivo fuente")
