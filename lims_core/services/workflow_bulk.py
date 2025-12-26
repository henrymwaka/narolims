# lims_core/services/workflow_bulk.py

from typing import List, Dict, Any

from django.db import transaction

from lims_core.models import Sample, Experiment
from lims_core.models.workflow_event import WorkflowEvent
from lims_core.workflows import (
    validate_transition,
    required_roles,
    normalize_role,
)

# ---------------------------------------------------------------------
# MODEL REGISTRY
# ---------------------------------------------------------------------

MODEL_REGISTRY = {
    "sample": Sample,
    "experiment": Experiment,
}


# ---------------------------------------------------------------------
# INTERNAL: HARD GUARD BYPASS
# ---------------------------------------------------------------------

def _force_status_update(model, pk, new_status: str) -> None:
    """
    Force-update status without triggering WorkflowWriteGuardMixin.
    """
    model.objects.filter(pk=pk).update(status=new_status)


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

    - Never raises for user input errors
    - Enforces workflow legality and role permissions for non-admin roles
    - Allows ADMIN/superuser to force transitions (even if workflow says invalid)
    - Bypasses workflow guards safely
    - Records WorkflowEvent per successful transition
    """
    kind = (kind or "").strip().lower()
    target_status = (target_status or "").strip().upper()
    actor_role = normalize_role(actor_role)

    is_admin = bool(
        actor_role == "ADMIN"
        or getattr(actor, "is_superuser", False)
    )

    # --------------------------------------------------
    # Unknown workflow kind (graceful failure)
    # --------------------------------------------------
    if kind not in MODEL_REGISTRY:
        return {
            "success": [],
            "failed": [
                {
                    "id": getattr(obj, "id", None),
                    "error": f"Unknown workflow kind: {kind}",
                }
                for obj in objects
            ],
        }

    Model = MODEL_REGISTRY[kind]

    results: Dict[str, List] = {
        "success": [],
        "failed": [],
    }

    # --------------------------------------------------
    # Per-object processing
    # --------------------------------------------------
    for obj in objects:
        old_status = (getattr(obj, "status", "") or "").upper()

        # 1) Transition validation (strict for non-admin, bypassable for admin)
        try:
            validate_transition(kind, old_status, target_status)
            transition_is_valid = True
        except Exception as exc:
            transition_is_valid = False
            if not is_admin:
                results["failed"].append({"id": getattr(obj, "id", None), "error": str(exc)})
                continue

        # 2) Role enforcement (only if non-admin and transition is valid)
        if not is_admin:
            try:
                allowed = required_roles(kind, old_status, target_status)
            except Exception as exc:
                # Defensive: required_roles may validate too
                results["failed"].append({"id": getattr(obj, "id", None), "error": str(exc)})
                continue

            if allowed and actor_role not in [normalize_role(r) for r in allowed]:
                results["failed"].append(
                    {
                        "id": getattr(obj, "id", None),
                        "error": (
                            f"Role '{actor_role}' not permitted for "
                            f"{old_status} -> {target_status}"
                        ),
                    }
                )
                continue

        # 3) Atomic forced transition + audit (always records event on success)
        try:
            with transaction.atomic():
                _force_status_update(Model, obj.pk, target_status)

                WorkflowEvent.objects.create(
                    kind=kind,
                    object_id=obj.pk,
                    from_status=old_status,
                    to_status=target_status,
                    performed_by=actor,
                    role=actor_role,
                    comment=comment or "",
                )

            results["success"].append(obj.pk)

        except Exception as exc:
            results["failed"].append({"id": obj.pk, "error": str(exc)})

    return results
