# lims_core/metadata/validators.py

from typing import Dict, Any, List

from django.core.exceptions import ValidationError

from lims_core.metadata.models import MetadataField, MetadataValue
from lims_core.metadata.resolver import resolve_metadata_schema


# ============================================================
# Payload-level validation (used by APIs / UI forms)
# ============================================================

def validate_metadata_payload(*, schema, payload: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Validate a metadata payload against a schema.

    Returns:
    {
        "missing_fields": [field_code, ...],
        "invalid_fields": [field_code, ...],
    }
    """

    missing_fields: List[str] = []
    invalid_fields: List[str] = []

    for field in schema.fields.all():
        code = field.code
        value = payload.get(code)

        # Required field missing
        if field.required and (value is None or value == ""):
            missing_fields.append(code)
            continue

        # Skip empty optional fields
        if value in (None, ""):
            continue

        # Type validation
        try:
            if field.field_type == "number":
                float(value)
            elif field.field_type == "boolean":
                if not isinstance(value, bool):
                    raise ValueError
            elif field.field_type == "date":
                # Accept date-like values already parsed upstream
                pass
            else:
                # Text / choice fields
                str(value)
        except Exception:
            invalid_fields.append(code)

    return {
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
    }


# ============================================================
# Object-level enforcement (used by workflow transitions)
# ============================================================

def enforce_required_metadata(*, obj, object_type: str) -> None:
    """
    Enforce presence of required metadata values for a persisted object.

    This is called during workflow transitions, not during registration.
    """

    schemas = resolve_metadata_schema(
        laboratory=obj.laboratory,
        object_type=object_type,
        analysis_context=getattr(obj, "analysis_context", None),
    )

    if not schemas.exists():
        return  # No metadata defined, nothing to enforce

    required_fields = MetadataField.objects.filter(
        schema__in=schemas,
        required=True,
    )

    missing_labels: List[str] = []

    for field in required_fields:
        exists = MetadataValue.objects.filter(
            schema_field=field,
            object_type=object_type,
            object_id=obj.pk,
        ).exists()

        if not exists:
            missing_labels.append(field.label)

    if missing_labels:
        raise ValidationError(
            {
                "metadata": (
                    "Missing required metadata: "
                    + ", ".join(missing_labels)
                )
            }
        )
