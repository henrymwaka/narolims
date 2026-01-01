from __future__ import annotations

from typing import Iterable, Optional

from .models import ConfigPack, LabPackAssignment, WorkflowPackDefinition, RolePackDefinition, SchemaPackItem
from lims_core.labs.models import LaboratoryProfile


def get_effective_packs(lab_profile: LaboratoryProfile, *, kind: Optional[str] = None) -> Iterable[ConfigPack]:
    qs = (
        LabPackAssignment.objects
        .select_related("pack")
        .filter(laboratory_profile=lab_profile, is_enabled=True, pack__is_published=True)
        .order_by("priority", "pack__code")
    )
    if kind:
        qs = qs.filter(pack__kind=kind)
    return [a.pack for a in qs]


def get_effective_schema_schemas(lab_profile: LaboratoryProfile):
    packs = get_effective_packs(lab_profile, kind=ConfigPack.KIND_SCHEMA)
    items = (
        SchemaPackItem.objects
        .select_related("schema", "pack")
        .filter(pack__in=packs)
        .order_by("pack__code", "order", "id")
    )
    return items


def get_effective_workflows(lab_profile: LaboratoryProfile, object_kind: str):
    packs = get_effective_packs(lab_profile, kind=ConfigPack.KIND_WORKFLOW)
    defs = (
        WorkflowPackDefinition.objects
        .select_related("pack")
        .filter(pack__in=packs, object_kind=object_kind, is_active=True)
        .order_by("pack__code", "code", "version")
    )
    return defs


def get_effective_roles(lab_profile: LaboratoryProfile):
    packs = get_effective_packs(lab_profile, kind=ConfigPack.KIND_ROLE)
    defs = (
        RolePackDefinition.objects
        .select_related("pack")
        .filter(pack__in=packs, is_active=True)
        .order_by("pack__code", "code", "version")
    )
    return defs
