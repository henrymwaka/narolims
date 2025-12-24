# lims_core/workflows/executor.py

from django.db import transaction

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from lims_core.models import WorkflowTransition, UserRole
from lims_core.workflows import (
    validate_transition,
    allowed_next_states,
    required_roles,
)

# SLA monitoring (post-transition)
from lims_core.workflows.sla_monitor import check_sla_breach


def execute_transition(
    *,
    instance,
    kind: str,
    new_status: str,
    user,
):
    """
    Single authoritative workflow execution path.

    Responsibilities:
    - validate transition legality (state machine)
    - enforce terminal-state lock
    - check role permissions (lab-scoped)
    - persist state change (safe update)
    - write transition timeline record
    - trigger SLA breach detection
    """

    kind = (kind or "").strip().lower()
    current = (getattr(instance, "status", None) or "").strip().upper()
    target = (new_status or "").strip().upper()

    # ---------------------------------------------------------
    # 1. HARD LOCK: terminal states
    # ---------------------------------------------------------
    if not allowed_next_states(kind, current):
        raise ValidationError(
            f"{kind.capitalize()} is in terminal state '{current}' "
            "and cannot be modified."
        )

    # ---------------------------------------------------------
    # 2. Validate transition legality
    # ---------------------------------------------------------
    try:
        validate_transition(kind=kind, old=current, new=target)
    except ValueError as e:
        raise ValidationError(str(e))

    # ---------------------------------------------------------
    # 3. Role enforcement (lab-scoped)
    # ---------------------------------------------------------
    required = required_roles(kind, current, target)

    if required:
        if user.is_superuser:
            user_roles = {"ADMIN"}
        else:
            user_roles = set(
                UserRole.objects.filter(
                    user=user,
                    laboratory=instance.laboratory,
                ).values_list("role", flat=True)
            )

        if not user_roles.intersection(required):
            raise PermissionDenied(
                f"You do not have the required role to transition "
                f"{kind} from {current} to {target}."
            )

    # ---------------------------------------------------------
    # 4. Apply transition + audit atomically
    # ---------------------------------------------------------
    with transaction.atomic():
        # Bypass model write guard safely
        instance.__class__.objects.filter(pk=instance.pk).update(
            status=target
        )

        WorkflowTransition.objects.create(
            kind=kind,
            object_id=instance.pk,
            from_status=current,
            to_status=target,
            performed_by=user,
            laboratory=instance.laboratory,
        )

    # ---------------------------------------------------------
    # 5. SLA breach detection (post-commit logic)
    # ---------------------------------------------------------
    check_sla_breach(
        kind=kind,
        object_id=instance.pk,
        user=user,
    )
