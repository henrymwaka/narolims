# lims_core/workflows/transition_service.py
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from lims_core.models import Sample, Experiment, WorkflowTransition, WorkflowAlert


KIND_MODEL = {
    "sample": Sample,
    "experiment": Experiment,
}


def _workflowalert_has_field(name: str) -> bool:
    try:
        WorkflowAlert._meta.get_field(name)
        return True
    except Exception:
        return False


def resolve_open_alerts(*, kind: str, object_id: int, state: str, now=None) -> int:
    """
    Resolve unresolved alerts for this object in the given state.
    Returns number of rows updated.

    Policy:
    - Always sets resolved_at
    - If WorkflowAlert has duration_seconds, compute it as (resolved_at - triggered_at) in seconds
      (or 0 if triggered_at is missing)
    """
    now = now or timezone.now()
    kind_norm = (kind or "").strip().lower()
    state_norm = (state or "").strip().upper()

    qs = WorkflowAlert.objects.filter(
        kind=kind_norm,
        object_id=object_id,
        state=state_norm,
        resolved_at__isnull=True,
    )

    # If duration_seconds exists, compute it deterministically here.
    if _workflowalert_has_field("duration_seconds"):
        updated = 0
        has_triggered_at = _workflowalert_has_field("triggered_at")

        for alert in qs.iterator():
            alert.resolved_at = now

            if has_triggered_at and getattr(alert, "triggered_at", None):
                delta = now - alert.triggered_at
                alert.duration_seconds = max(0, int(delta.total_seconds()))
            else:
                alert.duration_seconds = 0

            alert.save(update_fields=["resolved_at", "duration_seconds"])
            updated += 1

        return updated

    # Fallback for older schemas without duration_seconds
    return qs.update(resolved_at=now)


def transition_object(*, kind: str, object_id: int, to_status: str, performed_by=None, now=None) -> dict:
    """
    Atomically:
      1) Read current status
      2) Write WorkflowTransition row
      3) Update object.status
      4) Resolve alerts for previous state

    Returns a small dict for logging/testing.
    """
    now = now or timezone.now()
    kind_norm = (kind or "").strip().lower()
    to_status_norm = (to_status or "").strip().upper()

    if kind_norm not in KIND_MODEL:
        raise ValueError(f"Unknown workflow kind: {kind_norm}")
    if not to_status_norm:
        raise ValueError("to_status is required")

    model = KIND_MODEL[kind_norm]

    with transaction.atomic():
        obj = model.objects.select_for_update().get(pk=object_id)
        from_status = (getattr(obj, "status", "") or "").strip().upper()

        if from_status == to_status_norm:
            return {
                "changed": False,
                "kind": kind_norm,
                "object_id": obj.pk,
                "from_status": from_status,
                "to_status": to_status_norm,
                "alerts_resolved": 0,
                "transition_id": None,
            }

        # 1) Transition log
        t = WorkflowTransition.objects.create(
            kind=kind_norm,
            object_id=obj.pk,
            from_status=from_status,
            to_status=to_status_norm,
            performed_by=performed_by,
            laboratory=getattr(obj, "laboratory", None),
        )

        # 2) Update status safely (bypasses any save-level write guards)
        model.objects.filter(pk=obj.pk).update(status=to_status_norm, updated_at=now)

        # 3) Resolve alerts for the old state (and compute duration_seconds if supported)
        resolved = resolve_open_alerts(
            kind=kind_norm,
            object_id=obj.pk,
            state=from_status,
            now=now,
        )

        return {
            "changed": True,
            "kind": kind_norm,
            "object_id": obj.pk,
            "from_status": from_status,
            "to_status": to_status_norm,
            "alerts_resolved": resolved,
            "transition_id": t.id,
        }
