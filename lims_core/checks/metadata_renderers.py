# lims_core/checks/metadata_renderers.py

from django.core.checks import Error, register
from django.template.loader import get_template

from lims_core.metadata.models import MetadataField
from lims_core.metadata.renderers import get_field_renderer
from lims_core.metadata.renderer_contract import validate_renderer_contract


@register()
def check_metadata_renderers(app_configs, **kwargs):
    """
    Django system check for metadata renderer coverage and contract compliance.
    """
    errors = []

    field_types = (
        MetadataField.objects
        .values_list("field_type", flat=True)
        .distinct()
    )

    for field_type in field_types:
        renderer = get_field_renderer(field_type)

        # 1. Template existence
        try:
            get_template(renderer)
        except Exception as exc:
            errors.append(
                Error(
                    f"Renderer template not loadable for field_type '{field_type}'",
                    hint=str(exc),
                    id="lims_core.E001",
                )
            )
            continue

        # 2. Renderer contract
        contract_errors = validate_renderer_contract(renderer)
        for err in contract_errors:
            errors.append(
                Error(
                    f"Renderer contract violation for field_type '{field_type}'",
                    hint=err,
                    id="lims_core.E002",
                )
            )

    return errors
