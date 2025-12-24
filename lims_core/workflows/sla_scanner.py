# lims_core/workflows/sla_scanner.py
from __future__ import annotations

from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from lims_core.models import (
    Sample,
    Experiment,
    WorkflowTransition,
    WorkflowAlert,
)

from lims_core.workflows.sla import get_sla


# ------------------------------------------------------------
# Workflow kind → model resolution
# ------------------------------------------------------------
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


def check_sla_breaches(*, now=None, created_by=None) -> int:
    """
    Scan all workflow objects and raise SLA alerts where thresholds are exceeded.

    Returns:
        int: number of newly created SLA alerts
    """
    now = now or timezone.now()
    created_count = 0

    for kind, model in KIND_MODEL.items():
        qs = model.objects.select_related("laboratory").all()

        for obj in qs.iterator():
            status = (getattr(obj, "status", "") or "").strip().upper()
            if not status:
                continue

            sla = get_sla(kind, status)
            if not sla:
                continue

            max_age = sla["max_age"]
            severity = sla.get("severity", "warning")

            started_at = _status_window_start(kind, obj.pk, status)
            if not started_at:
                continue

            deadline = started_at + max_age
            if now <= deadline:
                continue

            # Prevent duplicate alerts for the same breach window
            with transaction.atomic():
                alert, created = WorkflowAlert.objects.get_or_create(
                    kind=kind,
                    object_id=obj.pk,
                    state=status,
                    defaults={
                        "laboratory": getattr(obj, "laboratory", None),
                        "severity": severity,
                        "detected_at": now,
                        "message": (
                            f"SLA breached for {kind} {obj.pk} "
                            f"in state {status} (>{max_age})"
                        ),
                        "meta": {
                            "started_at": started_at.isoformat(),
                            "deadline": deadline.isoformat(),
                            "now": now.isoformat(),
                        },
                    },
                )

                if created:
                    created_count += 1

                    # --------------------------------------------------
                    # Optional email hook (safe placeholder)
                    # --------------------------------------------------
                    # from django.conf import settings
                    # from django.core.mail import send_mail
                    #
                    # send_mail(
                    #     subject=f"SLA breach: {kind} {obj.pk}",
                    #     message=alert.message,
                    #     from_email=settings.DEFAULT_FROM_EMAIL,
                    #     recipient_list=[...],
                    # )

    return created_count
