FIELD_RENDERERS = {
    "text": "lims_core/metadata/field_text.html",
    "number": "lims_core/metadata/field_number.html",
    "date": "lims_core/metadata/field_date.html",
    "boolean": "lims_core/metadata/field_boolean.html",
    "choice": "lims_core/metadata/field_choice.html",
}

FALLBACK_RENDERER = "lims_core/metadata/field_unknown.html"


def get_field_renderer(field_type: str) -> str:
    return FIELD_RENDERERS.get(field_type, FALLBACK_RENDERER)
