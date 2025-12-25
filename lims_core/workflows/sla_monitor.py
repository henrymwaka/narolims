# lims_core/workflows/sla_monitor.py

from __future__ import annotations

from django.utils import timezone
from django.db import transaction

from lims_core.models import WorkflowTransition, WorkflowAlert
from lims_core.workflows.sla import get_sla


def check_sla_breach(*, kind: str, object_id: int, user=None) -> None:
    """
    Evaluate SLA for the current state of (kind, object_id).

    Called AFTER a successful workflow transition, and also safe for use
    by periodic scanners.

    Responsibilities:
    - determine current state entry time from WorkflowTransition
    - check SLA definition for that state
    - create an open WorkflowAlert if the SLA is exceeded
    - remain idempotent (no duplicate open alerts)
    """

    kind = (kind or "").strip().lower()
    if not kind:
        return

    # ---------------------------------------------------------
    # Find most recent transition (authoritative current state)
    # ---------------------------------------------------------
    transition = (
        WorkflowTransition.objects
        .filter(kind=kind, object_id=object_id)
        .order_by("-created_at", "-id")
        .first()
    )
    if not transition:
        return

    state = (transition.to_status or "").strip().upper()
    entered_at = transition.created_at
    now = timezone.now()

    if not state or not entered_at:
        return

    # ---------------------------------------------------------
    # SLA applicability for current state
    # ---------------------------------------------------------
    sla = get_sla(kind, state)
    if not sla:
        return

    max_age = sla.get("max_age")
    if not max_age:
        return

    deadline = entered_at + max_age
    if now <= deadline:
        return

    # ---------------------------------------------------------
    # Prevent duplicate open alerts
    # ---------------------------------------------------------
    if WorkflowAlert.objects.filter(
        kind=kind,
        object_id=object_id,
        state=state,
        resolved_at__isnull=True,
    ).exists():
        return

    # ---------------------------------------------------------
    # Create SLA breach alert
    # ---------------------------------------------------------
    duration = int((now - entered_at).total_seconds())

    with transaction.atomic():
        WorkflowAlert.objects.create(
            kind=kind,
            object_id=object_id,
            state=state,
            sla_seconds=int(max_age.total_seconds()),
            duration_seconds=max(duration, 0),
            triggered_at=entered_at,
            resolved_at=None,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
