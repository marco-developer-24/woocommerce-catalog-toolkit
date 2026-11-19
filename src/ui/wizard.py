"""Guided Streamlit workflow for preparing WooCommerce catalog imports."""

import streamlit as st

from src.application.provider_profile import (
    detect_provider_profile,
    provider_mapping_fingerprint,
    validate_provider_mapping,
)
from src.application.provider_setup import (
    confirm_provider_setup,
    inspect_provider_file,
)


MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DELIMITER_OPTIONS = {
    "Punto y coma (;)": ";",
    "Coma (,)": ",",
    "Tabulación": "\t",
    "Barra vertical (|)": "|",
}
STEPS = (
    ("Proveedor", "Archivo y columnas"),
    ("Tienda", "Comparación de SKU"),
    ("Categorías", "Correspondencias"),
    ("Selección", "Lote de productos"),
    ("Exportación", "CSV para WooCommerce"),
)


def _render_styles():
    st.markdown(
        """
        <style>
        .block-container {max-width: 1120px; padding-top: 2.2rem; padding-bottom: 4rem;}
        .wizard-eyebrow {color: #64748b; font-size: .78rem; font-weight: 700;
            letter-spacing: .11em; text-transform: uppercase; margin-bottom: .35rem;}
        .wizard-subtitle {color: #64748b; margin-top: -.45rem; margin-bottom: 1.5rem;}
        .step-card {border: 1px solid #dbe2ea; border-radius: 12px; padding: 13px 14px;
            min-height: 82px; background: var(--secondary-background-color);}
        .step-card.active {border: 1px solid #2563eb; background: rgba(37,99,235,.08);}
        .step-card.done {border: 1px solid #16a34a;}
        .step-number {font-size: .72rem; color: #64748b; font-weight: 700;}
        .step-name {font-weight: 700; margin-top: 4px;}
        .step-description {font-size: .78rem; color: #64748b; margin-top: 2px;}
        .section-kicker {color: #64748b; font-size: .78rem; font-weight: 700;
            letter-spacing: .08em; text-transform: uppercase;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_stepper(active_step, provider_confirmed):
    columns = st.columns(len(STEPS))
    for index, (name, description) in enumerate(STEPS):
        state_class = "active" if index + 1 == active_step else ""
        if index == 0 and provider_confirmed:
            state_class = "done" if active_step > 1 else "active"
        number = "✓" if index == 0 and provider_confirmed and active_step > 1 else f"0{index + 1}"
        with columns[index]:
            st.markdown(
                f'<div class="step-card {state_class}">'
                f'<div class="step-number">ETAPA {number}</div>'
                f'<div class="step-name">{name}</div>'
                f'<div class="step-description">{description}</div>'
                "</div>",
                unsafe_allow_html=True,
            )


def _render_provider_step():
    st.markdown('<div class="wizard-eyebrow">Etapa 1 de 5</div>', unsafe_allow_html=True)
    st.header("Conectemos el catálogo del proveedor")
    st.markdown(
        '<p class="wizard-subtitle">Cargá la lista de precios y confirmá cómo identificar cada producto. '
        "Todavía no se modifica ni se importa nada.</p>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Archivo CSV del proveedor",
        type=["csv"],
        help="Se procesa localmente. El archivo original no se modifica.",
        key="wizard_provider_upload",
    )
    if uploaded is None:
        st.info("Cargá un archivo CSV para configurar el proveedor.")
        return

    file_bytes = uploaded.getvalue()
    try:
        initial_inspection = inspect_provider_file(file_bytes, uploaded.name)
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        st.error(f"No se pudo interpretar el CSV: {exc}")
        return

    profile_default = initial_inspection["profile"]
    top_left, top_right = st.columns([1, 1])
    with top_left:
        profile = st.selectbox(
            "Perfil del proveedor",
            options=("NB", "Genérico"),
            index=("NB", "Genérico").index(profile_default),
            key=f"wizard_profile_{initial_inspection['file_hash'][:12]}",
            help="El prefijo NB- sugiere el perfil NB. Podés corregirlo si el archivo pertenece a otro proveedor.",
        )
    with top_right:
        labels = list(DELIMITER_OPTIONS)
        detected_label = next(
            (label for label, value in DELIMITER_OPTIONS.items()
             if value == initial_inspection["detected_delimiter"]),
            labels[0],
        )
        delimiter_label = st.selectbox(
            "Separador del archivo",
            options=labels,
            index=labels.index(detected_label),
            key=f"wizard_delimiter_{initial_inspection['file_hash'][:12]}",
        )
    delimiter = DELIMITER_OPTIONS[delimiter_label]

    try:
        inspection = inspect_provider_file(
            file_bytes,
            uploaded.name,
            delimiter=delimiter,
            profile=profile,
        )
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        st.error(f"No se pudo interpretar el CSV: {exc}")
        return

    headers = inspection["headers"]
    rows = inspection["rows"]
    ignored_empty_columns = inspection["ignored_empty_columns"]
    st.caption(
        f"**{uploaded.name}** · {len(rows):,} filas · {len(headers)} columnas útiles"
    )
    if ignored_empty_columns:
        st.warning(
            f"Se ignorarán {ignored_empty_columns} columna(s) sin encabezado y completamente vacía(s). "
            "El archivo original permanece intacto."
        )

    st.markdown("#### Vista previa")
    preview_columns = headers[: min(6, len(headers))]
    st.dataframe(
        [{header: row.get(header, "") for header in preview_columns} for row in rows[:5]],
        hide_index=True,
        use_container_width=True,
    )

    st.divider()
    st.markdown("#### Identificación de columnas")
    st.caption(
        "Las sugerencias se basan en los encabezados. Revisalas antes de confirmar; "
        "el sistema no completa campos obligatorios con la primera columna disponible."
    )
    suggestions = inspection["suggestions"]
    fields = (
        ("sku", "SKU", True),
        ("name", "Nombre del producto", True),
        ("category", "Categoría de origen", True),
        ("price", "Precio del proveedor", True),
        ("stock", "Stock (opcional)", False),
    )
    mapping = {}
    field_columns = st.columns(2)
    for index, (field, label, required) in enumerate(fields):
        with field_columns[index % 2]:
            placeholder = "— Seleccionar columna —"
            options = [placeholder] + headers
            suggested = suggestions[field]
            default_index = headers.index(suggested) + 1 if suggested in headers else 0
            selected = st.selectbox(
                label + (" *" if required else ""),
                options=options,
                index=default_index,
                key=f"wizard_{field}_{profile}_{inspection['file_hash'][:12]}",
            )
            mapping[field] = None if selected == placeholder else selected
            if suggested:
                st.caption(f"Sugerencia: {suggested}")
            elif required:
                st.caption("Sin sugerencia automática. Seleccioná la columna manualmente.")

    valid, mapping_error = validate_provider_mapping(mapping)
    if not valid:
        st.warning(mapping_error)
    else:
        st.success("Asignación completa. Confirmá que cada columna representa el dato indicado.")

    if mapping.get("stock"):
        st.info(
            f"Se usará **{mapping['stock']}** para evaluar disponibilidad. "
            "Los valores vacíos, inválidos o sin stock positivo pasarán a revisión."
        )
    else:
        st.warning(
            "No se asignó una columna de stock. Por seguridad, todos los productos "
            "quedarán en revisión y no serán seleccionables ni exportables."
        )

    fingerprint = provider_mapping_fingerprint(
        inspection["file_hash"], delimiter, profile, mapping
    )
    confirmed = st.session_state.get("wizard_provider_confirmation") == fingerprint
    action_col, status_col = st.columns([1, 2])
    with action_col:
        if st.button(
            "Confirmar proveedor",
            type="primary",
            use_container_width=True,
            disabled=not valid,
        ):
            try:
                confirmed_data = confirm_provider_setup(inspection, mapping)
            except (ValueError, TypeError) as exc:
                st.error(f"No se pudo confirmar la configuración: {exc}")
                return
            st.session_state["wizard_provider_confirmation"] = confirmed_data[
                "mapping_fingerprint"
            ]
            st.session_state["wizard_provider_data"] = confirmed_data
            st.rerun()
    with status_col:
        if confirmed:
            st.success("Proveedor confirmado. Podés continuar a la etapa Tienda.")
        else:
            st.caption("La configuración queda confirmada solo después de presionar el botón.")

    if confirmed:
        if st.button("Continuar a Tienda →", use_container_width=True):
            st.session_state["wizard_step"] = 2
            st.rerun()

def _render_store_placeholder():
    provider = st.session_state.get("wizard_provider_data", {})
    st.markdown('<div class="wizard-eyebrow">Etapa 2 de 5</div>', unsafe_allow_html=True)
    st.header("Conectá la referencia de tu tienda")
    st.markdown(
        '<p class="wizard-subtitle">En esta etapa vamos a comparar los SKU del proveedor '
        "con una exportación de productos de WooCommerce.</p>",
        unsafe_allow_html=True,
    )
    st.info("La etapa Tienda es la siguiente en construcción. La configuración del proveedor ya quedó guardada.")
    if provider:
        st.markdown("**Proveedor confirmado**")
        st.write(f"Archivo: {provider['filename']}")
        st.write(f"Perfil: {provider['profile']}")
        st.write(f"SKU: {provider['mapping']['sku']}")
        st.write(f"Nombre: {provider['mapping']['name']}")
        st.write(f"Categoría: {provider['mapping']['category']}")
        st.write(f"Precio: {provider['mapping']['price']}")
        st.write(
            "Stock: "
            + (provider["mapping"]["stock"] or "Sin columna, revisión general")
        )
    if st.button("← Volver a Proveedor"):
        st.session_state["wizard_step"] = 1
        st.rerun()


def _provider_is_confirmed():
    provider = st.session_state.get("wizard_provider_data")
    confirmation = st.session_state.get("wizard_provider_confirmation")
    if not provider:
        return False
    expected = provider_mapping_fingerprint(
        provider["file_hash"],
        provider["delimiter"],
        provider["profile"],
        provider["mapping"],
    )
    return confirmation == expected


def render_wizard():
    """Render the guided five-stage application shell and the active stage."""
    _render_styles()
    st.title("WooCommerce Catalog Toolkit")
    st.markdown(
        '<p class="wizard-subtitle">Prepará catálogos de proveedores para importar productos '
        "a WooCommerce, con revisión antes de exportar.</p>",
        unsafe_allow_html=True,
    )

    provider_confirmed = _provider_is_confirmed()
    active_step = st.session_state.setdefault("wizard_step", 1)
    if active_step > 1 and not provider_confirmed:
        st.session_state["wizard_step"] = 1
        active_step = 1

    _render_stepper(active_step, provider_confirmed)
    st.write("")
    if active_step == 1:
        _render_provider_step()
    elif active_step == 2:
        _render_store_placeholder()
    else:
        st.session_state["wizard_step"] = 2
        _render_store_placeholder()
