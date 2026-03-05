# lims_core/services/intake.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from lims_core.models.core import Laboratory, Project, SampleBatch, Sample, Experiment


class IntakeError(Exception):
    pass


class ScopeError(IntakeError):
    pass


class InvariantError(IntakeError):
    pass


def _require_lab_scope(*, user, laboratory_id: int, allowed_lab_ids: Sequence[int]) -> None:
    if user.is_staff or user.is_superuser:
        return
    if int(laboratory_id) not in set(int(x) for x in allowed_lab_ids):
        raise ScopeError("Laboratory not in scope")


def _tokenize_code(value: str, max_len: int = 16, fallback: str = "X") -> str:
    import re

    code_re = re.compile(r"[^A-Za-z0-9]+")
    if value is None:
        return fallback
    v = code_re.sub("", str(value).strip().upper())
    if not v:
        return fallback
    return v[:max_len]


def _generate_batch_code(*, lab: Laboratory, project: Project) -> str:
    """
    Stable, human-readable, collision-resistant batch code.

    Format:
      <LABCODE>-<PROJCODE>-BATCH-YYYYMMDD-####

    Example:
      NARL-SOILS-BGEN250121-BATCH-20260121-0001
    """
    date_part = timezone.localdate().strftime("%Y%m%d")
    lab_code = _tokenize_code(getattr(lab, "code", None) or "LAB", max_len=18, fallback="LAB")
    proj_code = _tokenize_code(getattr(project, "code", None) or "PROJ", max_len=18, fallback="PROJ")
    prefix = f"{lab_code}-{proj_code}-BATCH-{date_part}"

    existing = (
        SampleBatch.objects.filter(batch_code__startswith=prefix + "-")
        .values_list("batch_code", flat=True)
    )

    max_seq = 0
    for bc in existing:
        parts = str(bc).split("-")
        tail = parts[-1] if parts else ""
        if tail.isdigit():
            max_seq = max(max_seq, int(tail))

    return f"{prefix}-{(max_seq + 1):04d}"


@dataclass(frozen=True)
class ProjectCreateSpec:
    name: str
    description: str = ""
    laboratory_id: int = 0
    created_by_user_id: Optional[int] = None


@dataclass(frozen=True)
class BatchCreateSpec:
    laboratory_id: int
    project_id: int
    collected_at: Optional[timezone.datetime] = None
    collected_by: str = ""
    collection_site: str = ""
    client_name: str = ""
    notes: str = ""
    batch_code: str = ""  # optional override


@dataclass(frozen=True)
class SampleCreateSpec:
    project_id: int
    batch_id: int
    experiment_id: Optional[int] = None
    sample_type: str = ""
    name: str = ""
    subgroup: str = ""
    external_id: str = ""
    sample_id: str = ""  # optional override; blank triggers generator


@transaction.atomic
def create_project(*, spec: ProjectCreateSpec) -> Project:
    if not spec.laboratory_id:
        raise ValidationError("laboratory_id is required")

    lab = Laboratory.objects.select_related("institute").get(id=spec.laboratory_id)

    p = Project(
        laboratory=lab,
        name=(spec.name or "").strip(),
        description=(spec.description or "").strip(),
    )
    if spec.created_by_user_id:
        p.created_by_id = spec.created_by_user_id

    p.full_clean()
    p.save()
    return p


@transaction.atomic
def create_batch(*, spec: BatchCreateSpec) -> SampleBatch:
    lab = Laboratory.objects.get(id=spec.laboratory_id)
    project = Project.objects.select_related("laboratory").get(id=spec.project_id)

    if project.laboratory_id != lab.id:
        raise InvariantError("Batch laboratory must match project laboratory")

    bc = (spec.batch_code or "").strip()
    if not bc:
        bc = _generate_batch_code(lab=lab, project=project)

    b = SampleBatch(
        laboratory=lab,
        project=project,
        batch_code=bc,
        collected_at=spec.collected_at,
        collected_by=(spec.collected_by or "").strip(),
        collection_site=(spec.collection_site or "").strip(),
        client_name=(spec.client_name or "").strip(),
        notes=(spec.notes or "").strip(),
    )

    b.full_clean()
    b.save()
    return b


