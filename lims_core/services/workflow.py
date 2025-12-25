from __future__ import annotations

"""
Single-object workflow services.

IMPORTANT:
- Bulk transitions are implemented ONLY in:
  lims_core/services/workflow_bulk.py

This module must NOT contain any bulk workflow logic.
"""

from typing import Dict, Any

from django.db import transaction

from lims_core.models import Sample, Experiment
from lims_core.models.workflow_event import WorkflowEvent
from lims_core.workflows import (
    validate_transition,
    required_roles,
    normalize_role,
)


# ---------------------------------------------------------------------
# MODEL REGISTRY (shared semantics)
# ---------------------------------------------------------------------

MODEL_REGISTRY = {
    "sample": Sample,
    "experiment": Experiment,
}


# ---------------------------------------------------------------------
# INTERNAL: HARD GUARD BYPASS (single-object use only)
# ---------------------------------------------------------------------

def _force_status_update(model, pk, new_status: str):
    """
    Force-update status without triggering workflow guards,
    save(), clean(), or signals.

    This is intentionally private and MUST NOT be used for bulk logic.
    """
    model.objects.filter(pk=pk).update(status=new_status)


# ---------------------------------------------------------------------
# SINGLE-OBJECT WORKFLOW TRANSITION
# ---------------------------------------------------------------------

def execute_transition(
    *,
    kind: str,
    instance,
    target_status: str,
    actor,
    actor_role: str,
    comment: str | None = None,
) -> Dict[str, Any]:
    """
    Execute a single workflow transition with full validation and audit.

    Bulk transitions MUST use:
    lims_core.services.workflow_bulk.bulk_transition
    """

    kind = (kind or "").strip().lower()
    target_status = (target_status or "").strip().upper()
    actor_role = normalize_role(actor_role)

    if kind not in MODEL_REGISTRY:
        raise ValueError(f"Unknown workflow kind: {kind}")

    old_status = (instance.status or "").strip().upper()

    # --------------------------------------------------
    # 1. Validate transition legality
    # --------------------------------------------------
    validate_transition(kind, old_status, target_status)

    # --------------------------------------------------
    # 2. Role enforcement
    # --------------------------------------------------
    allowed = required_roles(kind, old_status, target_status)
    if allowed and actor_role not in allowed:
        raise PermissionError(
            f"Role '{actor_role}' not permitted for "
            f"{old_status} -> {target_status}"
        )

    # --------------------------------------------------
    # 3. Atomic transition + audit
    # --------------------------------------------------
    with transaction.atomic():
        _force_status_update(instance.__class__, instance.pk, target_status)

        WorkflowEvent.objects.create(
            kind=kind,
            object_id=instance.pk,
            from_status=old_status,
            to_status=target_status,
            performed_by=actor,
            role=actor_role,
            comment=comment or "",
        )

    return {
        "id": instance.pk,
        "from": old_status,
        "to": target_status,
    }
