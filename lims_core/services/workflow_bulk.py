# lims_core/services/workflow_bulk.py

from __future__ import annotations

from typing import List, Dict, Any

from django.db import transaction

from lims_core.models import Sample, Experiment
from lims_core.models.workflow_event import WorkflowEvent
from lims_core.workflows import (
    validate_transition,
    required_roles,
    normalize_role,
)
from lims_core.workflows.transition_service import transition_object
from lims_core.workflows.sla_monitor import check_sla_breach


# ---------------------------------------------------------------------
# MODEL REGISTRY
# ---------------------------------------------------------------------

MODEL_REGISTRY = {
    "sample": Sample,
    "experiment": Experiment,
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _event_supports_laboratory() -> bool:
    try:
        WorkflowEvent._meta.get_field("laboratory")
        return True
    except Exception:
        return False


def _create_workflow_event(
    *,
    can_set_lab: bool,
    obj,
    kind: str,
    from_status: str,
    to_status: str,
    performed_by,
    actor_role: str,
    comment: str,
) -> None:
    evt_kwargs = dict(
        kind=kind,
        object_id=obj.pk,
        from_status=from_status,
        to_status=to_status,
        performed_by=performed_by,
        role=actor_role,
        comment=comment or "",
    )
    if can_set_lab:
        evt_kwargs["laboratory"] = getattr(obj, "laboratory", None)

    WorkflowEvent.objects.create(**evt_kwargs)


def _force_transition(
    *,
    kind: str,
    obj,
    to_status: str,
    performed_by,
    actor_role: str,
    comment: str,
    can_set_lab: bool,
) -> Dict[str, Any]:
    """
    Admin-only forced transition path.

    Policy:
    - Even when validate_transition fails, we still write using transition_object()
      so that status update, WorkflowTransition, and alert resolution remain centralized.
    - We still evaluate SLA for the new state.
    - We always create a WorkflowEvent audit record when a change occurs.
    """
    resp = transition_object(
        kind=kind,
        object_id=obj.pk,
        to_status=to_status,
        performed_by=performed_by if getattr(performed_by, "is_authenticated", False) else None,
    )

    if resp.get("changed"):
        check_sla_breach(kind=kind, object_id=obj.pk, user=performed_by)

        _create_workflow_event(
            can_set_lab=can_set_lab,
            obj=obj,
            kind=kind,
            from_status=resp.get("from_status") or "",
            to_status=resp.get("to_status") or to_status,
            performed_by=performed_by,
            actor_role=actor_role,
            comment=comment,
        )

    resp["forced"] = True
    return resp


# ---------------------------------------------------------------------
# BULK WORKFLOW TRANSITION
# ---------------------------------------------------------------------

def bulk_transition(
    *,
    kind: str,
    objects: List,
    target_status: str,
    actor,
    actor_role: str,
    comment: str = "",
) -> Dict[str, Any]:
    """
    Canonical bulk workflow transition engine.

    Design goals:
    - No dead weight: bulk enforces policy, transition_service performs mechanics.
    - Non-admin: strict validate_transition + required_roles
    - Admin/superuser: may force invalid transitions, but still writes full audit trail
    - Every successful change writes WorkflowTransition, resolves SLA alerts, evaluates SLA, and records WorkflowEvent
    - Never raises for user input errors (per-object failures reported)
    """
    kind = (kind or "").strip().lower()
    target_status = (target_status or "").strip().upper()
    actor_role = normalize_role(actor_role)

    is_admin = bool(actor_role == "ADMIN" or getattr(actor, "is_superuser", False))

    if kind not in MODEL_REGISTRY:
        return {
            "success": [],
            "failed": [
                {"id": getattr(obj, "id", None), "error": f"Unknown workflow kind: {kind}"}
                for obj in objects
            ],
        }

    results: Dict[str, List] = {"success": [], "failed": []}
    can_set_lab = _event_supports_laboratory()

    for obj in objects:
        obj_id = getattr(obj, "pk", None) or getattr(obj, "id", None)
        old_status = (getattr(obj, "status", "") or "").strip().upper()

        # No-op counts as success
        if old_status == target_status:
            results["success"].append(obj_id)
            continue

        # 1) Validate transition legality (strict for non-admin, bypassable for admin)
        transition_is_valid = True
        try:
            validate_transition(kind, old_status, target_status)
        except Exception as exc:
            transition_is_valid = False
            if not is_admin:
                results["failed"].append({"id": obj_id, "error": str(exc)})
                continue

        # 2) Role enforcement (only for non-admin)
        if not is_admin:
            try:
                allowed = required_roles(kind, old_status, target_status) or set()
                allowed_norm = {normalize_role(r) for r in allowed if r}
            except Exception as exc:
                results["failed"].append({"id": obj_id, "error": str(exc)})
                continue

            if allowed_norm and actor_role not in allowed_norm:
                results["failed"].append(
                    {
                        "id": obj_id,
                        "error": f"Role '{actor_role}' not permitted for {old_status} -> {target_status}",
                    }
                )
                continue

        # 3) Apply transition atomically (per-object)
        try:
            with transaction.atomic():
                if transition_is_valid:
                    resp = transition_object(
                        kind=kind,
                        object_id=obj.pk,
                        to_status=target_status,
                        performed_by=actor if getattr(actor, "is_authenticated", False) else None,
                    )

                    if resp.get("changed"):
                        check_sla_breach(kind=kind, object_id=obj.pk, user=actor)

                        _create_workflow_event(
                            can_set_lab=can_set_lab,
                            obj=obj,
                            kind=kind,
                            from_status=resp.get("from_status") or old_status,
                            to_status=resp.get("to_status") or target_status,
                            performed_by=actor,
                            actor_role=actor_role,
                            comment=comment,
                        )
                else:
                    _force_transition(
                        kind=kind,
                        obj=obj,
                        to_status=target_status,
                        performed_by=actor,
                        actor_role=actor_role,
                        comment=comment,
                        can_set_lab=can_set_lab,
                    )

            results["success"].append(obj_id)

        except Exception as exc:
            results["failed"].append({"id": obj_id, "error": str(exc)})

    return results
