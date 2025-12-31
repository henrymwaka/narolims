# lims_core/metadata/schema_resolver.py

from typing import Optional

from django.core.exceptions import ValidationError
from django.db.models import Q

from lims_core.metadata.models import MetadataSchema
from lims_core.labs.models import LaboratoryProfile


def resolve_metadata_schema(
    *,
    laboratory_profile: LaboratoryProfile,
    applies_to: str,
    analysis_context=None,
    allow_unlocked: Optional[bool] = None,
) -> MetadataSchema:
    """
    Resolve the effective metadata schema for a given lab and object type.

    Accreditation behavior (OPTION C):
    - If laboratory_profile.accreditation_mode == True:
        → ONLY locked schemas are allowed
    - If accreditation_mode == False:
        → latest active schema is allowed (locked or not)

    Parameters
    ----------
    laboratory_profile : LaboratoryProfile
        The laboratory profile requesting metadata.
    applies_to : str
        Object type (e.g. "sample", "batch", "experiment").
    analysis_context : AnalysisContext | None
        Optional analysis context override.
    allow_unlocked : bool | None
        Optional override (advanced use only).
        If None, defaults to NOT accreditation_mode.

    Returns
    -------
    MetadataSchema

    Raises
    ------
    ValidationError
        If no valid schema can be resolved under policy.
    """

    if not laboratory_profile:
        raise ValidationError("Laboratory profile is required to resolve metadata schema.")

    # --------------------------------------------------
    # Accreditation policy resolution
    # --------------------------------------------------
    if allow_unlocked is None:
        allow_unlocked = not laboratory_profile.accreditation_mode

    # --------------------------------------------------
    # Base queryset
    # --------------------------------------------------
    qs = MetadataSchema.objects.filter(
        laboratory_profile=laboratory_profile,
        applies_to=applies_to,
        is_active=True,
    )

    # --------------------------------------------------
    # Analysis context preference
    # --------------------------------------------------
    if analysis_context is not None:
        qs = qs.filter(
            Q(analysis_context=analysis_context) |
            Q(analysis_context__isnull=True)
        )
    else:
        qs = qs.filter(analysis_context__isnull=True)

    # --------------------------------------------------
    # Accreditation enforcement
    # --------------------------------------------------
    if not allow_unlocked:
        qs = qs.filter(is_locked=True)

    # --------------------------------------------------
    # Ordering strategy
    # --------------------------------------------------
    # Highest version wins, then newest created
    qs = qs.order_by("-version", "-created_at")

    schema = qs.first()

    if not schema:
        mode = "ACCREDITED" if laboratory_profile.accreditation_mode else "NON-ACCREDITED"
        ctx = getattr(analysis_context, "code", "default")
        raise ValidationError(
            f"No valid metadata schema found "
            f"(lab={laboratory_profile.laboratory.code}, "
            f"mode={mode}, applies_to={applies_to}, "
            f"context={ctx})"
        )

    return schema
