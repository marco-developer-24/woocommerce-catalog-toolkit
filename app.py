"""Local Streamlit interface for the Catalog CSV Validator."""

import csv
import hashlib
import unicodedata

import streamlit as st

from src.application.catalog_validation import run_catalog_validation
from src.application.catalog_exports import (
    make_dict_rows_csv,
    make_issues_csv,
    make_issues_text,
    make_report_zip,
    make_summary,
)
from src.application.catalog_preparation import prepare_catalog
from src.application.catalog_preparation_report import build_preparation_review
from src.catalog_csv_report import filter_catalog_issues
from src.application.catalog_input import (
    detect_delimiter,
    get_cached_csv_data,
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DELIMITER_OPTIONS = {
    "Punto y coma (;)": ";",