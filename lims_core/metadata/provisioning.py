# lims_core/metadata/provisioning.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from lims_core.labs.models import LaboratoryProfile
from lims_core.metadata.models import MetadataSchema, MetadataField


# -------------------------------------------------------------------
# Configuration (no hardcoding of "NARO" or any specific institute)
# -------------------------------------------------------------------
DEFAULT_TEMPLATE_LAB_CODE = getattr(
    settings,
    "LIMS_METADATA_TEMPLATE_LAB_CODE",
    "NARL-GENERAL",  # safe default for your current deployment
)


@dataclass(frozen=True)
class TemplatePick:
    schema: MetadataSchema
    reason: str


def _get_template_profile() -> Optional[LaboratoryProfile]:
    """
    Template profile is configurable.
    If not found, fall back to any profile that has at least one active sample schema.
    """
    lp = (
        LaboratoryProfile.objects.select_related("laboratory")
        .filter(laboratory__code=DEFAULT_TEMPLATE_LAB_CODE)
        .first()
    )
    if lp:
        return lp

    # fallback: "any profile with schemas"
    return (
        LaboratoryProfile.objects.select_related("laboratory")
        .filter(metadata_schemas__is_active=True)
        .distinct()
        .first()
    )


def _version_sort_key(v: str):
    """
    Sort versions robustly:
      "v1" < "v2"
      "1.0" < "1.1" < "2.0"
    Non-numeric tokens are handled safely.
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


def _pick_source_schema(
    *,
    template_profile: LaboratoryProfile,
    applies_to: str,
    analysis_context=None,
) -> TemplatePick:
    """
    Choose the best source schema from template profile:
    Prefer analysis_context match, else context=None.
    Prefer highest version, then newest.
    """
    qs = MetadataSchema.objects.filter(
        laboratory_profile=template_profile,
        applies_to=applies_to,
        is_active=True,
    )

    if analysis_context is not None:
        qs = qs.filter(Q(analysis_context=analysis_context) | Q(analysis_context__isnull=True))
    else:
        qs = qs.filter(analysis_context__isnull=True)

    schemas = list(qs)
    if not schemas:
        raise RuntimeError(
            f"No template schema available for applies_to={applies_to} "
            f"under template lab={template_profile.laboratory.code}"
        )

    schemas.sort(
        key=lambda s: (_version_sort_key(s.version), s.created_at),
        reverse=True,
    )
    return TemplatePick(schema=schemas[0], reason=f"template={template_profile.laboratory.code}")


def _clone_schema_with_fields(
    *,
    source: MetadataSchema,
    target_profile: LaboratoryProfile,
    lock_after: bool,
) -> MetadataSchema:
    """
    Clone schema + fields into target profile.

    IMPORTANT:
    If lock_after=True, we create it unlocked, create fields, then lock it.
    This avoids the "Cannot add fields to locked schema" error.
    """
    with transaction.atomic():
        new_schema = MetadataSchema.objects.create(
            laboratory_profile=target_profile,
            analysis_context=source.analysis_context,
            code=source.code,
            version=source.version,
            name=source.name,
            description=source.description,
            applies_to=source.applies_to,
            is_active=True,
            is_locked=False,  # always start unlocked so we can copy fields
            lock_reason="",
        )

        src_fields = list(MetadataField.objects.filter(schema=source).order_by("order", "id"))
        for f in src_fields:
            MetadataField.objects.create(
                schema=new_schema,
                order=f.order,
                code=f.code,
                label=f.label,
                field_type=f.field_type,
                required=f.required,
                help_text=f.help_text,
                choices=f.choices,
            )

        if lock_after:
            # lock in a separate save so field creation is finished
            new_schema.is_locked = True
            new_schema.lock_reason = "Auto-provisioned baseline (accreditation mode)"
            new_schema.save()

        return new_schema


def _normalize_active_defaults(
    *,
    profile: LaboratoryProfile,
    applies_to: str,
    analysis_context=None,
) -> None:
    """
    If multiple active schemas exist for the same (profile, applies_to, context),
    keep the preferred one:
      - First prefer profile.schema_code/schema_version if present
      - Else keep latest by version+created
    Deactivate the rest.
    """
    qs = MetadataSchema.objects.filter(
        laboratory_profile=profile,
        applies_to=applies_to,
        is_active=True,
    )
    if analysis_context is None:
        qs = qs.filter(analysis_context__isnull=True)
    else:
        qs = qs.filter(Q(analysis_context=analysis_context) | Q(analysis_context__isnull=True))

    schemas = list(qs)
    if len(schemas) <= 1:
        return

    preferred = None
    # try profile default
    for s in schemas:
        if (s.code == profile.schema_code) and (str(s.version) == str(profile.schema_version)):
            preferred = s
            break

    if preferred is None:
        schemas.sort(key=lambda s: (_version_sort_key(s.version), s.created_at), reverse=True)
        preferred = schemas[0]

    # deactivate all others
    for s in schemas:
        if s.id == preferred.id:
            continue
        MetadataSchema.objects.filter(pk=s.pk).update(is_active=False)


def ensure_baseline_schemas_for_profile(
    *,
    profile: LaboratoryProfile,
    apply_normalization: bool = True,
) -> dict:
    """
    Guarantee each lab profile has at least one active schema for:
      - sample
      - batch
      - experiment

    Uses a template profile (configurable) to clone schema+fields if missing.

    Returns a small report dict suitable for logs.
    """
    if not profile or not profile.pk:
        return {"ok": False, "reason": "no-profile"}

    template_profile = _get_template_profile()
    if template_profile is None:
        return {"ok": False, "reason": "no-template-profile"}

    lock_after = bool(profile.accreditation_mode)

    report = {"ok": True, "lab": profile.laboratory.code, "actions": []}

    for applies_to in ("sample", "batch", "experiment"):
        exists = MetadataSchema.objects.filter(
            laboratory_profile=profile,
            applies_to=applies_to,
            is_active=True,
        ).exists()

        if not exists:
            pick = _pick_source_schema(
                template_profile=template_profile,
                applies_to=applies_to,
                analysis_context=None,
            )
            _clone_schema_with_fields(source=pick.schema, target_profile=profile, lock_after=lock_after)
            report["actions"].append(f"cloned:{applies_to}({pick.schema.code}:{pick.schema.version})")
        else:
            report["actions"].append(f"exists:{applies_to}")

        if apply_normalization:
            _normalize_active_defaults(profile=profile, applies_to=applies_to, analysis_context=None)

    return report
