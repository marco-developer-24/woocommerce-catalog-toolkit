"""Local Streamlit interface for the Catalog CSV Validator."""

import csv
import hashlib
import io
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

from src.catalog_csv_validator import validate_catalog_csv
from src.catalog_csv_report import REPORT_FIELDS, build_catalog_report


MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DELIMITER_OPTIONS = {
    "Punto y coma (;)": ";",
    "Coma (,)": ",",
    "Tabulación": "\t",
    "Barra vertical (|)": "|",
}


def detect_delimiter(sample):
    """Return a likely delimiter, falling back to semicolon."""
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
    except csv.Error:
        return ";"


def read_csv_preview(file_bytes, delimiter, limit=10):
    """Read CSV headers and a small preview without changing uploaded bytes."""
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    headers = reader.fieldnames
    if not headers:
        raise ValueError("El archivo está vacío o no contiene encabezados.")
    if any(header is None or not header.strip() for header in headers):
        raise ValueError("El CSV contiene un nombre de columna vacío.")
    if len(headers) != len(set(headers)):
        raise ValueError("El CSV contiene nombres de columna duplicados.")

    preview = []
    total_rows = 0
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"El CSV tiene una fila con distinta cantidad de columnas (fila {total_rows + 2}).")
        total_rows += 1
        if len(preview) < limit:
            preview.append(row)
    return headers, preview, total_rows


def make_issues_csv(issues):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=REPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(issues)
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def make_summary(filename, file_hash, delimiter, mapping, report):
    lines = [
        "WooCommerce Catalog Toolkit — Catalog CSV Validator",
        "",
        f"Archivo analizado: {filename}",
        f"SHA-256: {file_hash}",
        f"Delimitador: {delimiter!r}",
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
        headers, preview, total_rows = read_csv_preview(file_bytes, delimiter)
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        st.error(f"No se pudo interpretar el CSV: {exc}")
        st.stop()

    st.caption(f"Archivo: {uploaded_file.name} · {total_rows} filas de productos · {len(headers)} columnas")
    st.markdown("**Vista previa**")
    st.dataframe(preview, use_container_width=True, hide_index=True)

    aliases = {
        "sku": ("SKU", "sku", "CODIGO", "CÓDIGO", "PRODUCT_CODE", "CODE"),
        "name": ("PRODUCT_NAME", "NAME", "NOMBRE", "DESCRIPCION", "DESCRIPCIÓN", "DESCRIPTION"),
        "price": ("PRICE", "PRECIO", "PRECIO_VENTA", "SALE_PRICE"),
        "stock": ("STOCK", "QUANTITY", "CANTIDAD", "EXISTENCIA"),
    }

    def default_column(kind, required=True):
        candidates = aliases[kind]
        match = next((header for candidate in candidates for header in headers if header.casefold() == candidate.casefold()), None)
        if match:
            return headers.index(match)
        return 0 if required else 0

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
    st.caption("Cada campo obligatorio debe apuntar a una columna diferente.")

    current_mapping = {
        "sku": sku_column,
        "name": name_column,
        "price": price_column,
        "stock": None if stock_column == "— No validar stock —" else stock_column,
    }
    current_signature = (
        hashlib.sha256(file_bytes).hexdigest(),
        delimiter,
        current_mapping["sku"],
        current_mapping["name"],
        current_mapping["price"],
        current_mapping["stock"],
    )

    if st.button("Analizar catálogo", type="primary", use_container_width=True):
        mapping = current_mapping
        required_columns = [mapping["sku"], mapping["name"], mapping["price"]]
        if len(set(required_columns)) != len(required_columns):
            st.error("SKU, nombre y precio deben estar asignados a columnas diferentes.")
        elif mapping["stock"] in required_columns:
            st.error("La columna de stock debe ser distinta de SKU, nombre y precio.")
        else:
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temporary:
                    temporary.write(file_bytes)
                    temp_path = Path(temporary.name)

                issues = validate_catalog_csv(
                    temp_path,
                    delimiter=delimiter,
                    sku_column=mapping["sku"],
                    name_column=mapping["name"],
                    price_column=mapping["price"],
                    stock_column=mapping["stock"],
                )
                report = build_catalog_report(total_rows, issues)
                issues_csv = make_issues_csv(issues)
                file_hash = hashlib.sha256(file_bytes).hexdigest()
                summary = make_summary(uploaded_file.name, file_hash, delimiter, mapping, report)
                archive = make_report_zip(issues_csv, summary)

                st.session_state["catalog_validation"] = {
                    "issues": issues,
                    "report": report,
                    "issues_csv": issues_csv,
                    "summary": summary,
                    "archive": archive,
                    "signature": current_signature,
                }
            except (OSError, UnicodeError, csv.Error, ValueError) as exc:
                st.error(f"No se pudo completar la validación: {exc}")
                st.session_state.pop("catalog_validation", None)
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)

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
        st.dataframe(result["issues"], use_container_width=True, hide_index=True)
    else:
        st.info("El CSV no presenta incidencias según las reglas actuales.")

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
st.caption("Versión inicial de la interfaz · Análisis local · Sin conexión a WooCommerce · Sin escritura sobre el archivo fuente")
