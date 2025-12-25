# lims_core/workflows/executor.py

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import PermissionDenied, ValidationError

from lims_core.models import WorkflowTransition, UserRole, WorkflowAlert
from lims_core.workflows import (
    validate_transition,
    allowed_next_states,
    required_roles,
    normalize_role,
)

from lims_core.workflows.sla_monitor import check_sla_breach


def _resolve_open_sla_alerts(*, kind: str, object_id: int, state: str) -> int:
    kind = (kind or "").strip().lower()
    state = (state or "").strip().upper()
    if not kind or not state:
        return 0

    now = timezone.now()

    qs = WorkflowAlert.objects.filter(
        kind=kind,
        object_id=object_id,
        state=state,
        resolved_at__isnull=True,
    )

    updated = 0
    for alert in qs.iterator():
        alert.resolved_at = now
        if alert.triggered_at:
            delta = now - alert.triggered_at
            alert.duration_seconds = max(0, int(delta.total_seconds()))
        else:
            alert.duration_seconds = 0
        alert.save(update_fields=["resolved_at", "duration_seconds"])
        updated += 1

    return updated


def execute_transition(*, instance, kind: str, new_status: str, user):
    kind = (kind or "").strip().lower()
    current = (getattr(instance, "status", None) or "").strip().upper()
    target = (new_status or "").strip().upper()

    # 1) Terminal state lock
    if not allowed_next_states(kind, current):
        raise ValidationError(
            {"status": f"{kind.capitalize()} is in terminal state '{current}' and cannot be modified."}
        )

    # 2) Validate transition legality (must be field-shaped)
    try:
        validate_transition(kind=kind, old=current, new=target)
    except ValueError as e:
        raise ValidationError({"status": str(e)})

    # No-op transition
    if current == target:
        return

    # 3) Role enforcement (lab-scoped)
    required = {normalize_role(r) for r in (required_roles(kind, current, target) or set())}

    if required:
        if user.is_superuser:
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

    # 4) Apply transition + timeline atomically
    with transaction.atomic():
        instance.__class__.objects.filter(pk=instance.pk).update(status=target)

        WorkflowTransition.objects.create(
            kind=kind,
            object_id=instance.pk,
            from_status=current,
            to_status=target,
            performed_by=user,
            laboratory=instance.laboratory,
        )

        _resolve_open_sla_alerts(kind=kind, object_id=instance.pk, state=current)

    # 5) SLA evaluation for current state
    check_sla_breach(kind=kind, object_id=instance.pk, user=user)
