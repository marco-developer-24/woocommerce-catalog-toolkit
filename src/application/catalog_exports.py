"""In-memory exports for catalog validation and preparation workflows."""

import csv
import io
import zipfile

from src.catalog_csv_report import REPORT_FIELDS


def make_dict_rows_csv(rows, fieldnames):
    """Serialize dictionary rows to a UTF-8-with-BOM CSV byte string."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=fieldnames, extrasaction="ignore"
    )
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def make_issues_csv(issues):
    """Serialize validation issues using the canonical report field order."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=REPORT_FIELDS, extrasaction="ignore"
    )
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


def make_summary(
    filename, file_hash, delimiter, mapping, report, ignored_empty_columns=0
):
    """Build the human-readable summary for a catalog validation run."""
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
    """Package the validation issues CSV and text summary in memory."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("catalog_issues.csv", issues_csv)
        archive.writestr("summary.txt", summary)
    return output.getvalue()
