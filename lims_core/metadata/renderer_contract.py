# lims_core/metadata/renderer_contract.py

from django.template import TemplateDoesNotExist
from django.template.loader import get_template

REQUIRED_CONTEXT_KEYS = {
    "field",
    "field_code",
    "field_value",
    "errors",
    "schema_error",
}


def _get_template_source(template_name: str) -> str:
    """
    Safely extracts template source across Django loaders.
    Returns empty string if unavailable.
    """
    try:
        template = get_template(template_name)
    except TemplateDoesNotExist:
        return ""

    origin = getattr(template, "origin", None)
    if origin and hasattr(origin, "loader"):
        try:
            return origin.loader.get_contents(origin)
        except Exception:
            return ""

    return ""


def validate_renderer_contract(template_name: str) -> list[str]:
    """
    Validates that a renderer template declares the required REQUIRES contract.

    Returns a list of human-readable errors.
    Empty list means OK.
    """
    errors: list[str] = []

    source = _get_template_source(template_name)

    if not source:
        return [f"{template_name}: unable to read template source"]

    if "REQUIRES:" not in source:
        return [f"{template_name}: missing REQUIRES contract declaration"]

    declared: set[str] = set()

    for line in source.splitlines():
        line = line.strip()
        if line.startswith("- "):
            declared.add(line[2:].strip())

    missing = REQUIRED_CONTEXT_KEYS - declared
    extra = declared - REQUIRED_CONTEXT_KEYS

    if missing:
        errors.append(
            f"{template_name}: missing required keys: {', '.join(sorted(missing))}"
        )

    if extra:
        errors.append(
            f"{template_name}: declares unknown keys: {', '.join(sorted(extra))}"
        )

    return errors
