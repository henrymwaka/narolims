# lims_core/services/workflow.py
from __future__ import annotations

"""
Single-object workflow services.

IMPORTANT:
- Bulk transitions live ONLY in: lims_core/services/workflow_bulk.py
- This module must NOT contain bulk logic.

AUTHORITATIVE WRITES:
- Status updates + WorkflowTransition rows + SLA alert resolution are handled by:
  lims_core/workflows/transition_service.py (transition_object)

This module is responsible for:
- validate_transition()
- required_roles() gating
- WorkflowEvent audit entry
- SLA evaluation for the new state
"""

from typing import Dict, Any

from django.db import transaction
from django.utils import timezone

from lims_core.models import Sample, Experiment
from lims_core.models.workflow_event import WorkflowEvent
from lims_core.workflows import validate_transition, required_roles, normalize_role
from lims_core.workflows.transition_service import transition_object
from lims_core.workflows.sla_monitor import check_sla_breach


MODEL_REGISTRY = {
    "sample": Sample,
    "experiment": Experiment,
}


def _event_supports_laboratory() -> bool:
    try:
        WorkflowEvent._meta.get_field("laboratory")
        return True
    except Exception:
        return False


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
    Execute a single workflow transition with validation and audit.

    Persistence is delegated to transition_object(), which is the only place
    allowed to:
      - change status
      - create WorkflowTransition rows
      - resolve open SLA alerts for the prior state
    """
    kind = (kind or "").strip().lower()
    target_status = (target_status or "").strip().upper()
    actor_role = normalize_role(actor_role)

    if kind not in MODEL_REGISTRY:
        raise ValueError(f"Unknown workflow kind: {kind}")

    old_status = (getattr(instance, "status", "") or "").strip().upper()

    # 1) Validate transition legality
    validate_transition(kind, old_status, target_status)

    # 2) Role enforcement
    # Superusers bypass role checks
    if not (actor and getattr(actor, "is_superuser", False)):
        allowed = required_roles(kind, old_status, target_status) or set()
        if allowed and actor_role not in allowed:
            raise PermissionError(
                f"Role '{actor_role}' not permitted for {old_status} -> {target_status}"
            )

    now = timezone.now()
    can_set_lab = _event_supports_laboratory()

    # 3) Atomic transition + audit + SLA evaluation
    with transaction.atomic():
        result = transition_object(
            kind=kind,
            object_id=instance.pk,
            to_status=target_status,
            performed_by=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
            now=now,
        )

        if result.get("changed"):
            evt_kwargs = dict(
                kind=kind,
                object_id=instance.pk,
                from_status=result.get("from_status") or old_status,
                to_status=result.get("to_status") or target_status,
                performed_by=actor,
                role=actor_role,
                comment=(comment or ""),
            )
            if can_set_lab:
                evt_kwargs["laboratory"] = getattr(instance, "laboratory", None)

            WorkflowEvent.objects.create(**evt_kwargs)

            # Evaluate SLA for the new current state
            check_sla_breach(kind=kind, object_id=instance.pk, user=actor)

    return {
        "id": instance.pk,
        "from": result.get("from_status") or old_status,
        "to": result.get("to_status") or target_status,
        "changed": bool(result.get("changed")),
        "alerts_resolved": int(result.get("alerts_resolved") or 0),
        "transition_id": result.get("transition_id"),
    }
