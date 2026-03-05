# lims_core/metadata/schema_resolver.py

from __future__ import annotations

from typing import Optional

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet

from lims_core.metadata.models import MetadataSchema
from lims_core.labs.models import LaboratoryProfile


def _version_sort_key(v: str):
    """
    Safe version sorting for strings like:
      - "v1", "v2"
      - "1", "1.0", "1.1", "2.0"
    Unknown formats sort lowest.
    """
    raw = (v or "").strip().lower()
    if raw.startswith("v"):
        raw = raw[1:]
    parts = raw.split(".")
    out = []
    for p in parts:
        try:
            out.append(int(p))
        except Exception:
            out.append(-1)
    return tuple(out)


def _base_queryset(
    *,
    laboratory_profile: LaboratoryProfile,
    applies_to: str,
    analysis_context=None,
) -> QuerySet:
    """
    Build the base queryset for schema resolution.

    Rules:
    - always restrict to: lab profile + applies_to + active
    - if analysis_context is provided:
        prefer exact context, but allow fallback to default (NULL)
      else:
        only default (NULL) context
    """
    qs = MetadataSchema.objects.filter(
        laboratory_profile=laboratory_profile,
        applies_to=applies_to,
        is_active=True,
    )

    if analysis_context is not None:
        qs = qs.filter(
            Q(analysis_context=analysis_context) |
            Q(analysis_context__isnull=True)
        )
    else:
        qs = qs.filter(analysis_context__isnull=True)

    return qs


def _apply_accreditation_policy(
    *,
    qs: QuerySet,
    allow_unlocked: bool,
) -> QuerySet:
    """
    If allow_unlocked is False (accredited mode), only locked schemas may be selected.
    """
    if not allow_unlocked:
        qs = qs.filter(is_locked=True)
    return qs


def resolve_metadata_schema(
    *,
    laboratory_profile: LaboratoryProfile,
    applies_to: str,
    analysis_context=None,
    allow_unlocked: Optional[bool] = None,
) -> MetadataSchema:
    """
    Resolve the effective metadata schema for a given lab and object type.

    Behavior:
    - If accreditation_mode == True:
        -> ONLY locked schemas are allowed
    - If accreditation_mode == False:
        -> active schema is allowed (locked or unlocked)

    Stable default:
    - If analysis_context is None (default context), resolver first tries to honor
      LaboratoryProfile.schema_code + schema_version as the default schema selection.

    Fallback selection:
    - Prefer higher version (parsed safely)
    - Then newest created_at (id as final tiebreaker)
    - If analysis_context is provided, prefer exact context over NULL
    """

    if not laboratory_profile:
        raise ValidationError("Laboratory profile is required to resolve metadata schema.")

    # --------------------------------------------------
    # Accreditation policy resolution
    # --------------------------------------------------
    if allow_unlocked is None:
        allow_unlocked = not laboratory_profile.accreditation_mode

    # --------------------------------------------------
    # Base queryset (active, scoped by lab + applies_to + context rules)
    # --------------------------------------------------
    qs = _base_queryset(
        laboratory_profile=laboratory_profile,
        applies_to=applies_to,
        analysis_context=analysis_context,
    )
    qs = _apply_accreditation_policy(qs=qs, allow_unlocked=allow_unlocked)

    # --------------------------------------------------
    # 1) Preferred default selection for NULL analysis_context
    # --------------------------------------------------
    if analysis_context is None:
        default_code = (laboratory_profile.schema_code or "").strip()
        default_ver = (laboratory_profile.schema_version or "").strip()

        if default_code and default_ver:
            preferred = qs.filter(
                analysis_context__isnull=True,
                code=default_code,
                version=default_ver,
            ).order_by("-created_at", "-id").first()

            if preferred:
                return preferred

    # --------------------------------------------------
    # 2) Fallback selection (version-aware, deterministic)
    # --------------------------------------------------
    candidates = list(qs)
    if not candidates:
        mode = "ACCREDITED" if laboratory_profile.accreditation_mode else "NON-ACCREDITED"
        ctx = getattr(analysis_context, "code", "default")
        raise ValidationError(
            f"No valid metadata schema found "
            f"(lab={laboratory_profile.laboratory.code}, "
            f"mode={mode}, applies_to={applies_to}, "
            f"context={ctx})"
        )

    def ctx_rank(s: MetadataSchema) -> int:
        if analysis_context is None:
            return 0
        return 1 if (s.analysis_context_id == getattr(analysis_context, "id", None)) else 0

    candidates.sort(
        key=lambda s: (
            ctx_rank(s),                 # prefer exact context when applicable
            _version_sort_key(s.version),# prefer higher version
            s.created_at,                # then newest created
            s.id,                        # final stable tiebreaker
        ),
        reverse=True,
    )

    return candidates[0]
