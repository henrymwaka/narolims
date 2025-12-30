# lims_core/metadata/resolver.py

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet, Case, When, Value, IntegerField
from django.core.exceptions import ValidationError

from lims_core.metadata.models import MetadataSchema
from lims_core.labs.models_analysis_context import AnalysisContext


def _coerce_laboratory_profile(obj: Any):
    """
    Resolve a LaboratoryProfile from supported inputs.
    """
    if obj is None:
        return None

    # Already a LaboratoryProfile-like object
    if hasattr(obj, "schema_code") and hasattr(obj, "schema_version"):
        return obj

    # Laboratory instance -> LaboratoryProfile
    return getattr(obj, "profile", None)


def resolve_metadata_schema(
    *,
    laboratory: Any,
    object_type: str,
    analysis_context: AnalysisContext | None = None,
) -> QuerySet:
    """
    Resolve metadata schemas using the following logic:

    1. ALWAYS include base schemas:
       - analysis_context IS NULL

    2. If a context is provided:
       - ALSO include schemas bound to that context

    Ordering rules (CRITICAL):
    - Context-specific schemas first
    - Base schemas second
    - Then by code, then version
    """

    object_type = (object_type or "").strip().lower()
    lab_profile = _coerce_laboratory_profile(laboratory)

    if not lab_profile or not object_type:
        return MetadataSchema.objects.none()

    # Base schemas (always apply)
    base_q = Q(
        laboratory_profile=lab_profile,
        applies_to=object_type,
        is_active=True,
        analysis_context__isnull=True,
    )

    # Context-specific schemas (optional)
    if analysis_context:
        context_q = Q(
            laboratory_profile=lab_profile,
            applies_to=object_type,
            is_active=True,
            analysis_context=analysis_context,
        )
        final_q = base_q | context_q
    else:
        final_q = base_q

    return (
        MetadataSchema.objects
        .filter(final_q)
        .annotate(
            # Context-specific schemas first (rank 0), base schemas after (rank 1)
            context_rank=Case(
                When(analysis_context__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .prefetch_related("fields")
        .order_by("context_rank", "code", "version")
    )


def resolve_single_schema(
    *,
    laboratory: Any,
    object_type: str,
    analysis_context: AnalysisContext | None = None,
) -> MetadataSchema:
    """
    Resolve exactly ONE active metadata schema.

    Raises ValidationError if:
    - No schema matches
    - More than one schema matches

    This guarantees deterministic schema binding
    and prevents silent metadata drift.
    """

    qs = resolve_metadata_schema(
        laboratory=laboratory,
        object_type=object_type,
        analysis_context=analysis_context,
    )

    count = qs.count()

    if count == 0:
        raise ValidationError(
            f"No active metadata schema found for object type '{object_type}'."
        )

    if count > 1:
        raise ValidationError(
            f"Multiple active metadata schemas found for object type '{object_type}'. "
            "Schema resolution must be unambiguous."
        )

    return qs.first()
