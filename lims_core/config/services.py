from __future__ import annotations

from typing import Iterable, Optional, Sequence

from django.conf import settings

from lims_core.labs.models import LaboratoryProfile

from .models import (
    ConfigPack,
    LabPackAssignment,
    WorkflowPackDefinition,
    RolePackDefinition,
    SchemaPackItem,
)


def get_effective_packs(
    lab_profile: LaboratoryProfile,
    *,
    kind: Optional[str] = None,
    include_unpublished: bool = False,
) -> Sequence[ConfigPack]:
    """
    Return packs effectively applied to this lab profile, ordered by priority then code.

    Rules:
    - only enabled assignments are considered
    - by default only published packs are returned (include_unpublished=False)
    - kind can be one of: schema, workflow, role, ui
    """
    qs = (
        LabPackAssignment.objects.select_related("pack")
        .filter(laboratory_profile=lab_profile, is_enabled=True)
        .order_by("priority", "pack__code")
    )

    if not include_unpublished:
        qs = qs.filter(pack__is_published=True)

    if kind:
        qs = qs.filter(pack__kind=kind)

    return [a.pack for a in qs]


def get_effective_schema_schemas(lab_profile: LaboratoryProfile):
    packs = get_effective_packs(lab_profile, kind=ConfigPack.KIND_SCHEMA)
    items = (
        SchemaPackItem.objects.select_related("schema", "pack")
        .filter(pack__in=packs)
        .order_by("pack__code", "order", "id")
    )
    return items


def get_effective_workflows(lab_profile: LaboratoryProfile, object_kind: str):
    packs = get_effective_packs(lab_profile, kind=ConfigPack.KIND_WORKFLOW)
    defs = (
        WorkflowPackDefinition.objects.select_related("pack")
        .filter(pack__in=packs, object_kind=object_kind, is_active=True)
        .order_by("pack__code", "code", "version")
    )
    return defs


def get_effective_roles(lab_profile: LaboratoryProfile):
    packs = get_effective_packs(lab_profile, kind=ConfigPack.KIND_ROLE)
    defs = (
        RolePackDefinition.objects.select_related("pack")
        .filter(pack__in=packs, is_active=True)
        .order_by("pack__code", "code", "version")
    )
    return defs


def get_effective_ui_packs(lab_profile: LaboratoryProfile) -> Sequence[ConfigPack]:
    """
    UI packs represent UI/wizard behavior and templates.

    This function mirrors the schema/workflow/role pattern so UI can be driven
    by lab assignments instead of hard-coded settings.
    """
    return get_effective_packs(lab_profile, kind=ConfigPack.KIND_UI)


def resolve_active_pack_code_for_lab(
    lab_profile: Optional[LaboratoryProfile],
    *,
    kind: str = ConfigPack.KIND_UI,
    default_code: Optional[str] = None,
) -> str:
    """
    Resolve the active pack code for a lab profile.

    Priority:
    1) first effective pack of the requested kind assigned to the lab (priority order)
    2) default_code (if provided)
    3) settings.CONFIG_PACK_DEFAULT
    4) "default"
    """
    if lab_profile is not None:
        packs = get_effective_packs(lab_profile, kind=kind)
        if packs:
            return (packs[0].code or "").strip() or "default"

    if default_code:
        return default_code.strip() or "default"

    return (getattr(settings, "CONFIG_PACK_DEFAULT", None) or "default").strip() or "default"


def load_wizard_config_for_lab_profile(lab_profile: Optional[LaboratoryProfile]):
    """
    Bridge between DB-selected pack code and filesystem YAML wizard config.

    Returns WizardConfig from lims_core.config_packs.loader if available, else None.

    This is intentionally defensive:
    - if PyYAML is not installed, or wizard.yaml is missing, it returns None
    - callers should fall back to hard-coded templates
    """
    pack_code = resolve_active_pack_code_for_lab(lab_profile, kind=ConfigPack.KIND_UI)

    try:
        from lims_core.config_packs.loader import load_pack_wizard  # type: ignore
    except Exception:
        return None

    try:
        return load_pack_wizard(pack_code=pack_code)
    except Exception:
        return None
