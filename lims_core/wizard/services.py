# lims_core/wizard/services.py

from django.db import transaction
from django.utils import timezone

from lims_core.models.core import Project, Sample, Laboratory
from lims_core.models import AuditLog
from lims_core.models.drafts import ProjectDraft


def _safe_audit(*, user, laboratory, action: str, meta: dict | None = None):
    """
    Best-effort audit logging without making the wizard brittle.
    """
    try:
        AuditLog.objects.create(
            user=user,
            laboratory=laboratory,
            action=action,
        )
    except Exception:
        return


def _new_sample_id(*, lab_code: str, stamp: str, project_id: int, seq: int) -> str:
    """
    Generates a deterministic, unique sample_id for placeholder creation.
    Keeps it short and stable. Example:
    S-LAB-20260102-000123-001
    """
    return f"S-{lab_code}-{stamp}-{project_id:06d}-{seq:03d}"


@transaction.atomic
def apply_project_draft(*, draft: ProjectDraft, user):
    """
    Converts a draft into real system objects in a single atomic transaction.
    """
    payload = draft.payload or {}

    laboratory_id = payload.get("laboratory_id") or (draft.laboratory_id if draft.laboratory_id else None)
    if not laboratory_id:
        raise ValueError("Draft has no laboratory selected.")

    lab = Laboratory.objects.get(pk=laboratory_id)

    project_block = payload.get("project") or {}
    name = (project_block.get("name") or "").strip()
    description = (project_block.get("description") or "").strip()

    if not name:
        raise ValueError("Project name is required.")

    project = Project.objects.create(
        laboratory=lab,
        name=name,
        description=description,
        created_by=user,
        is_active=True,
    )

    samples_block = payload.get("samples") or {}
    create_placeholders = bool(samples_block.get("create_placeholders"))
    count = int(samples_block.get("count") or 0)
    sample_type = (samples_block.get("sample_type") or "test").strip() or "test"

    if create_placeholders and count > 0:
        lab_code = (getattr(lab, "code", None) or "LAB").strip() or "LAB"
        stamp = timezone.now().strftime("%Y%m%d")

        status_new = getattr(Sample, "STATUS_NEW", None) or "new"

        samples = []
        for i in range(1, count + 1):
            samples.append(
                Sample(
                    laboratory=lab,
                    project=project,
                    sample_type=sample_type,
                    status=status_new,
                    sample_id=_new_sample_id(
                        lab_code=lab_code,
                        stamp=stamp,
                        project_id=project.pk,
                        seq=i,
                    ),
                )
            )

        Sample.objects.bulk_create(samples)

    # mark applied
    draft.last_error = ""
    draft.mark_applied()

    _safe_audit(
        user=user,
        laboratory=lab,
        action="wizard.project.applied",
        meta={"project_id": project.pk, "draft_id": draft.pk, "applied_at": timezone.now().isoformat()},
    )

    return project
