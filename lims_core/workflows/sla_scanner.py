# lims_core/workflows/sla_scanner.py
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from lims_core.models import (
    Sample,
    Experiment,
    WorkflowTransition,
    WorkflowAlert,
)

from lims_core.workflows.sla import get_sla


KIND_MODEL = {
    "sample": Sample,
    "experiment": Experiment,
}


def _status_window_start(kind: str, object_id: int, status: str):
    """
    Determine when an object entered a given status.
    WorkflowTransition is the single source of truth.
    """
    t = (
        WorkflowTransition.objects.filter(
            kind=kind,
            object_id=object_id,
            to_status=status,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    return t.created_at if t else None


def _created_timestamp(obj):
    """
    Best-effort fallback for objects that may not have a transition
    recorded for their initial state (e.g., REGISTERED).
    """
    return (
        getattr(obj, "created_at", None)
        or getattr(obj, "created_on", None)
        or getattr(obj, "created", None)
    )


def check_sla_breaches(*, now=None, created_by=None) -> int:
    """
    Scan workflow objects and create WorkflowAlert rows when warning/breach thresholds are exceeded.

    WorkflowAlert fields in your model:
      - kind, object_id, state
      - sla_seconds: threshold used for the alert
      - duration_seconds: how long it has been in the state
      - triggered_at, resolved_at, created_by

    Returns:
        int: number of newly created alerts
    """
    now = now or timezone.now()
    created_count = 0

    for kind, model in KIND_MODEL.items():
        qs = model.objects.all()

        for obj in qs.iterator():
            status = (getattr(obj, "status", "") or "").strip().upper()
            if not status:
                continue

            sla = get_sla(kind, status)
            if not sla:
                continue

            warn_after = sla.get("warn_after")
            breach_after = sla.get("breach_after")

            started_at = _status_window_start(kind, obj.pk, status)

            # ------------------------------------------------------------
            # Safe fallback: some objects may not have an initial transition
            # row for REGISTERED. In that case, use object creation time.
            # ------------------------------------------------------------
            if not started_at and kind == "sample" and status == "REGISTERED":
                started_at = _created_timestamp(obj)

            if not started_at:
                continue

            elapsed = now - started_at
            elapsed_seconds = int(elapsed.total_seconds())

            threshold = None
            if breach_after and elapsed > breach_after:
                threshold = breach_after
            elif warn_after and elapsed > warn_after:
                threshold = warn_after
            else:
                continue

            sla_seconds = int(threshold.total_seconds()) if threshold else 0

            with transaction.atomic():
                alert = (
                    WorkflowAlert.objects.select_for_update()
                    .filter(
                        kind=kind,
                        object_id=obj.pk,
                        state=status,
                        resolved_at__isnull=True,
                    )
                    .first()
                )

                if alert:
                    # Keep it fresh without creating duplicates
                    alert.duration_seconds = elapsed_seconds
                    alert.sla_seconds = sla_seconds
                    alert.save(update_fields=["duration_seconds", "sla_seconds"])
                    continue

                WorkflowAlert.objects.create(
                    kind=kind,
                    object_id=obj.pk,
                    state=status,
                    sla_seconds=sla_seconds,
                    duration_seconds=elapsed_seconds,
                    triggered_at=now,
                    resolved_at=None,
                    created_by=created_by,
                )
                created_count += 1

    return created_count
