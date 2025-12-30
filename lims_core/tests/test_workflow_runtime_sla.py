# lims_core/tests/test_workflow_runtime_sla.py
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from lims_core.models import (
    Sample,
    Project,
    WorkflowEvent,
)
from lims_core.views_workflow_runtime import _get_state_entered_at


# ---------------------------------------------------------------------
# Factories (schema-aware, time-safe)
# ---------------------------------------------------------------------

def create_project():
    return Project.objects.create(name="Test Project")


def create_sample(*, status="REGISTERED"):
    return Sample.objects.create(
        project=create_project(),
        status=status,
    )


def create_workflow_event(
    *,
    kind: str,
    object_id: int,
    from_status: str,
    to_status: str,
    performed_by,
    created_at,
    role: str = "SYSTEM",
    comment: str = "",
):
    """
    IMPORTANT:
    WorkflowEvent.created_at uses auto_now_add=True.
    Django WILL ignore passed values.

    Therefore:
    - Create first
    - Then UPDATE created_at explicitly
    """
    e = WorkflowEvent.objects.create(
        kind=kind,
        object_id=object_id,
        from_status=from_status,
        to_status=to_status,
        performed_by=performed_by,
        role=role,
        comment=comment,
    )

    WorkflowEvent.objects.filter(pk=e.pk).update(created_at=created_at)
    e.refresh_from_db()
    return e


# ---------------------------------------------------------------------
# Tests: state entry resolution
# ---------------------------------------------------------------------

@pytest.mark.django_db
def test_get_state_entered_at_prefers_latest_matching_transition():
    User = get_user_model()
    user = User.objects.create_user(username="u1", password="x")

    sample = create_sample(status="REGISTERED")

    t1 = timezone.now() - timedelta(days=2)
    t2 = timezone.now() - timedelta(hours=3)

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="INITIAL",
        to_status="REGISTERED",
        performed_by=user,
        created_at=t1,
    )

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="IN_PROCESS",
        to_status="REGISTERED",
        performed_by=user,
        created_at=t2,
    )

    entered_at = _get_state_entered_at(
        kind="sample",
        object_id=sample.pk,
        current_status="REGISTERED",
        obj=sample,
    )

    assert entered_at == t2


@pytest.mark.django_db
def test_get_state_entered_at_falls_back_to_latest_event():
    User = get_user_model()
    user = User.objects.create_user(username="u2", password="x")

    sample = create_sample(status="REGISTERED")

    t1 = timezone.now() - timedelta(days=1)

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="INITIAL",
        to_status="IN_PROCESS",
        performed_by=user,
        created_at=t1,
    )

    entered_at = _get_state_entered_at(
        kind="sample",
        object_id=sample.pk,
        current_status="REGISTERED",
        obj=sample,
    )

    assert entered_at == t1


# ---------------------------------------------------------------------
# Tests: SLA payload exposure via API
# ---------------------------------------------------------------------

@pytest.mark.django_db
def test_timeline_sla_payload_has_stable_minimum_fields():
    User = get_user_model()
    user = User.objects.create_user(username="u3", password="x")

    sample = create_sample(status="REGISTERED")

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="INITIAL",
        to_status="REGISTERED",
        performed_by=user,
        created_at=timezone.now() - timedelta(hours=6),
    )

    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get(f"/lims/workflows/sample/{sample.pk}/timeline/")
    assert resp.status_code == 200

    sla = resp.json()["sla"]

    for key in (
        "applies",
        "status",
        "severity",
        "entered_at",
        "age_seconds",
        "warn_after_seconds",
        "breach_after_seconds",
        "remaining_seconds",
    ):
        assert key in sla


@pytest.mark.django_db
def test_latest_matching_transition_is_used_for_state_time_if_exposed():
    User = get_user_model()
    user = User.objects.create_user(username="u4", password="x")

    sample = create_sample(status="REGISTERED")

    t1 = timezone.now() - timedelta(days=2)
    t2 = timezone.now() - timedelta(hours=1)

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="INITIAL",
        to_status="REGISTERED",
        performed_by=user,
        created_at=t1,
    )

    create_workflow_event(
        kind="sample",
        object_id=sample.pk,
        from_status="IN_PROCESS",
        to_status="REGISTERED",
        performed_by=user,
        created_at=t2,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get(f"/lims/workflows/sample/{sample.pk}/timeline/")
    assert resp.status_code == 200

    # API returns ISO string
    assert resp.json()["entered_at"].startswith(t2.isoformat()[:19])
