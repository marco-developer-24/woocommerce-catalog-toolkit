"""Build and export human-readable catalog validation reports."""

import csv
import os
import tempfile
from pathlib import Path


REPORT_FIELDS = ("row_number", "field", "value", "severity", "code", "message")


def build_catalog_report(total_products, issues):
    """Return aggregate counts for a validator result.

    A product is ready when it has no error-level issue. Warning-only products
    remain eligible for review, but are counted separately.
    """
    if not isinstance(total_products, int) or isinstance(total_products, bool):
        raise ValueError("total_products must be a non-negative integer.")
    if total_products < 0:
        raise ValueError("total_products must be a non-negative integer.")

    error_rows = set()
    warning_rows = set()
    error_count = 0
    warning_count = 0

    for issue in issues:
        severity = issue.get("severity")
        row_number = issue.get("row_number")
        if not isinstance(row_number, int) or row_number < 2:
            raise ValueError("Each issue must include a CSV row number >= 2.")
        if severity == "error":
            error_count += 1
            error_rows.add(row_number)
        elif severity == "warning":
            warning_count += 1
            warning_rows.add(row_number)
        else:
            raise ValueError("Issue severity must be 'error' or 'warning'.")

    if any(row_number > total_products + 1
           for row_number in error_rows | warning_rows):
        raise ValueError("An issue row number exceeds the product count.")

    return {
        "total_products": total_products,
        "ready_products": total_products - len(error_rows),
        "products_with_errors": len(error_rows),
        "products_with_warnings": len(warning_rows),
        "total_issues": error_count + warning_count,
        "error_count": error_count,
        "warning_count": warning_count,
    }


def export_issues_csv(issues, output_path, overwrite=False):
    """Write row-level issues to CSV and return the output path.

    Existing reports are protected by default. Set overwrite=True explicitly
    to replace one. The report is written to a temporary file first so a
    failed write does not leave a partially written destination.
    """
    destination = Path(output_path)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Report already exists: {destination}")

    destination.parent.mkdir(parents=False, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temp_path = Path(temporary.name)
            writer = csv.DictWriter(
                temporary, fieldnames=REPORT_FIELDS, extrasaction="ignore"
            )
            writer.writeheader()
            for issue in issues:
                writer.writerow({field: issue.get(field, "") for field in REPORT_FIELDS})

        if overwrite:
            os.replace(temp_path, destination)
        else:
            # Creating a hard link is atomic and fails if the destination exists.
            os.link(temp_path, destination)
            temp_path.unlink()
        return destination
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
