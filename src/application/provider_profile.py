"""Provider identification and column-mapping application rules."""

from src.application.column_mapping import suggest_column


PROVIDER_PROFILES = {
    "NB": {
        "sku": ("CODIGO", "CÓDIGO", "SKU", "CODE"),
        "name": ("DETALLE", "NOMBRE", "NAME", "DESCRIPTION"),
        "category": ("CATEGORIA", "CATEGORÍA", "CATEGORY"),
        "price": ("PRECIO PESOS CON IVA",),
        "stock": ("STOCK", "EXISTENCIA", "CANTIDAD"),
    },
    "Genérico": {
        "sku": ("SKU", "CODIGO", "CÓDIGO", "CODE", "PRODUCT_CODE"),
        "name": ("NOMBRE", "NAME", "DETALLE", "DESCRIPTION", "PRODUCT_NAME"),
        "category": ("CATEGORIA", "CATEGORÍA", "CATEGORY", "PRODUCT_CATEGORY"),
        "price": ("PRECIO", "PRICE", "PRECIO_VENTA", "SALE_PRICE"),
        "stock": ("STOCK", "EXISTENCIA", "QUANTITY", "CANTIDAD"),
    },
}


def detect_provider_profile(filename):
    """Suggest NB only for filenames carrying its stable NB- prefix."""
    return "NB" if str(filename).strip().upper().startswith("NB-") else "Genérico"


def suggest_provider_columns(headers, profile):
    """Return suggested source column names; unresolved fields remain None."""
    aliases = PROVIDER_PROFILES.get(profile)
    if aliases is None:
        raise ValueError(f"Unknown provider profile: {profile}")
    suggestions = {}
    for field, field_aliases in aliases.items():
        index = suggest_column(headers, field_aliases)
        suggestions[field] = headers[index] if index is not None else None
    return suggestions


def validate_provider_mapping(mapping):
    """Validate required provider columns without silently choosing fallbacks."""
    required = ("sku", "name", "category", "price")
    missing = [field for field in required if not mapping.get(field)]
    if missing:
        return False, "Faltan asignar: " + ", ".join(missing) + "."
    required_values = [mapping[field] for field in required]
    if len(set(required_values)) != len(required_values):
        return False, "SKU, nombre, categoría y precio deben usar columnas diferentes."
    stock = mapping.get("stock")
    if stock and stock in required_values:
        return False, "La columna de stock debe ser distinta de los campos obligatorios."
    return True, None


def stock_review_policy(mapping):
    """Return the safe review policy when the provider has no stock column."""
    return "validate_column" if mapping.get("stock") else "review_all"


def provider_mapping_fingerprint(file_hash, delimiter, profile, mapping):
    """Build a stable signature for a confirmed provider configuration."""
    return (
        file_hash,
        delimiter,
        profile,
        tuple(
            (field, mapping.get(field))
            for field in ("sku", "name", "category", "price", "stock")
        ),
    )
