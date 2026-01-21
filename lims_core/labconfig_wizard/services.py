from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from lims_core.models.core import Laboratory
from lims_core.models import AuditLog
from lims_core.labs.models import LaboratoryProfile
from lims_core.config.models import LabPackAssignment, ConfigPack
from lims_core.models.drafts import LabConfigDraft


def _safe_audit(*, user, laboratory, action: str):
    try:
        AuditLog.objects.create(
            user=user,
            laboratory=laboratory,
            action=action,
        )
    except Exception:
        return


@transaction.atomic
def apply_labconfig_draft(*, draft: LabConfigDraft, user):
    payload = draft.payload or {}

    laboratory_id = payload.get("laboratory_id") or (draft.laboratory_id if draft.laboratory_id else None)
    if not laboratory_id:
        raise ValueError("Draft has no laboratory selected.")

    lab = Laboratory.objects.get(pk=laboratory_id)

    profile_block = payload.get("profile") or {}

    lab_type = (profile_block.get("lab_type") or "").strip()
    if not lab_type:
        raise ValueError("lab_type is required.")

    description = (profile_block.get("description") or "").strip()
    accreditation_mode = bool(profile_block.get("accreditation_mode"))

    schema_code = (profile_block.get("schema_code") or "").strip()
    if not schema_code:
        raise ValueError("schema_code is required.")

    schema_version = (profile_block.get("schema_version") or "v1").strip() or "v1"

    default_analysis_context_id = profile_block.get("default_analysis_context_id") or None
    if default_analysis_context_id in ("", "null", "None"):
        default_analysis_context_id = None

    profile, _created = LaboratoryProfile.objects.get_or_create(
        laboratory=lab,
        defaults={
            "lab_type": lab_type,
            "description": description,
            "accreditation_mode": accreditation_mode,
            "schema_code": schema_code,
            "schema_version": schema_version,
            "default_analysis_context_id": default_analysis_context_id,
            "is_active": True,
        },
    )

    # Update existing profile deterministically
    profile.lab_type = lab_type
    profile.description = description
    profile.accreditation_mode = accreditation_mode
    profile.schema_code = schema_code
    profile.schema_version = schema_version
    profile.default_analysis_context_id = default_analysis_context_id
    profile.is_active = True
    profile.save()

    # Assignments: replace in full (deterministic)
    assignments = payload.get("assignments") or []
    clean_rows = []

    for row in assignments:
        if not row:
            continue
        pack_id = row.get("pack_id")
        if not pack_id:
            continue

        try:
            pack_id = int(pack_id)
        except Exception:
            continue

        is_enabled = bool(row.get("is_enabled", True))

        try:
            priority = int(row.get("priority") or 0)
        except Exception:
            priority = 0

        if priority < 0:
            priority = 0
        if priority > 1000000:
            priority = 1000000

        clean_rows.append((pack_id, is_enabled, priority))

    # Optional safety: only allow published packs
    published_pack_ids = set(
        ConfigPack.objects.filter(is_published=True).values_list("id", flat=True)
    )
    clean_rows = [r for r in clean_rows if r[0] in published_pack_ids]

    LabPackAssignment.objects.filter(laboratory_profile=profile).delete()

    objs = []
    for pack_id, is_enabled, priority in clean_rows:
        objs.append(
            LabPackAssignment(
                laboratory_profile=profile,
                pack_id=pack_id,
                is_enabled=is_enabled,
                priority=priority,
            )
        )
    if objs:
        LabPackAssignment.objects.bulk_create(objs)

    draft.last_error = ""
    draft.mark_applied()

    _safe_audit(
        user=user,
        laboratory=lab,
        action="wizard.labconfig.applied",
    )

    return profile
