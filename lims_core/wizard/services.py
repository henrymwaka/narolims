# lims_core/wizard/services.py

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from lims_core.models.core import Laboratory
from lims_core.models import AuditLog
from lims_core.models.drafts import ProjectDraft

from lims_core.services.intake import (
    create_project_with_intake_batch,
    ProjectCreateSpec,
    BatchCreateSpec,
)


def _safe_audit(*, user, laboratory, action: str, meta: dict | None = None):
    """
    Best-effort audit logging without making the wizard brittle.
    """
    try:
        AuditLog.objects.create(
            user=user,
            laboratory=laboratory,
            action=action,
            details=meta or {},
        )
    except Exception:
        return


@transaction.atomic
def apply_project_draft_result(*, draft: ProjectDraft, user) -> dict:
    """
    Full apply: returns a dict containing created objects.

    Returns:
      {
        "project": Project,
        "batch": SampleBatch,
        "samples": list[Sample]
      }
    """
    payload = draft.payload or {}

    laboratory_id = payload.get("laboratory_id") or (draft.laboratory_id if draft.laboratory_id else None)
    if not laboratory_id:
        raise ValueError("Draft has no laboratory selected.")

    lab = Laboratory.objects.get(pk=int(laboratory_id))

    project_block = payload.get("project") or {}
    name = (project_block.get("name") or "").strip()
    description = (project_block.get("description") or "").strip()

    if not name:
        raise ValueError("Project name is required.")

    samples_block = payload.get("samples") or {}
    create_placeholders = bool(samples_block.get("create_placeholders"))
    count = int(samples_block.get("count") or 0)
    sample_type = (samples_block.get("sample_type") or "").strip()

    if not create_placeholders:
        count = 0

    if count < 0:
        count = 0
    if count > 5000:
        count = 5000

    result = create_project_with_intake_batch(
        project_spec=ProjectCreateSpec(
            name=name,
            description=description,
            laboratory_id=int(lab.id),
            created_by_user_id=getattr(user, "id", None),
        ),
        batch_spec_overrides=BatchCreateSpec(
            laboratory_id=int(lab.id),
            project_id=0,  # ignored by intake service overrides builder
        ),
        placeholder_count=count,
        placeholder_sample_type=sample_type,
        placeholder_name_prefix="Placeholder",
    )

    project = result["project"]
    batch = result["batch"]
    created_samples = result.get("samples") or []

    draft.last_error = ""
    draft.mark_applied()

    _safe_audit(
        user=user,
        laboratory=lab,
        action="wizard.project.applied",
        meta={
            "draft_id": draft.pk,
            "project_id": project.pk,
            "project_code": getattr(project, "code", None),
            "laboratory_id": lab.id,
            "intake_batch_id": batch.id,
            "intake_batch_code": getattr(batch, "batch_code", None),
            "placeholders_requested": bool(create_placeholders),
            "placeholders_created": len(created_samples),
            "sample_type": sample_type,
            "applied_at": timezone.now().isoformat(),
        },
    )

    return {"project": project, "batch": batch, "samples": created_samples}


@transaction.atomic
def apply_project_draft(*, draft: ProjectDraft, user):
    """
    Backwards compatible API: returns ONLY the Project.
    Tests and older callers rely on this.
    """
    return apply_project_draft_result(draft=draft, user=user)["project"]
