# lims_core/workflows/metadata_gating.py

from typing import Dict, List

from django.core.exceptions import ValidationError

from lims_core.metadata.validators import validate_metadata_payload
from lims_core.metadata.models import MetadataValue


# ------------------------------------------------------------
# Import-safe resolver (CRITICAL under Gunicorn)
# ------------------------------------------------------------
try:
    from lims_core.metadata.schema_resolver import resolve_metadata_schema
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

    OPTION C (Accreditation-aware):

    - accreditation_mode = True
        * schema MUST exist
        * schema MUST be locked
        * missing or invalid metadata → BLOCK

    - accreditation_mode = False
        * schema must exist
        * missing or invalid metadata → BLOCK
        * unlocked schema allowed

    This function MUST NEVER crash the UI.
    Workflow enforcement happens downstream based on "allowed".
    """

    # --------------------------------------------------------
    # Resolver unavailable → fail OPEN (UI-safe)
    # --------------------------------------------------------
    if resolve_metadata_schema is None:
        return {
            "allowed": True,
            "missing_fields": [],
            "invalid_fields": [],
            "warning": "metadata schema resolver unavailable",
        }

    # --------------------------------------------------------
    # Resolve schema safely
    # --------------------------------------------------------
    try:
        schema = resolve_metadata_schema(
            laboratory_profile=laboratory.profile,
            applies_to=object_type,
        )
    except ValidationError as exc:
        # No schema found → metadata not required
        return {
            "allowed": True,
            "missing_fields": [],
            "invalid_fields": [],
            "warning": str(exc),
        }
    except Exception:
        return {
            "allowed": True,
            "missing_fields": [],
            "invalid_fields": [],
            "warning": "metadata schema resolver error",
        }

    # --------------------------------------------------------
    # Accreditation hard enforcement
    # --------------------------------------------------------
    if laboratory.profile.accreditation_mode and not schema.is_locked:
        return {
            "allowed": False,
            "missing_fields": [],
            "invalid_fields": [],
            "warning": (
                f"Unlocked metadata schema '{schema.code}:{schema.version}' "
                "cannot be used in accreditation mode."
            ),
        }

    # --------------------------------------------------------
    # Build payload from persisted MetadataValue
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Validate payload
    # --------------------------------------------------------
    result = validate_metadata_payload(
        schema=schema,
        payload=payload,
    )

    missing_fields: List[str] = result.get("missing_fields", [])
    invalid_fields: List[str] = result.get("invalid_fields", [])

    return {
        "allowed": not (missing_fields or invalid_fields),
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
    }
