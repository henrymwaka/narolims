# lims_core/workflows/sla_monitor.py

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from django.db import transaction

# Optional email hook (safe placeholder)
# from django.conf import settings
# from django.core.mail import send_mail

from lims_core.models import (
    WorkflowTransition,
    WorkflowAlert,
)

from lims_core.workflows.sla import SLA_DEFINITIONS


def check_sla_breach(*, kind: str, object_id: int, user=None):
    """
    Detect SLA breaches for a workflow object.

    Called after a successful workflow transition.

    Responsibilities:
    - determine SLA rules for the workflow kind
    - compute elapsed time since last transition
    - create WorkflowAlert if SLA exceeded
    - remain idempotent (no duplicate alerts)
    """

    kind = (kind or "").strip().lower()

    if kind not in SLA_DEFINITIONS:
        return

    rules = SLA_DEFINITIONS[kind]

    # ---------------------------------------------------------
    # Get most recent transition
    # ---------------------------------------------------------
    last_transition = (
        WorkflowTransition.objects
        .filter(kind=kind, object_id=object_id)
        .order_by("-created_at")
        .first()
    )

    if not last_transition:
        return

    state = last_transition.to_status

    if state not in rules:
        return

    sla_hours = rules[state]
    if sla_hours is None:
        return

    deadline = last_transition.created_at + timedelta(hours=sla_hours)
    now = timezone.now()

    if now <= deadline:
        return

    # ---------------------------------------------------------
    # Prevent duplicate alerts
    # ---------------------------------------------------------
    if WorkflowAlert.objects.filter(
        kind=kind,
        object_id=object_id,
        state=state,
        resolved=False,
    ).exists():
        return

    # ---------------------------------------------------------
    # Create SLA breach alert
    # ---------------------------------------------------------
    with transaction.atomic():
        alert = WorkflowAlert.objects.create(
            kind=kind,
            object_id=object_id,
            state=state,
            breached_at=now,
            deadline=deadline,
            created_by=user if user and user.is_authenticated else None,
        )

    # ---------------------------------------------------------
    # OPTIONAL: email notification hook (disabled by default)
    # ---------------------------------------------------------
    # send_mail(
    #     subject=f"SLA breach: {kind} {object_id}",
    #     message=(
    #         f"The workflow object {kind} (ID {object_id}) "
    #         f"has exceeded its SLA while in state '{state}'.\n\n"
    #         f"Deadline: {deadline}\n"
    #         f"Breach detected at: {now}"
    #     ),
    #     from_email=settings.DEFAULT_FROM_EMAIL,
    #     recipient_list=[
    #         # "lab-manager@example.org",
    #         # "qa@example.org",
    #     ],
    # )