@transaction.atomic
def create_samples(*, specs: list[SampleCreateSpec]) -> list[Sample]:
    if not specs:
        return []

    project_id = specs[0].project_id
    batch_id = specs[0].batch_id

    project = Project.objects.select_related("laboratory").get(id=project_id)
    batch = SampleBatch.objects.select_related("laboratory", "project").get(id=batch_id)

    if batch.project_id != project.id:
        raise InvariantError("Samples must be created in a batch that belongs to the same project")

    created: list[Sample] = []
    for s in specs:
        if s.project_id != project_id or s.batch_id != batch_id:
            raise InvariantError("All samples in this call must target the same project and batch")

        exp = None
        if s.experiment_id:
            exp = Experiment.objects.select_related("project").get(id=s.experiment_id)
            if exp.project_id != project.id:
                raise InvariantError("Sample experiment must belong to the same project")

        # Important:
        # - Sample.sample_id is commonly blank=False at model layer.
        # - The model.save() generator populates sample_id when falsy.
        # - Therefore validate with exclude=["sample_id"] before saving.
        sid = (s.sample_id or "").strip()

        obj = Sample(
            project=project,
            batch=batch,
            experiment=exp,
            sample_type=(s.sample_type or "").strip(),
            name=(s.name or "").strip(),
            subgroup=(s.subgroup or "").strip(),
            external_id=(s.external_id or "").strip(),
            sample_id=sid,  # blank is allowed here, generator will fill in save()
        )

        obj.full_clean(exclude=["sample_id"])
        obj.save()
        created.append(obj)

    return created


# ============================================================
# UI-friendly wrappers (so views do not reimplement intake logic)
# ============================================================

@transaction.atomic
def create_intake_batch_for_project(*, project: Project, batch_spec: BatchCreateSpec) -> SampleBatch:
    """
    UI wrapper:
    - caller provides a Project instance
    - laboratory is derived from project
    - uses the same invariants as create_batch
    """
    if not project or not project.pk:
        raise ValidationError("project is required")
    if not project.laboratory_id:
        raise InvariantError("Project has no laboratory assigned")

    spec = BatchCreateSpec(
        laboratory_id=int(project.laboratory_id),
        project_id=int(project.id),
        collected_at=batch_spec.collected_at,
        collected_by=batch_spec.collected_by,
        collection_site=batch_spec.collection_site,
        client_name=batch_spec.client_name,
        notes=batch_spec.notes,
        batch_code=batch_spec.batch_code,
    )
    return create_batch(spec=spec)


@transaction.atomic
def bulk_create_samples_for_batch(*, batch: SampleBatch, rows: list[dict]) -> list[Sample]:
    """
    UI wrapper:
    - rows: [{sample_id?, name?, sample_type?, subgroup?, external_id?, experiment_id?}, ...]
    - sample_id may be blank and model will generate
    """
    if not batch or not batch.pk:
        raise ValidationError("batch is required")
    if not batch.project_id:
        raise InvariantError("Batch must be tied to a project")

    specs: list[SampleCreateSpec] = []
    for r in rows or []:
        sid = (r.get("sample_id") or "").strip()
        nm = (r.get("name") or "").strip()
        st = (r.get("sample_type") or "").strip()
        subgroup = (r.get("subgroup") or "").strip()
        external_id = (r.get("external_id") or "").strip()
        exp_id = r.get("experiment_id") or None

        if not (sid or nm or st or subgroup or external_id or exp_id):
            continue

        specs.append(
            SampleCreateSpec(
                project_id=int(batch.project_id),
                batch_id=int(batch.id),
                experiment_id=int(exp_id) if exp_id else None,
                sample_type=st,
                name=nm,
                subgroup=subgroup,
                external_id=external_id,
                sample_id=sid,
            )
        )

    return create_samples(specs=specs)


@transaction.atomic
def create_project_with_intake_batch(
    *,
    project_spec: ProjectCreateSpec,
    batch_spec_overrides: Optional[BatchCreateSpec] = None,
    placeholder_count: int = 0,
    placeholder_sample_type: str = "",
    placeholder_name_prefix: str = "Placeholder",
) -> dict:
    """
    Wizard-friendly: create Project, then create one intake batch and optional N placeholder samples.
    """
    project = create_project(spec=project_spec)

    bspec = BatchCreateSpec(
        laboratory_id=project.laboratory_id,
        project_id=project.id,
        collected_at=(batch_spec_overrides.collected_at if batch_spec_overrides else None),
        collected_by=(batch_spec_overrides.collected_by if batch_spec_overrides else ""),
        collection_site=(batch_spec_overrides.collection_site if batch_spec_overrides else ""),
        client_name=(batch_spec_overrides.client_name if batch_spec_overrides else ""),
        notes=(batch_spec_overrides.notes if batch_spec_overrides else ""),
        batch_code=(batch_spec_overrides.batch_code if batch_spec_overrides else ""),
    )
    batch = create_batch(spec=bspec)

    samples: list[Sample] = []
    n = int(placeholder_count or 0)
    if n > 0:
        if n > 5000:
            n = 5000
        stype = (placeholder_sample_type or "").strip()
        specs = [
            SampleCreateSpec(
                project_id=project.id,
                batch_id=batch.id,
                experiment_id=None,
                sample_type=stype,
                name=f"{placeholder_name_prefix} {i + 1}",
                sample_id="",
            )
            for i in range(n)
        ]
        samples = create_samples(specs=specs)

    return {
        "project": project,
        "batch": batch,
        "samples": samples,
    }
