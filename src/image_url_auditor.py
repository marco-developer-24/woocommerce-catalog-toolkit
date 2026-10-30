#!/usr/bin/env python3
"""Audit image URLs listed in a CSV file."""

import argparse
import csv
import math
import os
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


FIELDNAMES = (
    "status",
    "content_type",
    "content_length",
    "response_time",
    "result",
    "error",
)


def check_image(url, timeout=15):
    """Check an image URL and return HTTP and response metadata."""
    url = (url or "").strip()

    if not url:
        return {
            "status": "",
            "content_type": "",
            "content_length": "",
            "response_time": "",
            "result": "INVALID_URL",
            "error": "URL is empty",
        }

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        username = parsed.username
        password = parsed.password
    except ValueError:
        return {
            "status": "",
            "content_type": "",
            "content_length": "",
            "response_time": "",
            "result": "INVALID_URL",
            "error": "Malformed URL",
        }

    if (
        parsed.scheme.lower() not in ("http", "https")
        or not hostname
        or username is not None
        or password is not None
    ):
        return {
            "status": "",
            "content_type": "",
            "content_length": "",
            "response_time": "",
            "result": "INVALID_URL",
            "error": "Expected an absolute HTTP or HTTPS URL without credentials",
        }

    started = time.monotonic()

    try:
        request = Request(
            url,
            headers={"User-Agent": "WooCommerceCatalogToolkit/0.1"},
        )

        with urlopen(request, timeout=timeout) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            content_length = response.headers.get("Content-Length", "")
            elapsed = round(time.monotonic() - started, 3)

            media_type = content_type.split(";", 1)[0].strip().lower()
            is_image_response = (
                200 <= status < 300
                and status != 204
                and media_type.startswith("image/")
            )
            result = "OK" if is_image_response else "CHECK"

            if status == 204:
                error = "Server returned no content (HTTP 204)"
            elif not media_type.startswith("image/"):
                reported_type = media_type or "missing Content-Type"
                error = f"Response is not declared as an image ({reported_type})"
            else:
                error = ""

            return {
                "status": status,
                "content_type": content_type,
                "content_length": content_length,
                "response_time": elapsed,
                "result": result,
                "error": error,
            }

    except HTTPError as exc:
        elapsed = round(time.monotonic() - started, 3)
        return {
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type", ""),
            "content_length": exc.headers.get("Content-Length", ""),
            "response_time": elapsed,
            "result": "HTTP_ERROR",
            "error": str(exc.reason),
        }

    except (URLError, TimeoutError, OSError, ValueError) as exc:
        elapsed = round(time.monotonic() - started, 3)
        return {
            "status": "",
            "content_type": "",
            "content_length": "",
            "response_time": elapsed,
            "result": "CONNECTION_ERROR",
            "error": str(exc),
        }


def validate_input_csv(input_path, delimiter, required_columns):
    """Read and validate the complete CSV before making network requests."""
    with open(input_path, encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter=delimiter)
        headers = reader.fieldnames

        if not headers:
            raise ValueError("Input CSV is empty or has no header row.")

        if any(header is None or not header.strip() for header in headers):
            raise ValueError("CSV contains an empty column name.")

        if len(headers) != len(set(headers)):
            raise ValueError("CSV contains duplicate column names.")

        missing = set(required_columns) - set(headers)
        if missing:
            raise ValueError("Missing CSV columns: " + ", ".join(sorted(missing)))

        rows = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"CSV row {line_number} has more fields than the header."
                )

            if any(value is None for value in row.values()):
                raise ValueError(
                    f"CSV row {line_number} has fewer fields than the header."
                )

            rows.append(row)

        return rows


def main():
    parser = argparse.ArgumentParser(
        description="Audit image URLs from a CSV file."
    )
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--delimiter", default=";", help="CSV delimiter")
    parser.add_argument("--sku-column", default="SKU")
    parser.add_argument("--name-column", default="PRODUCT_NAME")
    parser.add_argument("--url-column", default="IMAGE_URL")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()

    if len(args.delimiter) != 1:
        parser.error("--delimiter must be exactly one character")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a finite number greater than zero")

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    if input_path == output_path:
        parser.error("Input and output paths must be different.")

    if output_path.exists():
        parser.error(
            f"Output already exists; refusing to overwrite it: {output_path}"
        )

    if not input_path.is_file():
        parser.error(f"Input file does not exist or is not a file: {input_path}")

    required_columns = (
        args.sku_column,
        args.name_column,
        args.url_column,
    )

    if len(set(required_columns)) != len(required_columns):
        parser.error("The configured input column names must be different.")

    try:
        rows = validate_input_csv(input_path, args.delimiter, required_columns)

        fieldnames = [
            args.sku_column,
            args.name_column,
            args.url_column,
            *FIELDNAMES,
        ]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_name = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8-sig",
                newline="",
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as target:
                temp_name = target.name
                writer = csv.DictWriter(
                    target,
                    fieldnames=fieldnames,
                    delimiter=args.delimiter,
                    extrasaction="ignore",
                )
                writer.writeheader()

                total = len(rows)
                for index, row in enumerate(rows, start=1):
                    info = check_image(row.get(args.url_column), args.timeout)
                    writer.writerow({**row, **info})
                    print(f"[{index}/{total}] {info['result']}")

            try:
                os.link(temp_name, output_path)
            except FileExistsError:
                raise ValueError(
                    f"Output appeared during processing; refusing to overwrite: "
                    f"{output_path}"
                )
            except OSError as exc:
                raise OSError(
                    f"Could not safely publish report at {output_path}: {exc}"
                ) from exc

        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)

        print(f"Finished. Audited {len(rows)} rows.")
        print(f"Report: {output_path}")

    except (OSError, csv.Error, UnicodeError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
