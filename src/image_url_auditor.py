#!/usr/bin/env python3
"""Audit image URLs listed in a CSV file."""

import argparse
import csv
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


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

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {
            "status": "",
            "content_type": "",
            "content_length": "",
            "response_time": "",
            "result": "INVALID_URL",
            "error": "Expected an absolute HTTP or HTTPS URL",
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
            result = (
                "OK"
                if 200 <= status < 300 and media_type.startswith("image/")
                else "CHECK"
            )

            return {
                "status": status,
                "content_type": content_type,
                "content_length": content_length,
                "response_time": elapsed,
                "result": result,
                "error": "",
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
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    try:
        with open(args.input, encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, delimiter=args.delimiter)

            required = {
                args.sku_column,
                args.name_column,
                args.url_column,
            }
            available = set(reader.fieldnames or [])
            missing = required - available

            if missing:
                parser.error(
                    "Missing CSV columns: " + ", ".join(sorted(missing))
                )

            rows = list(reader)

        fieldnames = [
            args.sku_column,
            args.name_column,
            args.url_column,
            "status",
            "content_type",
            "content_length",
            "response_time",
            "result",
            "error",
        ]

        with open(args.output, "w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(
                target,
                fieldnames=fieldnames,
                delimiter=args.delimiter,
                extrasaction="ignore",
            )
            writer.writeheader()

            for index, row in enumerate(rows, start=1):
                info = check_image(row.get(args.url_column), args.timeout)
                writer.writerow({**row, **info})
                print(f"[{index}/{len(rows)}] {info['result']}")

        print(f"Finished. Audited {len(rows)} rows.")
        print(f"Report: {args.output}")

    except (OSError, csv.Error, UnicodeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
