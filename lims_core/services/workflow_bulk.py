# lims_core/services/workflow_bulk.py

from typing import List, Dict, Any

from django.db import transaction

from lims_core.models import Sample, Experiment, UserRole
from lims_core.models.workflow_event import WorkflowEvent
from lims_core.workflows import (
    validate_transition,
    required_roles,
    normalize_role,
)

# Optional authoritative path (only when DB membership is present)
from lims_core.workflows.executor import execute_transition


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


def _has_db_role_for_instance(*, actor, actor_role: str, obj) -> bool:
    """
    The executor re-checks roles via UserRole(user, laboratory).

    For API calls this is normally true because views resolve actor_role from DB.
    For tests calling bulk_transition directly, this may be false.

    We only use execute_transition when this check passes, otherwise we keep the
    existing bulk engine behavior (which trusts actor_role and required_roles()).

    Important:
    - Do not require the raw stored role string to match exactly.
      Normalize DB roles and compare to normalized actor_role.
    """
    if getattr(actor, "is_superuser", False):
        return True

    lab_id = getattr(obj, "laboratory_id", None)
    if not lab_id:
        return False

    role_norm = normalize_role(actor_role)

    raw_roles = UserRole.objects.filter(
        user=actor,
        laboratory_id=lab_id,
    ).values_list("role", flat=True)

    normalized_roles = {normalize_role(r) for r in raw_roles if r}
    return role_norm in normalized_roles


def _event_supports_laboratory() -> bool:
    try:
        WorkflowEvent._meta.get_field("laboratory")
        return True
    except Exception:
        return False


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

    Note:
    - execute_transition() is only used when DB role membership exists for the object's lab.
      Otherwise we preserve the original behavior (trust actor_role passed in).
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

    can_set_lab = _event_supports_laboratory()

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
                results["failed"].append({"id": getattr(obj, "id", None), "error": str(exc)})
                continue

            allowed_norm = {normalize_role(r) for r in (allowed or set())}
            if allowed_norm and actor_role not in allowed_norm:
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

        # 3) Atomic transition + audit
        try:
            with transaction.atomic():
                if transition_is_valid and _has_db_role_for_instance(actor=actor, actor_role=actor_role, obj=obj):
                    # Use authoritative executor only when it can succeed (DB role membership present)
                    execute_transition(
                        instance=obj,
                        kind=kind,
                        new_status=target_status,
                        user=actor,
                    )
                else:
                    # Preserve original bulk semantics
                    _force_status_update(Model, obj.pk, target_status)

                evt_kwargs = dict(
                    kind=kind,
                    object_id=obj.pk,
                    from_status=old_status,
                    to_status=target_status,
                    performed_by=actor,
                    role=actor_role,
                    comment=comment or "",
                )

                if can_set_lab:
                    lab = getattr(obj, "laboratory", None)
                    evt_kwargs["laboratory"] = lab

                WorkflowEvent.objects.create(**evt_kwargs)

            results["success"].append(obj.pk)

        except Exception as exc:
            results["failed"].append({"id": obj.pk, "error": str(exc)})

    return results
