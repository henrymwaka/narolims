from django.template.loader import get_template
from django.core.exceptions import ImproperlyConfigured

from lims_core.metadata.models import MetadataField
from lims_core.metadata.renderers import (
    FIELD_RENDERERS,
    FALLBACK_RENDERER,
)


def validate_renderer_coverage(*, allow_fallback: bool = True) -> None:
    """
    Validate that all metadata field types have a renderer
    and that all renderer templates exist.

    Runs at startup. Fails fast on misconfiguration.
    """

    # 1. Collect field types actually used in DB
    field_types_in_use = (
        MetadataField.objects
        .values_list("field_type", flat=True)
        .distinct()
    )

    missing_renderers = []
    missing_templates = []

    # 2. Check renderer mapping coverage
    for field_type in field_types_in_use:
        renderer = FIELD_RENDERERS.get(field_type)

        if not renderer:
            if allow_fallback:
                renderer = FALLBACK_RENDERER
            else:
                missing_renderers.append(field_type)
                continue

        # 3. Check template existence
        try:
            get_template(renderer)
        except Exception:
            missing_templates.append((field_type, renderer))

    # 4. Raise configuration errors
    if missing_renderers:
        raise ImproperlyConfigured(
            "Metadata renderer missing for field types: "
            + ", ".join(sorted(missing_renderers))
        )

    if missing_templates:
        details = ", ".join(
            f"{ft} → {tpl}" for ft, tpl in missing_templates
        )
        raise ImproperlyConfigured(
            "Metadata renderer templates not found: " + details
        )
