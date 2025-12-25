# lims_core/workflows/sla_resolver.py
from __future__ import annotations

from django.db.models import F, ExpressionWrapper, DurationField
from django.db.models.functions import Now

from lims_core.models import WorkflowAlert


def resolve_open_alerts_for_object(*, kind: str, object_id: int, current_state: str) -> int:
    """
    Auto-resolve any *open* SLA alerts for this object that are not for the current state.

    This is intentionally conservative and non-breaking:
    - We never delete anything.
    - We only set resolved_at + duration_seconds for rows where resolved_at IS NULL.
    - We resolve alerts for states the object is no longer in.

    Returns: number of alerts resolved.
    """
    kind = (kind or "").strip().lower()
    current_state = (current_state or "").strip().upper()

    qs = WorkflowAlert.objects.filter(
        kind=kind,
        object_id=object_id,
        resolved_at__isnull=True,
    ).exclude(state=current_state)

    # duration_seconds = (resolved_at - triggered_at) in seconds
    # resolved_at = Now()
    # duration_seconds stored as int, so compute via DB:
    # Use an interval expression then extract seconds in Python is tricky;
    # simplest safe approach is:
    # 1) set resolved_at now in DB
    # 2) re-fetch and compute in Python (still cheap because per-object)
    #
    # But we can keep it DB-only by using Now()-triggered_at to a DurationField,
    # then update duration_seconds via a follow-up update.
    #
    # Non-breaking + simple: do it in two steps.
    resolved_count = qs.update(resolved_at=Now())

    if resolved_count:
        # Compute duration_seconds for newly resolved rows
        # We only update rows resolved_at is not null and duration_seconds is 0 or null.
        # Your model uses PositiveIntegerField; if null is not allowed, it will be 0 by default.
        newly_resolved = WorkflowAlert.objects.filter(
            kind=kind,
            object_id=object_id,
            resolved_at__isnull=False,
        ).exclude(state=current_state).filter(duration_seconds=0)

        for alert in newly_resolved.iterator():
            delta = alert.resolved_at - alert.triggered_at
            seconds = int(delta.total_seconds()) if delta else 0
            if seconds < 0:
                seconds = 0
            WorkflowAlert.objects.filter(pk=alert.pk).update(duration_seconds=seconds)

    return resolved_count
