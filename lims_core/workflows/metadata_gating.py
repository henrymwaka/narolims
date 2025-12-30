# lims_core/workflows/metadata_gating.py

from typing import Dict, List

from lims_core.metadata.validators import validate_metadata_payload
from lims_core.metadata.models import MetadataValue

# ------------------------------------------------------------
# Import-safe resolver (CRITICAL under Gunicorn)
# ------------------------------------------------------------
try:
    from lims_core.metadata.resolver import resolve_metadata_schema
except ImportError:
    resolve_metadata_schema = None


def check_metadata_gate(
    *,
    laboratory,
    object_type: str,
    object_id: int,
) -> Dict:
    """
    Enforce metadata completeness and validity before workflow transitions
    and for UI completeness indicators.

    Returns a structured decision dict:

    {
        "allowed": bool,
        "missing_fields": list[str],
        "invalid_fields": list[str],
        "warning": optional str
    }

    This function MUST NEVER raise ImportError or crash the UI.
    """

    # --------------------------------------------------------
    # Resolver unavailable → fail OPEN (never block UI/workflow)
    # --------------------------------------------------------
    if resolve_metadata_schema is None:
        return {
            "allowed": True,
            "missing_fields": [],
            "invalid_fields": [],
            "warning": "metadata schema resolver unavailable",
        }

    # --------------------------------------------------------
    # Resolver execution must never crash UI
    # --------------------------------------------------------
    try:
        schemas = resolve_metadata_schema(
            laboratory=laboratory,
            object_type=object_type,
        )
    except Exception:
        return {
            "allowed": True,
            "missing_fields": [],
            "invalid_fields": [],
            "warning": "metadata schema resolver error",
        }

    # No schemas defined → metadata not required
    if not schemas:
        return {
            "allowed": True,
            "missing_fields": [],
            "invalid_fields": [],
        }

    missing_fields: List[str] = []
    invalid_fields: List[str] = []

    for schema in schemas:
        # --------------------------------------------
        # Build payload from persisted MetadataValue
        # --------------------------------------------
        values = (
            MetadataValue.objects
            .filter(
                schema_field__schema=schema,
                object_type=object_type,
                object_id=object_id,
            )
            .select_related("schema_field")
        )

        payload = {
            mv.schema_field.code: mv.get_value()
            for mv in values
        }

        result = validate_metadata_payload(
            schema=schema,
            payload=payload,
        )

        missing_fields.extend(result.get("missing_fields", []))
        invalid_fields.extend(result.get("invalid_fields", []))

    return {
        "allowed": not (missing_fields or invalid_fields),
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
    }
