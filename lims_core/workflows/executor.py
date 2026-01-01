# lims_core/workflows/executor.py

from __future__ import annotations

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from lims_core.models import UserRole
from lims_core.workflows import (
    validate_transition,
    allowed_next_states,
    required_roles,
    normalize_role,
)
from lims_core.workflows.sla_monitor import check_sla_breach
from lims_core.workflows.transition_service import transition_object


def execute_transition(*, instance, kind: str, new_status: str, user):
    """
    Authoritative transition entrypoint used by UI/API code paths.

    This function enforces:
      - terminal lock
      - transition legality
      - role checks

    It delegates persistence to transition_object(), which is the only place
    allowed to write status and create WorkflowTransition rows, and to resolve
    open SLA alerts for the prior state.
    """
    kind = (kind or "").strip().lower()
    current = (getattr(instance, "status", None) or "").strip().upper()
    target = (new_status or "").strip().upper()

    if not kind:
        raise ValidationError({"status": "kind is required."})
    if not target:
        raise ValidationError({"status": "new_status is required."})

    # 1) Terminal state lock
    if not allowed_next_states(kind, current):
        raise ValidationError(
            {"status": f"{kind.capitalize()} is in terminal state '{current}' and cannot be modified."}
        )

    # 2) Validate transition legality
    try:
        validate_transition(kind=kind, old=current, new=target)
    except ValueError as e:
        raise ValidationError({"status": str(e)})

    # No-op transition
    if current == target:
        return {
            "changed": False,
            "kind": kind,
            "object_id": instance.pk,
            "from_status": current,
            "to_status": target,
            "alerts_resolved": 0,
            "transition_id": None,
        }

    # 3) Role enforcement (lab-scoped)
    required = {normalize_role(r) for r in (required_roles(kind, current, target) or set())}

    if required:
        if not user or not getattr(user, "is_authenticated", False):
            raise PermissionDenied(
                "You must be authenticated to perform this transition."
            )

        if getattr(user, "is_superuser", False):
            user_roles = {"ADMIN"}
        else:
            raw_roles = UserRole.objects.filter(
                user=user,
                laboratory=instance.laboratory,
            ).values_list("role", flat=True)
            user_roles = {normalize_role(r) for r in raw_roles}

        if not user_roles.intersection(required):
            raise PermissionDenied(
                "You do not have the required role to transition "
                f"{kind} from {current} to {target}."
            )

    # 4) Persist via the single authoritative writer
    result = transition_object(
        kind=kind,
        object_id=instance.pk,
        to_status=target,
        performed_by=user if (user and getattr(user, "is_authenticated", False)) else None,
        now=timezone.now(),
    )

    # 5) SLA evaluation for current state
    # This runs after the transition is stored so the monitor can use the new timeline.
    check_sla_breach(kind=kind, object_id=instance.pk, user=user)

    return result
