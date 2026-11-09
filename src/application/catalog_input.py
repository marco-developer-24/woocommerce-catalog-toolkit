"""Application services for reading and inspecting catalog CSV input."""

import csv
import io


def detect_delimiter(sample):
    """Return a likely delimiter, falling back to semicolon."""
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
    except csv.Error:
        return ";"


def _read_csv(file_bytes, delimiter):
    """Read all rows while enforcing the shared CSV structure rules."""
    if not isinstance(file_bytes, bytes):
        raise TypeError("file_bytes must be bytes.")

    text = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    raw_headers = next(reader, None)
    if not raw_headers:
        raise ValueError("El archivo está vacío o no contiene encabezados.")

    blank_positions = [
        index for index, header in enumerate(raw_headers) if not header.strip()
    ]
    headers = [header for header in raw_headers if header.strip()]
    if not headers:
        raise ValueError("El CSV no contiene columnas con encabezado.")
    if len(headers) != len(set(headers)):
        raise ValueError("El CSV contiene nombres de columna duplicados.")

    rows = []
    for row_number, values in enumerate(reader, start=2):
        if len(values) != len(raw_headers):
            raise ValueError(
                f"El CSV tiene una fila con distinta cantidad de columnas (fila {row_number})."
            )
        for position in blank_positions:
            if values[position].strip():
                raise ValueError(
                    f"La columna {position + 1} no tiene encabezado, "
                    f"pero contiene datos en la fila {row_number}."
                )
        rows.append({
            header: values[index]
            for index, header in enumerate(raw_headers)
            if header.strip()
        })
    return headers, rows, len(blank_positions)


def read_csv_rows(file_bytes, delimiter):
    """Read every CSV row as a dictionary without modifying source bytes."""
    headers, rows, _ = _read_csv(file_bytes, delimiter)
    return headers, rows


def read_csv_preview(file_bytes, delimiter, limit=10):
    """Read CSV headers and a small preview without changing uploaded bytes."""
    headers, rows, blank_columns = _read_csv(file_bytes, delimiter)
    return headers, rows[:limit], len(rows), blank_columns
