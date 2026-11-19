"""Streamlit entry point for the guided WooCommerce catalog workflow."""

import streamlit as st

from src.ui.wizard import render_wizard


st.set_page_config(
    page_title="WooCommerce Catalog Toolkit",
    page_icon="🧰",
    layout="wide",
)

render_wizard()
